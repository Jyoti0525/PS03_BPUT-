"""Domain logic shared by routers and the seed script."""

import threading
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit
from .config import get_settings
from .models import Consent, Encounter, Escalation, Facility, FileObject, Patient, User
from .schemas import ADMIN_ROLES, ConsentOut, EncounterOut, PatientOut
from .triage.pipeline import build_note, infer_specialist
from .triage.rules import evaluate


def aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def now() -> datetime:
    return datetime.now(timezone.utc)


def escalate_after(urgency: str) -> int | None:
    s = get_settings()
    return {"red": s.escalate_red_min, "yellow": s.escalate_yellow_min}.get(urgency)


def next_patient_code(db: Session) -> str:
    n = db.scalar(select(func.count(Patient.id))) or 0
    while True:
        n += 1
        code = f"JVA-P{n:03d}"
        if not db.scalar(select(Patient.id).where(Patient.code == code)):
            return code


def own_patient(db: Session, user: User) -> Patient | None:
    """A patient account links to exactly one record (phone + name) even on a shared household phone."""
    return db.scalar(select(Patient).where(Patient.phone == user.phone, Patient.name == user.name))


def create_encounter(db: Session, intake: dict, patient: Patient, created: datetime | None = None) -> Encounter:
    created = created or now()
    history = list(
        db.scalars(select(Encounter).where(Encounter.patient_id == patient.id).order_by(Encounter.created_at.desc()))
    )
    files = [f for f in (db.get(FileObject, fid) for fid in intake.get("file_ids", [])) if f]
    urgency, hits = evaluate(intake, patient.age)
    consent = db.get(Consent, intake["consent_id"]) if intake.get("consent_id") else None
    note = build_note(intake=intake, patient=patient, hits=hits, files=files, history=history, proxy=bool(consent and consent.mode == "proxy"))
    specialist = infer_specialist(intake, patient.age)
    facility = db.get(Facility, intake["facility_id"])
    on_site = any(s["key"] == specialist and s["available"] for s in (facility.specialists if facility else []))
    esc = escalate_after(urgency)
    enc = Encounter(
        patient_id=patient.id,
        facility_id=intake["facility_id"],
        category=intake["category"],
        status="queued",
        chief_complaint=intake["chief_complaint"],
        created_at=created,
        urgency=urgency,
        rules_urgency=urgency,
        urgency_source="rules",
        note=note,
        intake=intake,
        referral_needed=True if urgency == "red" and not on_site else None,
        specialist_required=specialist,
        escalation_due_at=created + timedelta(minutes=esc) if esc else None,
        consent_id=intake.get("consent_id"),
        client_ref=intake["client_ref"],
    )
    db.add(enc)
    db.flush()
    for f in files:
        f.encounter_id = enc.id
    return enc


def encounter_out(e: Encounter, viewer: User) -> EncounterOut:
    out = EncounterOut(
        id=e.id,
        patient=PatientOut.model_validate(e.patient),
        facility_id=e.facility_id,
        category=e.category,
        status=e.status,
        chief_complaint=e.chief_complaint,
        created_at=aware(e.created_at),
        urgency=e.urgency,
        urgency_source=e.urgency_source,
        note=e.note,
        intake=e.intake,
        override=e.override,
        reviewed_by=e.reviewed_by,
        reviewed_at=aware(e.reviewed_at),
        referral_needed=e.referral_needed,
        specialist_required=e.specialist_required,
        escalation_due_at=aware(e.escalation_due_at),
        consent=ConsentOut.model_validate(e.consent) if e.consent else None,
    )
    if viewer.role == "patient":
        # Health outputs stay reviewer-facing: no urgency, no AI note, no override.
        out.urgency = None
        out.note = None
        out.override = None
        out.escalation_due_at = None
        out.specialist_required = None
        out.referral_needed = None
    return out


def load_encounter(db: Session, eid: str, user: User, *, clinical: bool = True) -> Encounter:
    if clinical and (user.role in ADMIN_ROLES or user.role == "employer"):
        raise HTTPException(403, "This role cannot read clinical notes")
    e = db.get(Encounter, eid)
    if not e:
        raise HTTPException(404, "Encounter not found")
    if user.role == "patient":
        mine = own_patient(db, user)
        if not mine or mine.id != e.patient_id:
            raise HTTPException(403, "Not your record")
    elif user.facility_id and e.facility_id != user.facility_id:
        raise HTTPException(403, "Encounter belongs to another facility")
    return e


_escalation_lock = threading.Lock()


def auto_escalate(db: Session) -> None:
    """Critical/semi-urgent cases that wait past their window are escalated to the senior MO.

    Evaluated lazily on queue / escalation / stats reads; the lock stops two concurrent reads from
    raising the same escalation twice.
    """
    with _escalation_lock:
        _auto_escalate(db)


def _auto_escalate(db: Session) -> None:
    t = now()
    due = list(db.scalars(select(Encounter).where(Encounter.status == "queued", Encounter.escalation_due_at.is_not(None))))
    changed = False
    for e in due:
        if aware(e.escalation_due_at) > t:
            continue
        if db.scalar(select(Escalation.id).where(Escalation.encounter_id == e.id)):
            continue
        reason = f"Unreviewed {'critical' if e.urgency == 'red' else 'semi-urgent'} case past {escalate_after(e.urgency)} min"
        db.add(Escalation(encounter_id=e.id, raised_by="Escalation timer", raised_at=aware(e.escalation_due_at), to_role="senior_mo", reason=reason, auto=True))
        e.status = "escalated"
        audit.record(db, None, "ESCALATE", "encounter", e.id, reason, e.patient.code, e.facility_id)
        changed = True
    if changed:
        db.commit()
