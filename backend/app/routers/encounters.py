"""Intake submission, triage queue, review actions (confirm / edit / override), escalation,
referral and export (E1–E7)."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import alerts, audit, exports, language, privacy
from ..config import get_settings
from ..models import Consent, Device, Encounter, FileObject, Escalation, Facility, FitnessAssessment, KioskLink, Patient, Referral, Reminder, User
from ..schemas import (
    ClaimIn,
    DOCTOR_ROLES,
    NO_AI_SCOPE,
    REVIEWER_ROLES,
    STAFF_ROLES,
    AckIn,
    EncounterOut,
    EncounterPatch,
    EscalationIn,
    EscalationOut,
    ExportFormat,
    FitnessIn,
    FitnessOut,
    IntakeIn,
    MedicationReview,
    NotePatch,
    ObservationIn,
    OverrideIn,
    QueueItem,
    ReferralIn,
    ReferralReceivedIn,
    ReferralOut,
)
from ..security import DB, CurrentUser, DeviceHeader, require
from ..triage.findings import FINDINGS
from ..services import (auto_escalate, aware, can_confirm, check_in, create_encounter, encounter_out, escalate_after, load_encounter, now, record_observations, sign_off_role,
                        summarise_later, wait_minutes)
from .facilities import get_facility

router = APIRouter(tags=["encounters"])
Reviewer = Annotated[User, Depends(require(*REVIEWER_ROLES))]
Doctor = Annotated[User, Depends(require(*DOCTOR_ROLES))]  # doctor or medical officer
Clinician = Annotated[User, Depends(require("nurse", *DOCTOR_ROLES))]
Staff = Annotated[User, Depends(require(*STAFF_ROLES))]
RANK = {"red": 0, "yellow": 1, "green": 2}


@router.post("/encounters", response_model=EncounterOut)
def submit_intake(body: IntakeIn, user: CurrentUser, db: DB, device_id: DeviceHeader = None):
    if user.role not in ("nurse", "doctor", "medical_officer", "health_worker", "receptionist", "supervisor", "kiosk"):
        raise HTTPException(403, "Not allowed")
    dup = db.scalar(select(Encounter).where(Encounter.client_ref == body.client_ref))
    if dup:
        return encounter_out(dup, user)  # idempotent offline replay
    p = db.get(Patient, body.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    if not db.get(Facility, body.facility_id):
        raise HTTPException(422, "Unknown facility")
    for prog in (body.maternal, body.chronic):
        w = db.get(User, prog.assigned_worker_id) if prog and prog.assigned_worker_id else None
        if prog and prog.assigned_worker_id and (not w or w.role != "health_worker" or w.facility_id != body.facility_id or not w.is_active):
            raise HTTPException(422, "The assigned worker must be an active health worker (ASHA / ANM) at this facility")
    if body.facility_id != user.facility_id:
        raise HTTPException(403, "Intakes can only be submitted for your own facility")
    if user.role != "kiosk" and get_settings().require_bound_device:
        dev = db.get(Device, device_id) if device_id else None
        if not dev or dev.revoked or dev.facility_id != user.facility_id:
            raise HTTPException(403, "This device is not bound to your facility — bind it from the kiosk screen")
        dev.last_seen_at = now()
    if not body.consent_id:
        raise HTTPException(422, "Consent must be captured before intake")
    # Identifiers are scrubbed from free text before anything is stored or sent to a model (G3); the placeholders
    # survive translation. Then free text in the patient's language gets an English rendering (offline IndicTrans2),
    # which is scrubbed again for names that only appear in Latin script.
    consent = db.get(Consent, body.consent_id)
    if not consent or consent.patient_id != p.id:
        raise HTTPException(422, "Consent does not belong to this patient")
    # "Continue without AI" (G1): no speech, translation or report-reading model touches this intake.
    ai = NO_AI_SCOPE not in (consent.scopes or [])
    if not ai and any(s.source == "voice" for s in body.symptoms):
        raise HTTPException(422, "Voice entries need speech recognition, which the patient declined — type or tap instead")
    names = [p.name] + ([consent.proxy_name] if consent.proxy_name else [])
    intake, removed = privacy.anonymise_intake(body.model_dump(mode="json"), names)
    intake["ai_assist"] = ai
    if ai:
        intake, removed_en = privacy.anonymise_intake(language.translate_symptoms(intake), names)
    else:
        removed_en = {}
        for f in (db.get(FileObject, fid) for fid in body.file_ids):
            if f and f.extraction and f.uploaded_by == user.id:
                f.extraction = None  # read before the patient chose no AI: discarded, staff view the image itself
    for k, n in removed_en.items():
        removed[k] = removed.get(k, 0) + n
    if removed:
        intake["redactions"] = removed
    captured = body.captured_at if body.captured_at and body.captured_at < now() else None
    try:
        link = db.scalar(select(KioskLink).where(KioskLink.user_id == user.id)) if user.role == "kiosk" else None
        channel = "staff_kiosk" if not link else "home_link" if link.for_home else "kiosk_link"
        enc = create_encounter(db, intake, p, captured, channel)
    except IntegrityError:
        db.rollback()
        dup = db.scalar(select(Encounter).where(Encounter.client_ref == body.client_ref))
        return encounter_out(dup, user)
    m = body.maternal
    if body.category == "maternal" or m:
        alerts.close_on_visit(db, p.id, user)  # she came: earlier check-up reminders are done
    if body.category == "chronic" or body.chronic:
        alerts.close_on_visit(db, p.id, user, kind="chronic_checkin")
    fac = db.get(Facility, enc.facility_id)
    if m and m.next_checkup:
        due = _visit_day(fac, "anc_checkup", _date(m.next_checkup))
        if due:
            # D4: the reminder always exists so a missed visit is noticed; the channel only decides whether a message goes
            # out, and a phone that is not hers gets wording that says nothing about pregnancy.
            owner = m.phone_belongs_to or ("none" if not p.phone else None)
            db.add(Reminder(patient_id=p.id, kind="anc_checkup", due_at=due, channel=m.reminder_channel or "sms", facility_id=enc.facility_id,
                            assigned_to=m.assigned_worker_id, phone_belongs_to=owner, encounter_id=enc.id,
                            message=alerts.reminder_message(p, alerts.facility_name(db, enc.facility_id), due, owner)))
    c = body.chronic
    if c and c.next_checkup and (due := _visit_day(fac, "chronic_checkin", _date(c.next_checkup))):
        # E5: the next check-in for a long-term condition. Missed → the assigned health worker, then a reminder call.
        owner = "self" if p.phone else "none"
        db.add(Reminder(patient_id=p.id, kind="chronic_checkin", due_at=due, channel="voice" if p.phone else "none", facility_id=enc.facility_id,
                        assigned_to=c.assigned_worker_id, phone_belongs_to=owner, encounter_id=enc.id,
                        message=alerts.reminder_message(p, alerts.facility_name(db, enc.facility_id), due, owner, kind="chronic_checkin")))
    audit.record(db, user, "CREATE", "encounter", enc.id, f"Intake submitted{' (offline, synced)' if body.captured_offline else ''}; rules engine: {enc.urgency}", p.code, enc.facility_id)
    if removed:
        audit.record(db, user, "REDACT", "encounter", enc.id, f"Removed from free text before storage: {privacy.describe(removed)}", p.code, enc.facility_id)
    if enc.note and enc.note["disagreements"]:
        detail = "; ".join(f"{d['field']}: " + " vs ".join(v["value"] for v in d["values"]) for d in enc.note["disagreements"])
        audit.record(db, None, "DISAGREEMENT", "encounter", enc.id, detail, p.code, enc.facility_id)
    db.commit()
    alerts.check_fever_cluster(db, enc.facility_id, alerts.cluster_of(enc))
    if enc.urgency == "red":
        alerts.check_capacity(db, enc.facility_id)
    db.commit()
    if enc.intake.get("ai_assist", True):
        summarise_later(enc.id)
    return encounter_out(enc, user)


def _visit_day(fac, kind: str, when):
    """E5: a follow-up date lands on the facility's next clinic day for that kind of visit."""
    from .. import visits

    if when is None or fac is None or when < now():  # a date already past is a record, not a booking: kept as given
        return when
    d, _ = visits.snap(fac, kind, when.date())
    return when.replace(year=d.year, month=d.month, day=d.day)


