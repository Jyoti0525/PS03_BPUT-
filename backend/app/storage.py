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


def put(key: str, data: bytes) -> None:
    path = _root() / key
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def get(key: str) -> bytes | None:
    path = _root() / key
    return path.read_bytes() if path.exists() else None


def delete(key: str) -> None:
    (_root() / key).unlink(missing_ok=True)


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
