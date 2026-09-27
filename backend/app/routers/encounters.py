"""Intake submission, triage queue, review actions (confirm / edit / override), escalation,
referral and export (E1–E7)."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import audit, exports
from ..config import get_settings
from ..models import Device, Encounter, Escalation, Facility, FitnessAssessment, Patient, Referral, Reminder, User
from ..schemas import (
    REVIEWER_ROLES,
    AckIn,
    EncounterOut,
    EncounterPatch,
    EscalationIn,
    EscalationOut,
    ExportFormat,
    FitnessIn,
    FitnessOut,
    IntakeIn,
    NotePatch,
    OverrideIn,
    QueueItem,
    ReferralIn,
    ReferralOut,
)
from ..security import DB, CurrentUser, DeviceHeader, require
from ..services import auto_escalate, create_encounter, encounter_out, escalate_after, load_encounter, now, own_patient
from .facilities import get_facility

router = APIRouter(tags=["encounters"])
Reviewer = Annotated[User, Depends(require(*REVIEWER_ROLES))]
Doctor = Annotated[User, Depends(require("doctor"))]
RANK = {"red": 0, "yellow": 1, "green": 2}


@router.post("/encounters", response_model=EncounterOut)
def submit_intake(body: IntakeIn, user: CurrentUser, db: DB, device_id: DeviceHeader = None):
    if user.role not in ("nurse", "doctor", "receptionist", "supervisor", "patient", "kiosk"):
        raise HTTPException(403, "Not allowed")
    dup = db.scalar(select(Encounter).where(Encounter.client_ref == body.client_ref))
    if dup:
        return encounter_out(dup, user)  # idempotent offline replay
    p = db.get(Patient, body.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    if not db.get(Facility, body.facility_id):
        raise HTTPException(422, "Unknown facility")
    if user.role == "patient":
        mine = own_patient(db, user)
        if not mine or mine.id != p.id:
            raise HTTPException(403, "Patients can only submit their own intake")
    else:
        if body.facility_id != user.facility_id:
            raise HTTPException(403, "Intakes can only be submitted for your own facility")
        if user.role != "kiosk" and get_settings().require_bound_device:
            dev = db.get(Device, device_id) if device_id else None
            if not dev or dev.revoked or dev.facility_id != user.facility_id:
                raise HTTPException(403, "This device is not bound to your facility — bind it from the kiosk screen")
            dev.last_seen_at = now()
    if not body.consent_id:
        raise HTTPException(422, "Consent must be captured before intake")
    intake = body.model_dump(mode="json")
    captured = body.captured_at if body.captured_at and body.captured_at < now() else None
    try:
        channel = {"kiosk": "kiosk_link", "patient": "patient_app"}.get(user.role, "staff_kiosk")
        enc = create_encounter(db, intake, p, captured, channel)
    except IntegrityError:
        db.rollback()
        dup = db.scalar(select(Encounter).where(Encounter.client_ref == body.client_ref))
        return encounter_out(dup, user)
    m = body.maternal
    if m and m.next_checkup and m.reminder_channel != "none":
        try:
            from datetime import datetime, timezone

            due = datetime.fromisoformat(m.next_checkup).replace(tzinfo=timezone.utc)
            db.add(Reminder(patient_id=p.id, kind="anc_checkup", due_at=due, channel=m.reminder_channel or "sms", message=f"ANC check-up reminder for {p.name}"))
        except ValueError:
            pass
    audit.record(db, user, "CREATE", "encounter", enc.id, f"Intake submitted{' (offline, synced)' if body.captured_offline else ''}; rules engine: {enc.urgency}", p.code, enc.facility_id)
    if enc.note and enc.note["disagreements"]:
        detail = "; ".join(f"{d['field']}: " + " vs ".join(v["value"] for v in d["values"]) for d in enc.note["disagreements"])
        audit.record(db, None, "DISAGREEMENT", "encounter", enc.id, detail, p.code, enc.facility_id)
    db.commit()
    return encounter_out(enc, user)


@router.get("/queue", response_model=list[QueueItem])
def queue(user: Reviewer, db: DB, facility_id: str = Query(...)):
    if facility_id != user.facility_id:
        raise HTTPException(403, "You can only view your own facility's queue")
    auto_escalate(db)
    rows = db.scalars(select(Encounter).where(Encounter.facility_id == facility_id, Encounter.status.in_(("queued", "in_review", "escalated"))))
    t = now()
    items = []
    for e in rows:
        n = e.note or {}
        items.append(
            QueueItem(
                encounter_id=e.id,
                token=e.token,
                channel=e.channel,
                patient_code=e.patient.code,
                patient_name=e.patient.name,
                age=e.patient.age,
                sex=e.patient.sex,
                category=e.category,
                chief_complaint=e.chief_complaint,
                urgency=e.urgency,
                status=e.status,
                created_at=e.created_at,
                wait_minutes=max(0, round((t - e.created_at).total_seconds() / 60)),
                flag_count=sum(1 for f in n.get("flags", []) if f["severity"] != "info"),
                needs_check_count=sum(1 for v in [*n.get("vitals", []), *n.get("labs", [])] if v.get("needs_check")),
                language=e.patient.language,
                escalation_due_at=e.escalation_due_at,
            )
        )
    return sorted(items, key=lambda i: (RANK[i.urgency], -i.wait_minutes))


@router.get("/encounters/{eid}", response_model=EncounterOut)
def get_encounter(eid: str, user: CurrentUser, db: DB):
    e = load_encounter(db, eid, user)
    if e.status == "queued" and user.role in REVIEWER_ROLES:
        e.status = "in_review"
    audit.record(db, user, "VIEW", "encounter", eid, "Triage note viewed", e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.patch("/encounters/{eid}", response_model=EncounterOut)
def patch_encounter(eid: str, body: EncounterPatch, user: Reviewer, db: DB):
    e = load_encounter(db, eid, user)
    if body.referral_needed is not None:
        e.referral_needed = body.referral_needed
        audit.record(db, user, "UPDATE", "encounter", eid, f"Referral needed: {'yes' if body.referral_needed else 'no'}", e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.post("/encounters/{eid}/confirm", response_model=EncounterOut)
def confirm(eid: str, user: Doctor, db: DB):
    e = load_encounter(db, eid, user)
    e.status, e.reviewed_by, e.reviewed_at = "confirmed", user.name, now()
    audit.record(db, user, "CONFIRM", "encounter", eid, "Triage note reviewed and confirmed", e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.patch("/encounters/{eid}/note", response_model=EncounterOut)
def edit_note(eid: str, body: NotePatch, user: Reviewer, db: DB):
    e = load_encounter(db, eid, user)
    if not e.note:
        raise HTTPException(404, "No note")
    patch = body.model_dump(exclude_none=True)
    e.note = {**e.note, **patch, "edited_by": user.name, "edited_at": now().isoformat()}
    audit.record(db, user, "UPDATE", "encounter", eid, f"Note edited: {', '.join(patch) or 'nothing'}", e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.post("/encounters/{eid}/override", response_model=EncounterOut)
def override(eid: str, body: OverrideIn, user: Doctor, db: DB):
    """Human-in-the-loop override. The rules-engine output stays in `rules_urgency`; a written reason is mandatory."""
    e = load_encounter(db, eid, user)
    frm = e.urgency
    e.override = {"from_urgency": frm, "to_urgency": body.to_urgency, "category": body.category, "reason": body.reason, "by": user.name, "at": now().isoformat()}
    e.urgency = body.to_urgency
    e.urgency_source = "override"
    esc = escalate_after(body.to_urgency)
    e.escalation_due_at = e.created_at + timedelta(minutes=esc) if esc else None
    audit.record(db, user, "OVERRIDE", "encounter", eid, f'Urgency {frm} → {body.to_urgency} ({body.category}). Reason: "{body.reason}". Rules-engine output ({e.rules_urgency}) retained.', e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.get("/encounters/{eid}/export")
def export(eid: str, user: Reviewer, db: DB, format: ExportFormat = "pdf"):
    e = load_encounter(db, eid, user)
    data = encounter_out(e, user).model_dump(mode="json")
    fac = get_facility(e.facility_id, db)
    body, mime, name = exports.build(data, format, {"name": fac.name, "district": fac.district, "state": fac.state})
    audit.record(db, user, "EXPORT", "encounter", eid, f"Triage note exported as {format.upper()}", e.patient.code, e.facility_id)
    disp = "inline" if format == "print" else "attachment"
    return Response(body, media_type=mime, headers={"Content-Disposition": f'{disp}; filename="{name}"'})


@router.post("/encounters/{eid}/fitness", response_model=FitnessOut)
def record_fitness(eid: str, body: FitnessIn, user: Doctor, db: DB):
    """Occupational fitness outcome for a worker. The employer sees this outcome only."""
    e = load_encounter(db, eid, user)
    if not e.patient.organisation_id:
        raise HTTPException(422, "This patient is not on an employer's roster")
    a = FitnessAssessment(
        patient_id=e.patient_id, organisation_id=e.patient.organisation_id, encounter_id=e.id, status=body.status,
        restrictions=(body.restrictions or "").strip() or None, valid_until=body.valid_until, assessed_by=user.name, assessed_by_id=user.id,
    )
    db.add(a)
    db.flush()
    audit.record(db, user, "UPDATE", "fitness", a.id, f"Fitness recorded: {body.status}{' until ' + body.valid_until if body.valid_until else ''}", e.patient.code, e.facility_id)
    db.refresh(a)
    return a


# ── Escalations ───────────────────────────────────────
def esc_out(x: Escalation) -> EscalationOut:
    return EscalationOut(
        id=x.id, encounter_id=x.encounter_id, patient_name=x.encounter.patient.name, urgency=x.encounter.urgency,
        raised_by=x.raised_by, raised_at=x.raised_at, to_role=x.to_role, reason=x.reason, auto=x.auto, status=x.status,
        acknowledged_by=x.acknowledged_by, acknowledged_at=x.acknowledged_at, ack_note=x.ack_note,
    )


@router.post("/encounters/{eid}/escalations", response_model=EscalationOut)
def escalate(eid: str, body: EscalationIn, user: Reviewer, db: DB):
    e = load_encounter(db, eid, user)
    x = Escalation(encounter_id=e.id, raised_by=user.name, to_role=body.to_role, reason=body.reason.strip())
    db.add(x)
    e.status = "escalated"
    db.flush()
    audit.record(db, user, "ESCALATE", "encounter", e.id, f"Escalated to {body.to_role}: {body.reason.strip()}", e.patient.code, e.facility_id)
    db.refresh(x)
    return esc_out(x)


@router.get("/escalations", response_model=list[EscalationOut])
def list_escalations(user: Reviewer, db: DB, status: str | None = None):
    auto_escalate(db)
    q = select(Escalation).join(Encounter).where(Encounter.facility_id == user.facility_id).order_by(Escalation.raised_at.desc())
    if status:
        q = q.where(Escalation.status == status)
    return [esc_out(x) for x in db.scalars(q).unique()]


@router.post("/escalations/{xid}/acknowledge", response_model=EscalationOut)
def acknowledge(xid: str, body: AckIn, user: Doctor, db: DB):
    x = db.get(Escalation, xid)
    if not x or x.encounter.facility_id != user.facility_id:
        raise HTTPException(404, "Escalation not found")
    x.status, x.acknowledged_by, x.acknowledged_at, x.ack_note = "acknowledged", user.name, now(), body.note or None
    if x.encounter.status == "escalated":
        x.encounter.status = "in_review"
    audit.record(db, user, "ACKNOWLEDGE", "escalation", xid, f"Escalation acknowledged{': ' + body.note if body.note else ''}", x.encounter.patient.code, user.facility_id)
    return esc_out(x)


# ── Referrals ─────────────────────────────────────────
def ref_out(r: Referral) -> ReferralOut:
    return ReferralOut(
        id=r.id, encounter_id=r.encounter_id, patient_name=r.encounter.patient.name, destination=r.destination, specialty=r.specialty,
        reason=r.reason, note_text=r.note_text, transport=r.transport, created_by=r.created_by, created_at=r.created_at, status=r.status,
    )


@router.post("/encounters/{eid}/referrals", response_model=ReferralOut)
def create_referral(eid: str, body: ReferralIn, user: Doctor, db: DB):
    e = load_encounter(db, eid, user)
    r = Referral(encounter_id=e.id, created_by=user.name, **body.model_dump())
    db.add(r)
    e.status, e.referral_needed = "referred", True
    e.reviewed_by = e.reviewed_by or user.name
    e.reviewed_at = e.reviewed_at or now()
    db.flush()
    audit.record(db, user, "REFERRAL", "encounter", e.id, f"Referral to {body.destination} ({body.specialty}); transport: {body.transport}", e.patient.code, e.facility_id)
    db.refresh(r)
    return ref_out(r)


@router.get("/referrals", response_model=list[ReferralOut])
def list_referrals(user: Reviewer, db: DB):
    q = select(Referral).join(Encounter).where(Encounter.facility_id == user.facility_id).order_by(Referral.created_at.desc())
    return [ref_out(r) for r in db.scalars(q).unique()]
