"""Domain logic shared by routers and the seed script."""

import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit
from .config import get_settings
from .models import Consent, Encounter, Escalation, Facility, FileObject, Patient, User
from .schemas import ADMIN_ROLES, ConsentOut, EncounterOut, FitnessOut, PatientOut, WorkerInfo
from .triage.pipeline import build_note, infer_specialist
from .triage.extraction import lab_values
from .triage.rules import evaluate_full


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


_token_lock = threading.Lock()


def local_day(d: datetime) -> str:
    return d.astimezone(ZoneInfo(get_settings().timezone)).date().isoformat()


def next_token(db: Session, facility_id: str, day: str) -> str:
    """Daily running number per facility: T-001, T-002 … (resets at local midnight)."""
    n = db.scalar(select(func.count(Encounter.id)).where(Encounter.facility_id == facility_id, Encounter.token_date == day)) or 0
    return f"T-{n + 1:03d}"


def create_encounter(db: Session, intake: dict, patient: Patient, created: datetime | None = None, channel: str = "staff_kiosk") -> Encounter:
    with _token_lock:
        return _create_encounter(db, intake, patient, created, channel)


def _create_encounter(db: Session, intake: dict, patient: Patient, created: datetime | None, channel: str) -> Encounter:
    created = created or now()
    history = list(
        db.scalars(select(Encounter).where(Encounter.patient_id == patient.id).order_by(Encounter.created_at.desc()))
    )
    files = [f for f in (db.get(FileObject, fid) for fid in intake.get("file_ids", [])) if f]
    if labs := lab_values([f.extraction for f in files if f.extraction]):
        intake = {**intake, "lab_values": labs}  # read from uploaded reports; rules may only raise urgency
    triage = evaluate_full(intake, patient.age, patient.sex)
    urgency = triage["urgency"]
    consent = db.get(Consent, intake["consent_id"]) if intake.get("consent_id") else None
    note = build_note(intake=intake, patient=patient, triage=triage, files=files, history=history, proxy=bool(consent and consent.mode == "proxy"))
    specialist = infer_specialist(intake, patient.age, triage)
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
        channel=channel,
    )
    day = local_day(now())
    enc.token_date = day
    enc.token = next_token(db, intake["facility_id"], day)
    db.add(enc)
    db.flush()
    for f in files:
        f.encounter_id = enc.id
    return enc


def record_observations(db: Session, e: Encounter, user: User, vitals: dict, note: str, signs: list[str] | None = None, exam_done: bool = False) -> None:
    """Bedside vitals / observations from a nurse or doctor. The note is rebuilt from the updated intake and the
    deterministic rules run again, so new vitals (e.g. SpO2 88%) or a danger sign can raise urgency, and a completed
    danger-sign check can release a provisional case. A doctor's override is kept."""
    intake = dict(e.intake or {})
    if vitals:
        intake["vitals"] = {**(intake.get("vitals") or {}), **vitals}
    if signs is not None or exam_done:
        prev = intake.get("exam") or {}
        intake["exam"] = {
            "done": bool(exam_done or prev.get("done")),
            "signs": sorted(set(prev.get("signs") or []) | set(signs or [])),
            "by": f"{user.name} ({user.role})",
            "at": now().isoformat(),
        }
    files = [f for f in (db.get(FileObject, fid) for fid in intake.get("file_ids", [])) if f]
    if labs := lab_values([f.extraction for f in files if f.extraction]):
        intake["lab_values"] = labs
    e.intake = intake
    triage = evaluate_full(intake, e.patient.age, e.patient.sex)
    urgency = triage["urgency"]
    history = [x for x in db.scalars(select(Encounter).where(Encounter.patient_id == e.patient_id).order_by(Encounter.created_at.desc())) if x.id != e.id]
    consent = db.get(Consent, intake["consent_id"]) if intake.get("consent_id") else None
    old = dict(e.note or {})
    new = build_note(intake=intake, patient=e.patient, triage=triage, files=files, history=history, proxy=bool(consent and consent.mode == "proxy"))
    if old.get("edited_by"):  # keep what a clinician wrote by hand
        new.update({k: old[k] for k in ("summary", "missing_info", "edited_by", "edited_at") if k in old})
    obs = list(old.get("observations") or [])
    obs.append({"by": user.name, "role": user.role, "at": now().isoformat(), "vitals": vitals, "note": note or None,
                "signs": signs or [], "exam_done": exam_done})
    new["observations"] = obs
    e.note = new
    e.rules_urgency = urgency
    if e.urgency_source == "rules" and urgency != e.urgency:
        e.urgency = urgency
        esc = escalate_after(urgency)
        e.escalation_due_at = aware(e.created_at) + timedelta(minutes=esc) if esc else None


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
        token=e.token,
        channel=e.channel,
        worker=_worker_info(e) if viewer.role not in ("patient", "kiosk") else None,
        consent=ConsentOut.model_validate(e.consent) if e.consent else None,
    )
    if viewer.role in ("patient", "kiosk"):
        # Health outputs stay reviewer-facing: no urgency, no AI note, no override.
        out.urgency = None
        out.note = None
        out.override = None
        out.escalation_due_at = None
        out.specialist_required = None
        out.referral_needed = None
    return out


def _worker_info(e: Encounter) -> WorkerInfo | None:
    p = e.patient
    if not p.organisation_id:
        return None
    from sqlalchemy.orm import object_session

    from .models import FitnessAssessment, Organisation

    db = object_session(e)
    org = db.get(Organisation, p.organisation_id) if db else None
    latest = db.scalar(select(FitnessAssessment).where(FitnessAssessment.patient_id == p.id).order_by(FitnessAssessment.assessed_at.desc()).limit(1)) if db else None
    return WorkerInfo(
        organisation_id=p.organisation_id, organisation_name=org.name if org else "", employee_code=p.employee_code, department=p.department,
        latest=FitnessOut.model_validate(latest) if latest else None,
    )


def load_encounter(db: Session, eid: str, user: User, *, clinical: bool = True) -> Encounter:
    if clinical and (user.role in ADMIN_ROLES or user.role in ("employer", "kiosk")):
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