def _date(s: str):
    from datetime import datetime, timezone

    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@router.get("/queue", response_model=list[QueueItem])
def queue(user: Reviewer, db: DB, facility_id: str = Query(...)):
    if facility_id != user.facility_id:
        raise HTTPException(403, "You can only view your own facility's queue")
    auto_escalate(db)
    rows = list(db.scalars(select(Encounter).where(Encounter.facility_id == facility_id, Encounter.status.in_(("queued", "in_review", "escalated")))))
    alerts.check_capacity(db, facility_id)
    long_wait = alerts.check_long_wait(db, facility_id)
    t = now()
    wait = {e.id: wait_minutes(e, t) for e in rows}
    why = alerts.order_reasons([{"id": e.id, "urgency": e.urgency, "wait": wait[e.id], "why": alerts.why_tier(e), "escalated": e.status == "escalated",
                                 "long_wait": e.id in long_wait, "from_home": e.channel == "home_link"} for e in rows])
    items = []
    for e in rows:
        n = e.note or {}
        raised = sorted((f for f in n.get("flags", []) if f["severity"] != "info"), key=lambda f: f["severity"] != "critical")
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
                arrived_at=e.arrived_at,
                wait_minutes=wait[e.id],
                flag_count=len(raised),
                top_flags=[f["label"] for f in raised[:2]],
                needs_check_count=sum(1 for v in [*n.get("vitals", []), *n.get("labs", [])] if v.get("needs_check")),
                language=e.patient.language,
                escalation_due_at=e.escalation_due_at,
                vitals_recorded=bool(n.get("vitals")),
                observation_count=len(n.get("observations") or []),
                order_reason=why[e.id],
                sign_off=sign_off_role(e.urgency),
            )
        )
    # C3: tier, then escalation state, then minutes waiting since arrival (plan, "Queue ordering")
    return sorted(items, key=lambda i: (RANK[i.urgency], i.status != "escalated", -i.wait_minutes))


