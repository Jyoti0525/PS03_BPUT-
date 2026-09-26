"""File and object storage.

Backends (JEEVIA_STORAGE_BACKEND):
* local      — files on the API server's disk (development; wiped on Render restarts).
* cloudinary — Cloudinary, uploaded as `type=authenticated`, so files are never publicly
               reachable; the API fetches them with signed download URLs and streams them only
               to callers it has authorised. Layout: jeevia/<facility>/<yyyy-mm>/<kind>/<file id>.
* s3         — any S3-compatible store (Cloudflare R2, MinIO, AWS).

`put` returns the storage key to save on the FileObject; `get`/`delete` accept that key, so files
written under an older backend stay readable after switching.

Every object gets an expiry timestamp at upload (minimal retention). `purge_expired` deletes
expired bytes, keeps metadata and writes a PURGE audit event.
"""

import io
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .config import get_settings
from .models import FileObject

log = logging.getLogger("jeevia.storage")

ALLOWED_TYPES = {
    "report": ("image/", "application/pdf"),
    "image": ("image/",),
    "audio": ("audio/", "video/webm"),
}


def retention_hours(kind: str) -> int:
    s = get_settings()
    return {"audio": s.retention_hours_audio, "image": s.retention_hours_image, "report": s.retention_hours_report}[kind]


def expiry_for(kind: str, start: datetime | None = None) -> datetime:
    return (start or datetime.now(timezone.utc)) + timedelta(hours=retention_hours(kind))


# ── local disk ────────────────────────────────────────
def _root() -> Path:
    p = Path(get_settings().storage_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _local_put(key: str, data: bytes) -> str:
    path = _root() / key
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return key


# ── Cloudinary ────────────────────────────────────────
_cld_ready = False


def _cld():
    global _cld_ready
    import cloudinary
    import cloudinary.api
    import cloudinary.uploader
    import cloudinary.utils

    if not _cld_ready:
        s = get_settings()
        cloudinary.config(cloud_name=s.cloudinary_cloud_name, api_key=s.cloudinary_api_key, api_secret=s.cloudinary_api_secret, secure=True)
        _cld_ready = True
    return cloudinary


def _cld_resource_type(content_type: str) -> str:
    if content_type.startswith("image/") or content_type == "application/pdf":
        return "image"  # Cloudinary stores PDFs as images (page previews work)
    if content_type.startswith(("audio/", "video/")):
        return "video"
    return "raw"


def _cld_put(file_id: str, data: bytes, content_type: str, folder: str) -> str:
    c = _cld()
    rt = _cld_resource_type(content_type)
    r = c.uploader.upload(io.BytesIO(data), public_id=file_id, folder=folder, resource_type=rt, type="authenticated", overwrite=False, tags=["jeevia"])
    return f"cld:{rt}:{r.get('format') or ''}:{r['public_id']}"


def _cld_parse(key: str) -> tuple[str, str, str]:
    _, rt, fmt, public_id = key.split(":", 3)
    return rt, fmt, public_id


def _cld_get(key: str) -> bytes | None:
    rt, fmt, public_id = _cld_parse(key)
    url = _cld().utils.private_download_url(public_id, fmt, resource_type=rt, type="authenticated")
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True)
    except httpx.HTTPError:
        return None
    return r.content if r.status_code == 200 else None


def _cld_delete(key: str) -> None:
    rt, _, public_id = _cld_parse(key)
    _cld().uploader.destroy(public_id, resource_type=rt, type="authenticated", invalidate=True)


# ── S3-compatible (Cloudflare R2) ─────────────────────
_s3 = None


def _client():
    global _s3
    if _s3 is None:
        import boto3
        from botocore.config import Config

        s = get_settings()
        _s3 = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint,
            aws_access_key_id=s.s3_access_key_id,
            aws_secret_access_key=s.s3_secret_access_key,
            region_name=s.s3_region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )
    return _s3


# ── public API ────────────────────────────────────────
def folder_for(facility_id: str | None, kind: str, when: datetime | None = None) -> str:
    d = when or datetime.now(timezone.utc)
    return f"jeevia/{facility_id or 'patients'}/{d:%Y-%m}/{kind}"


def put(file_id: str, data: bytes, content_type: str = "application/octet-stream", folder: str = "jeevia/misc") -> str:
    backend = get_settings().storage_backend
    if backend == "cloudinary":
        return _cld_put(file_id, data, content_type, folder)
    if backend == "s3":
        key = f"{folder}/{file_id}"
        _client().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3:{key}"
    return _local_put(file_id, data)


def get(key: str) -> bytes | None:
    if key.startswith("cld:"):
        return _cld_get(key)
    if key.startswith("s3:"):
        try:
            return _client().get_object(Bucket=get_settings().s3_bucket, Key=key[3:])["Body"].read()
        except Exception:
            return None
    path = _root() / key
    return path.read_bytes() if path.exists() else None


def delete(key: str) -> None:
    if key.startswith("cld:"):
        _cld_delete(key)
    elif key.startswith("s3:"):
        _client().delete_object(Bucket=get_settings().s3_bucket, Key=key[3:])
    else:
        (_root() / key).unlink(missing_ok=True)


_health: tuple[float, dict] | None = None


def health() -> dict:
    """Backend name and reachability. Cached for 10 minutes so status polling never burns API quota."""
    global _health
    if _health and time.time() - _health[0] < 600:
        return _health[1]
    backend = get_settings().storage_backend
    ok = True
    try:
        if backend == "cloudinary":
            _cld().api.ping()
        elif backend == "s3":
            _client().head_bucket(Bucket=get_settings().s3_bucket)
    except Exception:  # report, never raise from a health check
        ok = False
        log.warning("storage health check failed")
    out = {"backend": backend, "ok": ok, "persistent": backend != "local"}
    _health = (time.time(), out)
    return out


def purge_expired(db: Session) -> int:
    """Delete bytes of expired objects, keep metadata, and log each purge."""
    now = datetime.now(timezone.utc)
    n = 0
    for f in list(db.scalars(select(FileObject).where(FileObject.purged_at.is_(None)))):
        if f.expires_at > now:
            continue
        if f.storage_key:
            try:
                delete(f.storage_key)
            except Exception:
                log.warning("purge failed")
                continue
        f.purged_at = now
        n += 1
        audit.record(db, None, "PURGE", "file", f.id, f"{f.kind} {f.filename} deleted at end of retention window")
    db.commit()
    return n
