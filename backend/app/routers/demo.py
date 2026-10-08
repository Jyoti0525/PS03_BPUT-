"""Sample-data switch for the demo laptop (landing page).

On: the demo database is rebuilt with every sample facility, staff account and patient, timed from now, so the queue
never shows a two-day wait left over from an old seed. Off: the same rebuild, then every sample patient and visit is
removed; facilities, staff accounts and kiosk links stay, so staff can sign in to empty queues and enter patients live.

Either way everything else on this server is cleared too (it is a demo database). Off unless JEEVIA_DEMO_CONTROLS is
true, and refused on PostgreSQL (the hosted copy, whose audit log is append-only): only a local SQLite demo can be reset.
"""

import importlib

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from .. import audit, ratelimit
from ..config import get_settings
from ..db import Base, SessionLocal, engine
from ..models import Encounter, Facility, Patient

router = APIRouter(tags=["demo"])

# Kept when sample data is off: the places and the people who sign in. Revoked tokens stay so a signed-out session
# cannot come back; the facility directory (public OSM data) is never touched.
KEEP_WHEN_OFF = {"organisations", "facility_directory", "facilities", "users", "devices", "kiosk_links", "revoked_tokens"}
NEVER_CLEARED = {"facility_directory", "revoked_tokens"}
MARKER_PATIENT = "JVA-P001"


class SamplesIn(BaseModel):
    on: bool


def _allowed() -> bool:
    return get_settings().demo_controls and engine.dialect.name == "sqlite"


def samples_on() -> bool:
    with SessionLocal() as db:
        return db.scalar(select(Patient.id).where(Patient.code == MARKER_PATIENT)) is not None


def _state() -> dict:
    return {"available": _allowed(), "on": samples_on()}


def rebuild(on: bool) -> None:
    from .. import scenarios, seed

    tables = [t for t in reversed(Base.metadata.sorted_tables) if t.name not in NEVER_CLEARED]
    with engine.begin() as conn:
        for t in tables:
            conn.execute(t.delete())
    seed_mod = importlib.reload(seed)  # its sample times are computed at import: take them from now
    with SessionLocal() as db:
        seed_mod.seed(db)
    if get_settings().seed_scenarios:
        with SessionLocal() as db:
            scenarios.scenarios(db)
            scenarios.call_scenarios(db)
            scenarios.facility_kinds(db)
            if get_settings().seed_synthea:
                scenarios.synthea_histories(db)
    if not on:
        with engine.begin() as conn:
            for t in tables:
                if t.name not in KEEP_WHEN_OFF:
                    conn.execute(t.delete())
    with SessionLocal() as db:
        audit.record(db, None, "CONFIG", "system", None, "Demo database rebuilt: " + ("sample patients loaded, timed from now" if on else "no sample patients"))
        db.commit()


@router.get("/demo/samples")
def samples_state() -> dict:
    return _state()


@router.post("/demo/samples")
def set_samples(body: SamplesIn, request: Request) -> dict:
    if not _allowed():
        raise HTTPException(403, "The sample-data switch works only on the demo laptop")
    ratelimit.hit(f"demo:{ratelimit.client_key(request)}", 6)
    rebuild(body.on)
    return _state()


RANK = {"red": 0, "yellow": 1, "green": 2}


@router.get("/demo/queue-preview")
def queue_preview(facility_id: str = "fac_phc_manikpur") -> dict:
    """The landing page's hero card, from the real queue, on the demo laptop only. Synthetic patients only, never a
    record entered as real; a public page must not show real patients, so anywhere else this is refused."""
    if not _allowed():
        raise HTTPException(404, "Not available")
    from ..alerts import why_tier
    from ..services import now, wait_minutes
    from ..triage.rules import load_rules

    t = now()
    with SessionLocal() as db:
        fac = db.get(Facility, facility_id)
        if not fac:
            raise HTTPException(404, "Unknown facility")
        rows = [e for e in db.scalars(select(Encounter).where(Encounter.facility_id == facility_id, Encounter.status.in_(("queued", "in_review", "escalated"))))
                if e.patient.data_origin == "SYNTHETIC" and e.urgency in RANK]
        rows.sort(key=lambda e: (RANK[e.urgency], -wait_minutes(e, t)))
        items = [{"name": e.patient.name.replace(" (sample)", ""), "age": e.patient.age, "sex": e.patient.sex, "complaint": e.chief_complaint,
                  "urgency": e.urgency, "why": why_tier(e), "wait_minutes": wait_minutes(e, t)} for e in rows]
        return {"facility": fac.name, "waiting": len(items), "red": sum(i["urgency"] == "red" for i in items), "rules": len(load_rules()), "items": items[:4]}