@router.post("/encounters/{eid}/arrive", response_model=EncounterOut)
def arrive(eid: str, user: Staff, db: DB):
    """The desk checks in a patient who filled in the form from home: they join the queue from now."""
    e = db.get(Encounter, eid)
    if not e or e.facility_id != user.facility_id:
        raise HTTPException(404, "Not found")
    if e.status != "expected":
        raise HTTPException(409, "Already checked in" if e.arrived_at else f"This intake is {e.status}")
    check_in(db, e, user)
    audit.record(db, user, "ARRIVE", "encounter", e.id, f"Checked in at the desk (filled in from home); token {e.token}", e.patient.code, e.facility_id)
    db.commit()
    if e.urgency == "red":
        alerts.check_capacity(db, e.facility_id)
    return encounter_out(e, user)


@router.post("/encounters/claim", response_model=EncounterOut)
def claim(body: ClaimIn, user: Staff, db: DB):
    """A patient brings the reference (or QR) of a form filled in "for any centre": it moves to this facility and the
    patient joins its queue now, with a token for today. The note, rules and files come with it."""
    from ..services import ANY_FACILITY

    ref = body.reference.strip().upper().removeprefix("JEEVIA:")
    digits = "".join(c for c in ref if c.isdigit())
    if len(digits) >= 10 and not any(c.isalpha() for c in ref):
        # The patient lost the reference: their latest unclaimed form, found by the mobile number they gave.
        from ..crypto import blind

        since = now() - timedelta(hours=get_settings().home_intake_valid_h)
        e = db.scalar(select(Encounter).join(Patient, Encounter.patient_id == Patient.id)
                      .where(Patient.phone_hash == blind(digits[-10:]), Encounter.facility_id == ANY_FACILITY, Encounter.status == "expected", Encounter.created_at >= since)
                      .order_by(Encounter.created_at.desc()).limit(1))
        if not e:
            raise HTTPException(404, "No open form for this mobile number. Check the number, or fill in a new one at the kiosk.")
        ref = e.token
    else:
        ref = ref if ref.startswith("J-") else f"J-{ref}"
        e = db.scalar(select(Encounter).where(Encounter.token == ref, Encounter.facility_id == ANY_FACILITY))
    if not e:
        since = now() - timedelta(hours=get_settings().home_intake_valid_h * 2)
        done = next((x for x in db.scalars(select(Encounter).where(Encounter.channel == "home_link", Encounter.created_at >= since))
                     if (x.intake or {}).get("any_centre_ref") == ref), None)
        if done:
            raise HTTPException(409, "This form was already checked in" + (" here" if done.facility_id == user.facility_id else " at another centre"))
        raise HTTPException(404, "No form found for this reference. Check the letters, or fill in a new one at the kiosk.")
    if e.status != "expected":
        raise HTTPException(409, f"This form is {e.status}")
    if aware(e.created_at) < now() - timedelta(hours=get_settings().home_intake_valid_h):
        e.status = "lapsed"
        db.commit()
        raise HTTPException(410, "This form is older than the validity window. Please fill in a new one at the kiosk.")
    e.facility_id = user.facility_id
    e.intake = {**(e.intake or {}), "facility_id": user.facility_id, "any_centre_ref": ref}
    check_in(db, e, user)
    audit.record(db, user, "ARRIVE", "encounter", e.id, f"Claimed any-centre form {ref} and checked in; token {e.token}", e.patient.code, e.facility_id)
    db.commit()
    if e.urgency == "red":
        alerts.check_capacity(db, e.facility_id)
    return encounter_out(e, user)


