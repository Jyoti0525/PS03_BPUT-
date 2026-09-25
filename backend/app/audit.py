"""Append-only, hash-chained audit log (G4). Every VIEW of a clinical record is written here."""

import hashlib
import json
import threading
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import AuditEvent, User

_lock = threading.Lock()
_PG_LOCK_KEY = 7_274_421  # arbitrary constant for pg_advisory_xact_lock


def _digest(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()


def _body(e: AuditEvent) -> dict:
    return {
        "ts": e.ts.astimezone(timezone.utc).isoformat() if e.ts.tzinfo else e.ts.replace(tzinfo=timezone.utc).isoformat(),
        "actor_id": e.actor_id,
        "actor_name": e.actor_name,
        "actor_role": e.actor_role,
        "facility_id": e.facility_id,
        "action": e.action,
        "resource_type": e.resource_type,
        "resource_id": e.resource_id,
        "patient_code": e.patient_code,
        "detail": e.detail,
    }


def record(
    db: Session | None,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    detail: str,
    patient_code: str | None = None,
    facility_id: str | None = None,
    ts: datetime | None = None,
) -> AuditEvent:
    """Append one event.

    The caller's pending changes are committed first, so the log only describes actions that
    actually persisted. The event itself is written in its own short transaction, serialised by a
    process lock and (on Postgres) an advisory lock, so the chain never forks across requests or
    workers and no request transaction is ever held open while waiting for the chain.
    """
    if db is not None and db.in_transaction():
        db.commit()
    with _lock, SessionLocal() as s:
        if s.get_bind().dialect.name == "postgresql":
            s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _PG_LOCK_KEY})
        last = s.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
        prev = last.hash if last else "GENESIS"
        e = AuditEvent(
            ts=(ts or datetime.now(timezone.utc)).replace(microsecond=0),
            actor_id=actor.id if actor else None,
            actor_name=actor.name if actor else "System",
            actor_role=actor.role if actor else "system",
            facility_id=facility_id or (actor.facility_id if actor else None),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_code=patient_code,
            detail=detail,
            prev_hash=prev,
            hash="",
        )
        e.hash = _digest(prev, _body(e))
        s.add(e)
        s.commit()
        return e


def verify(db: Session) -> tuple[bool, int, int | None]:
    prev = "GENESIS"
    n = 0
    for e in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars():
        n += 1
        if e.prev_hash != prev or e.hash != _digest(prev, _body(e)):
            return False, n, e.id
        prev = e.hash
    return True, n, None
