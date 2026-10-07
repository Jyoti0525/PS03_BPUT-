"""Domain logic shared by routers and the seed script."""

import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit, regions
from .config import get_settings
from .models import Consent, Encounter, Escalation, Facility, FileObject, Patient, User
from .schemas import ADMIN_ROLES, DOCTOR_ROLES, SIGN_OFF, ConsentOut, EncounterOut, FitnessOut, PatientOut, WorkerInfo
from .triage.pipeline import build_note, infer_specialist, questions_for
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


def waiting_since(e: Encounter) -> datetime:
    """Waiting counts from arrival at the facility, not from when the form was sent (C3): filling it in at home at 6 am
    must not move anyone ahead of people already standing in the OPD."""
    return aware(e.arrived_at or e.created_at)


def wait_minutes(e: Encounter, t: datetime | None = None) -> int:
    return max(0, round(((t or now()) - waiting_since(e)).total_seconds() / 60))


def next_patient_code(db: Session) -> str:
    n = db.scalar(select(func.count(Patient.id))) or 0
    while True:
        n += 1
        code = f"JVA-P{n:03d}"
        if not db.scalar(select(Patient.id).where(Patient.code == code)):
            return code


_token_lock = threading.Lock()


def local_day(d: datetime) -> str:
    return d.astimezone(ZoneInfo(get_settings().timezone)).date().isoformat()


def calendar_context(facility: Facility | None, when: datetime) -> dict:
    """The facility's regional calendar (F5) and the visit's local date, for dating "since Diwali" onsets."""
    return {"calendar": regions.for_facility(facility), "on": aware(when).astimezone(ZoneInfo(get_settings().timezone)).date()}


def next_token(db: Session, facility_id: str, day: str, prefix: str = "T") -> str:
    """Daily running number per facility: T-001, T-002 … (resets at local midnight). An intake sent from home gets an
    H- reference; its T- token is issued when the desk checks the patient in, so the token order is the arrival order."""
    n = db.scalar(select(func.count(Encounter.id)).where(Encounter.facility_id == facility_id, Encounter.token_date == day,
                                                         Encounter.token.like(f"{prefix}-%"))) or 0
    return f"{prefix}-{n + 1:03d}"


def with_fev1_baseline(intake: dict, history: list[Encounter]) -> dict:
    """D2: a worker's FEV1 is compared with their own earliest recorded value (ATS 2014), taken from earlier screenings."""
    occ = intake.get("occupational") or {}
    if not occ.get("fev1_l"):
        return intake
    earlier = [(e.created_at, (e.intake or {}).get("occupational") or {}) for e in history]
    earlier = sorted((t, o) for t, o in earlier if o.get("fev1_l"))
    if not earlier:
        return intake
    t, o = earlier[0]
    return {**intake, "occupational": {**occ, "fev1_baseline_l": o["fev1_l"], "fev1_baseline_on": aware(t).date().isoformat()}}


def can_confirm(role: str, urgency: str | None) -> bool:
    """Sign-off limit (E2): a health worker may confirm GREEN, a nurse up to YELLOW, a doctor or medical officer any tier."""
    rank = {"green": 0, "yellow": 1, "red": 2}
    limit = SIGN_OFF.get(role)
    return limit is not None and urgency in rank and rank[urgency] <= rank[limit]