@router.get("/encounters/{eid}", response_model=EncounterOut)
def get_encounter(eid: str, user: CurrentUser, db: DB):
    e = load_encounter(db, eid, user)
    if e.status == "queued" and user.role in REVIEWER_ROLES:
        e.status = "in_review"
    audit.record(db, user, "VIEW", "encounter", eid, "Triage note viewed", e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.patch("/encounters/{eid}", response_model=EncounterOut)
def patch_encounter(eid: str, body: EncounterPatch, user: Doctor, db: DB):
    e = load_encounter(db, eid, user)
    if body.referral_needed is not None:
        e.referral_needed = body.referral_needed
        audit.record(db, user, "UPDATE", "encounter", eid, f"Referral needed: {'yes' if body.referral_needed else 'no'}", e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.post("/encounters/{eid}/medications", response_model=EncounterOut)
def review_medications(eid: str, body: MedicationReview, user: Clinician, db: DB):
    """Medicines read from a photo enter the record only here, one by one, by a nurse or doctor."""
    e = load_encounter(db, eid, user)
    note, intake = dict(e.note or {}), dict(e.intake or {})
    pending = {m["name"]: m for m in note.get("medications_pending") or []}
    unknown = [n for n in body.confirm + body.reject if n not in pending]
    if unknown:
        raise HTTPException(422, f"Not awaiting confirmation: {', '.join(unknown)}")
    stamp = {"by": f"{user.name} ({user.role})", "at": now().isoformat()}
    added = [{"name": n, "strength": pending[n].get("strength"), "source": f"read from {pending[n]['filename']}", **stamp} for n in body.confirm]
    intake["medications_confirmed"] = list(intake.get("medications_confirmed") or []) + added
    intake["medications_rejected"] = list(intake.get("medications_rejected") or []) + body.reject
    left = [m for n, m in pending.items() if n not in body.confirm and n not in body.reject]
    note["medications"] = intake["medications_confirmed"]
    note["medications_pending"] = left
    flags = [f for f in note.get("flags") or [] if f.get("code") != "MEDS-UNCONFIRMED"]
    if left:
        flags.append({"code": "MEDS-UNCONFIRMED", "label": f"{len(left)} medicine name(s) read from a strip or prescription — awaiting confirmation", "severity": "warning",
                      "reason": "Read by OCR and matched to the PMBJP generic list; not part of the record until a nurse or doctor confirms each one"})
    note["flags"] = flags
    e.intake, e.note = intake, note
    audit.record(db, user, "UPDATE", "encounter", e.id, f"Medicines read from photo — confirmed: {', '.join(body.confirm) or 'none'}; rejected: {', '.join(body.reject) or 'none'}", e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.post("/encounters/{eid}/observations", response_model=EncounterOut)
def add_observations(eid: str, body: ObservationIn, user: Reviewer, db: DB):
    """Nurse (or doctor) records vitals and bedside observations. Rules are re-run on the new vitals."""
    e = load_encounter(db, eid, user)
    vitals = {k: v for k, v in (body.vitals.model_dump() if body.vitals else {}).items() if v is not None}
    note = (body.note or "").strip()
    signs = [s for s in (body.signs or []) if s in FINDINGS]
    if body.signs and len(signs) != len(body.signs):
        raise HTTPException(422, "Unknown danger sign")
    if not vitals and not note and not signs and not body.exam_done:
        raise HTTPException(422, "Enter at least one vital sign, danger sign or observation")
    before = e.urgency
    record_observations(db, e, user, vitals, note, signs, body.exam_done)
    parts = [f"{k}={v}" for k, v in vitals.items()] + ([f"signs: {', '.join(signs)}"] if signs else []) + (["danger-sign check done"] if body.exam_done else []) + ([f"note: {note[:120]}"] if note else [])
    change = f"; urgency {before} → {e.urgency} (rules)" if e.urgency != before else ""
    audit.record(db, user, "UPDATE", "encounter", e.id, f"Observations recorded by {user.role}: {', '.join(parts)}{change}", e.patient.code, e.facility_id)
    alerts.check_fever_cluster(db, e.facility_id, alerts.cluster_of(e))  # a measured temperature can make a case a fever
    if e.urgency != before:
        alerts.check_capacity(db, e.facility_id)
    if (e.intake or {}).get("ai_assist", True):
        summarise_later(e.id)  # the note was rebuilt from the new vitals, so its summary is rewritten too
    return encounter_out(e, user)


@router.post("/encounters/{eid}/confirm", response_model=EncounterOut)
def confirm(eid: str, user: Reviewer, db: DB):
    """Sign-off limits (E2): a health worker may confirm GREEN, a nurse up to YELLOW, a doctor or medical officer any tier."""
    e = load_encounter(db, eid, user)
    if not can_confirm(user.role, e.urgency):
        need = "a doctor or medical officer" if e.urgency == "red" else "a nurse, doctor or medical officer"
        raise HTTPException(403, f"A {user.role.replace('_', ' ')} cannot confirm a {e.urgency.upper()} note — it needs {need}")
    e.status, e.reviewed_by, e.reviewed_at = "confirmed", user.name, now()
    audit.record(db, user, "CONFIRM", "encounter", eid, f"Triage note ({e.urgency.upper()}) reviewed and confirmed by {user.role.replace('_', ' ')}", e.patient.code, e.facility_id)
    if e.urgency == "red":
        alerts.check_capacity(db, e.facility_id)
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
def override(eid: str, body: OverrideIn, user: Reviewer, db: DB):
    """Human-in-the-loop override (E9). The rules-engine output stays in `rules_urgency`.

    Raising the urgency is free: any reviewer may do it, a reason is optional. Lowering it needs a doctor or
    medical officer and a written reason of at least 15 characters."""
    e = load_encounter(db, eid, user)
    frm = e.urgency
    rank = {"green": 0, "yellow": 1, "red": 2}
    if body.to_urgency == frm:
        raise HTTPException(400, "The urgency is already " + frm.upper())
    down = rank[body.to_urgency] < rank.get(frm, 0)
    if down and user.role not in DOCTOR_ROLES:
        raise HTTPException(403, "Only a doctor or medical officer can lower the urgency; you can raise it or escalate")
    if down and len(body.reason) < 15:
        raise HTTPException(422, "A written reason of at least 15 characters is required to lower the urgency")
    # Rules marked non-downgradable can still be overruled by a doctor (humans decide), but never
    # silently: the audit entry names every such rule that the new urgency goes below.
    overruled = [h["rule_id"] for h in ((e.note or {}).get("rules_fired") or [])
                 if h.get("non_downgradable") and rank.get(h["urgency"], 0) > rank[body.to_urgency]]
    e.override = {"from_urgency": frm, "to_urgency": body.to_urgency, "category": body.category, "reason": body.reason, "by": user.name, "by_role": user.role, "at": now().isoformat(), "direction": "down" if down else "up", "overruled_non_downgradable": overruled}
    e.urgency = body.to_urgency
    e.urgency_source = "override"
    esc = escalate_after(body.to_urgency)
    e.escalation_due_at = e.created_at + timedelta(minutes=esc) if esc else None
    audit.record(db, user, "OVERRIDE", "encounter", eid, f'Urgency {frm} → {body.to_urgency} ({"lowered" if down else "raised"}; {body.category}). Reason: "{body.reason or "none given"}". Rules-engine output ({e.rules_urgency}) retained.{(" Overrules non-downgradable rule(s): " + ", ".join(overruled)) if overruled else ""}', e.patient.code, e.facility_id)
    return encounter_out(e, user)


@router.get("/encounters/{eid}/export")
def export(eid: str, user: Doctor, db: DB, format: ExportFormat = "pdf"):
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
        due_at=aware(r.due_at), overdue=r.status != "received" and r.due_at is not None and aware(r.due_at) < now(),
        received_at=aware(r.received_at), received_by=r.received_by, received_note=r.received_note, received_via=r.received_via,
    )


# E4: how long a referral may stay open before someone checks whether the patient arrived.
REFERRAL_DUE = {"red": timedelta(hours=6), "yellow": timedelta(hours=48), "green": timedelta(days=14)}


@router.post("/encounters/{eid}/referrals", response_model=ReferralOut)
def create_referral(eid: str, body: ReferralIn, user: Doctor, db: DB):
    e = load_encounter(db, eid, user)
    r = Referral(encounter_id=e.id, created_by=user.name, due_at=now() + REFERRAL_DUE.get(e.urgency or "green", REFERRAL_DUE["green"]), **body.model_dump())
    db.add(r)
    e.status, e.referral_needed = "referred", True
    e.reviewed_by = e.reviewed_by or user.name
    e.reviewed_at = e.reviewed_at or now()
    db.flush()
    audit.record(db, user, "REFERRAL", "encounter", e.id, f"Referral to {body.destination} ({body.specialty}); transport: {body.transport}", e.patient.code, e.facility_id)
    db.refresh(r)
    return ref_out(r)


@router.post("/referrals/{rid}/received", response_model=ReferralOut)
def referral_received(rid: str, body: ReferralReceivedIn, user: Doctor, db: DB):
    """E4: the referring doctor records that care was received (for example confirmed by phone with the destination)."""
    r = db.get(Referral, rid)
    if not r or r.encounter.facility_id != user.facility_id:
        raise HTTPException(404, "Referral not found")
    mark_received(db, r, body.confirmed_by, body.note, "phone", user)
    return ref_out(r)


def mark_received(db, r: Referral, by: str, note: str, via: str, user) -> None:
    from ..alerts import _resolve

    if r.status == "received":
        raise HTTPException(409, f"Already confirmed received by {r.received_by}")
    r.status, r.received_at, r.received_by, r.received_note, r.received_via = "received", now(), by.strip(), note.strip() or None, via
    _resolve(db, r.encounter.facility_id, "referral_overdue", r.id, f"care received ({by.strip()})")
    how = "the receiving clinician (QR summary)" if via == "qr" else "the referring doctor"
    audit.record(db, user, "REFERRAL", "referral", r.id, f"Care received at {r.destination}; confirmed by {by.strip()}, recorded by {how}",
                 r.encounter.patient.code, r.encounter.facility_id)


@router.get("/referrals", response_model=list[ReferralOut])
def list_referrals(user: Doctor, db: DB):
    q = select(Referral).join(Encounter).where(Encounter.facility_id == user.facility_id).order_by(Referral.created_at.desc())
    return [ref_out(r) for r in db.scalars(q).unique()]
