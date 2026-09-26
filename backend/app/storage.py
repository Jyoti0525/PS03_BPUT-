"""File and object storage. Local-disk backend; swap for S3/MinIO by implementing the same 3 calls.

Every object gets an expiry timestamp at upload (minimal retention). The purge job that deletes
expired objects belongs to the data track; `purge_expired` is the hook it calls.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .config import get_settings
from .models import FileObject

ALLOWED_TYPES = {
    "report": ("image/", "application/pdf"),
    "image": ("image/",),
    "audio": ("audio/", "video/webm"),
}


def _root() -> Path:
    p = Path(get_settings().storage_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def retention_hours(kind: str) -> int:
    s = get_settings()
    return {"audio": s.retention_hours_audio, "image": s.retention_hours_image, "report": s.retention_hours_report}[kind]


def expiry_for(kind: str, start: datetime | None = None) -> datetime:
    return (start or datetime.now(timezone.utc)) + timedelta(hours=retention_hours(kind))


_s3 = None


def _client():
    """Lazily built S3 client (Cloudflare R2 speaks the S3 API)."""
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


def _use_s3() -> bool:
    return get_settings().storage_backend == "s3"


def put(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    if _use_s3():
        _client().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type)
        return
    path = _root() / key
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def get(key: str) -> bytes | None:
    if _use_s3():
        try:
            return _client().get_object(Bucket=get_settings().s3_bucket, Key=key)["Body"].read()
        except Exception:  # missing object or transient error → treat as gone
            return None
    path = _root() / key
    return path.read_bytes() if path.exists() else None


def delete(key: str) -> None:
    if _use_s3():
        _client().delete_object(Bucket=get_settings().s3_bucket, Key=key)
        return
    (_root() / key).unlink(missing_ok=True)


def health() -> str:
    """Backend name, verified by a cheap call for S3."""
    if _use_s3():
        _client().head_bucket(Bucket=get_settings().s3_bucket)
        return "s3"
    return "local"


def purge_expired(db: Session) -> int:
    """Delete bytes of expired objects, keep metadata, and log each purge."""
    now = datetime.now(timezone.utc)
    n = 0
    for f in list(db.scalars(select(FileObject).where(FileObject.purged_at.is_(None)))):
        exp = f.expires_at if f.expires_at.tzinfo else f.expires_at.replace(tzinfo=timezone.utc)
        if exp > now:
            continue
        if f.storage_key:
            delete(f.storage_key)
        f.purged_at = now
        n += 1
        audit.record(db, None, "PURGE", "file", f.id, f"{f.kind} {f.filename} deleted at end of retention window")
    db.commit()
    return n