def sign_off_role(urgency: str | None) -> str:
    return {"green": "health_worker", "yellow": "nurse"}.get(urgency or "", "doctor")


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
    intake = with_fev1_baseline(intake, history)
    triage = evaluate_full(intake, patient.age, patient.sex)
    urgency = triage["urgency"]
    consent = db.get(Consent, intake["consent_id"]) if intake.get("consent_id") else None
    facility = db.get(Facility, intake["facility_id"])
    note = build_note(intake=intake, patient=patient, triage=triage, files=files, history=history, proxy=bool(consent and consent.mode == "proxy"),
                      **calendar_context(facility, created))
    specialist = infer_specialist(intake, patient.age, triage)
    on_site = any(s["key"] == specialist and s["available"] for s in (facility.specialists if facility else []))
    # From home: not in the queue until the desk checks the patient in. A RED is the exception: the patient is told to
    # go to emergency or call 108, and the case is shown to the doctors now so someone can call back.
    expected = channel == "home_link" and urgency != "red"
    esc = None if expected else escalate_after(urgency)
    enc = Encounter(
        patient_id=patient.id,
        facility_id=intake["facility_id"],
        category=intake["category"],
        status="expected" if expected else "queued",
        chief_complaint=intake["chief_complaint"],
        created_at=created,
        arrived_at=None if channel == "home_link" else created,
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
    enc.token = next_token(db, intake["facility_id"], day, "H" if expected else "T")
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
    history = [x for x in db.scalars(select(Encounter).where(Encounter.patient_id == e.patient_id).order_by(Encounter.created_at.desc())) if x.id != e.id]
    intake = with_fev1_baseline(intake, history)
    e.intake = intake
    triage = evaluate_full(intake, e.patient.age, e.patient.sex)
    urgency = triage["urgency"]
    consent = db.get(Consent, intake["consent_id"]) if intake.get("consent_id") else None
    old = dict(e.note or {})
    new = build_note(intake=intake, patient=e.patient, triage=triage, files=files, history=history, proxy=bool(consent and consent.mode == "proxy"),
                     **calendar_context(db.get(Facility, e.facility_id), e.created_at))
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
        e.escalation_due_at = (waiting_since(e) + timedelta(minutes=esc) if esc else None) if e.status != "expected" else None


def check_in(db: Session, e: Encounter, user: User) -> None:
    """The patient who filled in the form from home is at the desk: they join the queue now, with a token for today,
    and their waiting time and escalation timer start from this moment."""
    t = now()
    e.arrived_at = t
    e.status = "queued"
    day = local_day(t)
    if e.token_date != day or not (e.token or "").startswith("T-"):
        with _token_lock:
            e.token_date = day
            e.token = next_token(db, e.facility_id, day)
    esc = escalate_after(e.urgency)
    e.escalation_due_at = t + timedelta(minutes=esc) if esc else None


def lapse_expected(db: Session, facility_id: str) -> int:
    """Intakes from home whose patient never came: after the validity window they leave the expected list."""
    cutoff = now() - timedelta(hours=get_settings().home_intake_valid_h)
    rows = [e for e in db.scalars(select(Encounter).where(Encounter.facility_id == facility_id, Encounter.status == "expected"))
            if aware(e.created_at) < cutoff]
    for e in rows:
        e.status = "lapsed"
    if rows:
        db.commit()
    return len(rows)


def home_advice(e: Encounter) -> str | None:
    """What the patient who filled in from home is told. Never a tier: either a danger sign was reported and they go to
    emergency now, or they bring their reference to the desk."""
    if e.channel != "home_link":
        return None
    return "emergency" if e.urgency == "red" else "show_at_desk"


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
        arrived_at=aware(e.arrived_at),
        data_origin=e.data_origin or "SYNTHETIC",
        home_advice=home_advice(e),
        worker=_worker_info(e) if viewer.role != "kiosk" else None,
        consent=ConsentOut.model_validate(e.consent) if e.consent else None,
        can_confirm=can_confirm(viewer.role, e.urgency),
        sign_off=sign_off_role(e.urgency),
    )
    if out.note and viewer.role != "kiosk":
        out.note = note_for(out.note, viewer.role)
    if viewer.role == "kiosk":
        # Health outputs stay reviewer-facing: no urgency, no AI note, no override.
        out.urgency = None
        out.note = None
        out.override = None
        out.escalation_due_at = None
        out.specialist_required = None
        out.referral_needed = None
    return out


HW_NOTE_KEYS = ("summary", "flags", "missing_info", "followup_questions", "vitals", "generated_by", "renderer", "ai_assist", "generated_at", "observations")


def note_for(note: dict, role: str) -> dict:
    """Note density by role (E2/B7). A health worker gets the short form: summary, flags, what is missing, their own
    questions and vital signs; the rule trace, labs and documents stay with the nurse, doctor and medical officer."""
    note = {**note, "followup_questions": questions_for(note.get("followup_questions") or [], role)}
    if role == "health_worker":
        t = note.get("triage") or {}
        note = {k: note[k] for k in HW_NOTE_KEYS if k in note}
        note["triage"] = {"urgency": t.get("urgency"), "provisional": t.get("provisional"), "missing_for_green": t.get("missing_for_green") or []}
        note["detail_level"] = "summary"
    else:
        note["detail_level"] = "full"
    return note


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
    if user.facility_id and e.facility_id != user.facility_id:
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


def summarise_later(encounter_id: str) -> None:
    """Ask the local language model for a readable summary in the background (B5), so intake is never slowed.
    The template note is already saved; this replaces its summary only if the model's text passes every check. A note
    rebuilt meanwhile (new vitals) or edited by a clinician is left alone."""
    if not get_settings().llm_url:
        return

    def run():
        from . import llm
        from .db import SessionLocal

        with SessionLocal() as db:
            e = db.get(Encounter, encounter_id)
            if not e or not e.note or e.note.get("edited_by"):
                return
            stamp = e.note.get("generated_at")
            note = llm.apply(e.note, e.intake or {}, e.patient)
            db.refresh(e)
            if not e.note or e.note.get("generated_at") != stamp or e.note.get("edited_by"):
                return
            e.note = note
            r = note.get("llm") or {}
            if r.get("status") == "FAIL_FELL_BACK":
                why = "; ".join(r["guard"] + r["faithfulness"])
                audit.record(db, None, "GUARD_BLOCK", "encounter", e.id, f'AI summary rejected ({why}). Rejected text: "{r["rejected_text"][:600]}"', e.patient.code, e.facility_id)
            elif r.get("status") == "PASS":
                audit.record(db, None, "UPDATE", "encounter", e.id, f"Summary written by {r['model']} in {r['ms']} ms; faithfulness and output guard passed", e.patient.code, e.facility_id)
            op = note.get("llm_opinion") or {}
            if op.get("status") == "DISAGREE":
                audit.record(db, None, "UPDATE", "encounter", e.id,
                             f"AI second opinion {op['model_urgency'].upper()} differs from the rules' {op['rules_urgency'].upper()} ({op['direction']}); "
                             f"urgency unchanged{'. Reason withheld by the checks' if op.get('reason_withheld') else ''}", e.patient.code, e.facility_id)
            db.commit()

    threading.Thread(target=run, name=f"summary-{encounter_id}", daemon=True).start()
