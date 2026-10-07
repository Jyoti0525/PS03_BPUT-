"""Alerts (capacity, fever cluster, missed visit, call escalation), maternal and chronic follow-ups, reminder calls (E6),
syndromic export and employer department rates."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import select

from .. import alerts as al
from .. import audit, calls, sarvam, telephony
from ..config import get_settings
from ..models import Alert, Call, Encounter, Patient, Reminder, User
from ..privacy import K_MIN
from ..schemas import (DOCTOR_ROLES, REVIEWER_ROLES, STAFF_ROLES, AckIn, AlertOut, CallAnswerIn, CallEndIn, CallOut, CallStartIn, CapacityOut,
                       FollowupAttemptIn, FollowupOut)
from ..security import DB, require
from ..services import auto_escalate, aware, now
from .organisations import my_org

router = APIRouter(tags=["alerts"])
Reviewer = Annotated[User, Depends(require(*REVIEWER_ROLES))]
Officer = Annotated[User, Depends(require(*DOCTOR_ROLES))]
Employer = Annotated[User, Depends(require("employer"))]
Staff = Annotated[User, Depends(require(*STAFF_ROLES))]


def _visible(a: Alert, user: User) -> bool:
    """A health worker sees the missed visits and call escalations assigned to them (or to nobody); everyone else on the
    clinical side sees all."""
    if user.role == "health_worker":
        return a.kind in ("missed_visit", "call_escalation") and a.assigned_to in (None, user.id)
    return True


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(user: Reviewer, db: DB, status: str | None = Query(None, pattern="^(open|acknowledged|resolved|active)$")):
    auto_escalate(db)
    al.check_capacity(db, user.facility_id)
    al.check_missed_visits(db, user.facility_id)
    q = select(Alert).where(Alert.facility_id == user.facility_id).order_by(Alert.raised_at.desc())
    if status == "active":
        q = q.where(Alert.status != "resolved")
    elif status:
        q = q.where(Alert.status == status)
    return [a for a in db.scalars(q.limit(200)) if _visible(a, user)]


@router.post("/alerts/{aid}/acknowledge", response_model=AlertOut)
def acknowledge_alert(aid: str, body: AckIn, user: Reviewer, db: DB):
    a = db.get(Alert, aid)
    if not a or a.facility_id != user.facility_id or not _visible(a, user):
        raise HTTPException(404, "Alert not found")
    if a.kind in ("capacity", "fever_cluster") and user.role not in DOCTOR_ROLES:
        raise HTTPException(403, "Only a doctor or medical officer can acknowledge this alert")
    if a.status == "resolved":
        raise HTTPException(409, "Alert already resolved")
    if a.kind == "call_escalation" and not (body.note or "").strip():
        raise HTTPException(422, "Say what was done, for example: phoned her back, coming in today")
    a.status, a.acknowledged_by, a.acknowledged_at, a.ack_note, a.updated_at = "acknowledged", user.name, now(), body.note or None, now()
    if a.kind == "call_escalation" and (r := db.get(Reminder, a.key)) and r.status == "flagged":
        r.status = "contacted"  # a person has called back; the follow-up stays open until the visit
        r.attempts = [*(r.attempts or []), {"at": now().isoformat(), "by": f"{user.name} ({user.role})", "outcome": "reached", "note": body.note}]
    audit.record(db, user, "ACKNOWLEDGE", "alert", a.id, f"{a.kind} alert acknowledged{': ' + body.note if body.note else ''}", None, a.facility_id)
    return a


@router.get("/capacity", response_model=CapacityOut)
def capacity(user: Reviewer, db: DB):
    auto_escalate(db)
    c = al.check_capacity(db, user.facility_id)
    return CapacityOut(open_red=c["open_red"], doctors_on_duty=c["doctors_on_duty"], over=c["over"], reds=c["reds"],
                       alert=AlertOut.model_validate(c["alert"]) if c["alert"] else None)


@router.get("/surveillance/syndromic.csv")
def syndromic(user: Officer, db: DB, days: int = Query(14, ge=1, le=90)):
    """Daily counts per place and syndrome for the medical officer (IDSP-style). Counts of 1–4 are written as "<5"."""
    body = al.syndromic_csv(db, user.facility_id, days)
    audit.record(db, user, "EXPORT", "surveillance", user.facility_id, f"Syndromic counts exported ({days} days, counts below {K_MIN} suppressed)", None, user.facility_id)
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="syndromic_{days}d.csv"'})


# ── Maternal and chronic follow-ups (D4, E5) ──────────
def _followup_out(db, r: Reminder) -> FollowupOut:
    p = db.get(Patient, r.patient_id)
    worker = db.get(User, r.assigned_to) if r.assigned_to else None
    enc = db.get(Encounter, r.encounter_id) if r.encounter_id else None
    gw = ((enc.intake or {}).get("maternal") or {}).get("gestation_weeks") if enc else None
    return FollowupOut(
        programme=calls.PROGRAMME.get(r.kind, r.kind), condition=calls.condition_of(db, r), who_calls=calls.who_calls(db, r, p),
        id=r.id, patient_id=p.id, patient_code=p.code, patient_name=p.name, village=p.village, phone=p.phone, phone_belongs_to=r.phone_belongs_to,
        kind=r.kind, due_at=r.due_at, status=r.status, missed_at=r.missed_at, attempts=list(r.attempts or []), assigned_to=r.assigned_to,
        assigned_name=worker.name if worker else None, gestation_weeks=gw, call_script=al.call_script(r, p, al.facility_name(db, r.facility_id)),
        resolved_at=r.resolved_at,
    )


@router.get("/health-workers")
def health_workers(user: Staff, db: DB):
    """Active health workers (ASHA / ANM / MPW) at the caller's facility, to assign a pregnant woman's follow-up. Names only."""
    q = select(User).where(User.facility_id == user.facility_id, User.role == "health_worker", User.is_active).order_by(User.name)
    return [{"id": u.id, "name": u.name} for u in db.scalars(q)]


def _reminder(db, rid: str, user: User) -> Reminder:
    r = db.get(Reminder, rid)
    if not r or r.facility_id != user.facility_id:
        raise HTTPException(404, "Follow-up not found")
    if user.role == "health_worker" and r.assigned_to not in (None, user.id):
        raise HTTPException(403, "This follow-up is assigned to another health worker")
    return r


@router.get("/followups", response_model=list[FollowupOut])
def followups(user: Reviewer, db: DB, scope: str = Query("active", pattern="^(active|all)$"),
              programme: str = Query("all", pattern="^(all|maternal|chronic)$")):
    """A health worker sees the patients assigned to them (and unassigned ones); nurses, doctors and the MO see the facility."""
    al.check_missed_visits(db, user.facility_id)
    kinds = [k for k, v in calls.PROGRAMME.items() if programme in ("all", v)]
    q = select(Reminder).where(Reminder.facility_id == user.facility_id, Reminder.kind.in_(kinds)).order_by(Reminder.due_at)
    if scope == "active":
        q = q.where(Reminder.status.in_(al.ACTIVE))
    if user.role == "health_worker":
        q = q.where((Reminder.assigned_to == user.id) | (Reminder.assigned_to.is_(None)))
    rows = [_followup_out(db, r) for r in db.scalars(q)]
    order = {"flagged": 0, "call_due": 1, "missed": 2, "contacted": 3, "scheduled": 4}
    return sorted(rows, key=lambda f: (order.get(f.status, 4), f.due_at))


@router.post("/followups/{rid}/attempt", response_model=FollowupOut)
def followup_attempt(rid: str, body: FollowupAttemptIn, user: Reviewer, db: DB):
    r = _reminder(db, rid, user)
    if r.status not in al.ACTIVE:
        raise HTTPException(409, "This follow-up is closed")
    al.record_attempt(db, r, user, body.outcome, body.note)
    p = db.get(Patient, r.patient_id)
    audit.record(db, user, "UPDATE", "reminder", r.id, f"Follow-up attempt: {body.outcome.replace('_', ' ')}; status {r.status}", p.code, r.facility_id)
    return _followup_out(db, r)


# ── Reminder calls (E6) ───────────────────────────────
def _call_out(db, c: Call) -> CallOut:
    p = db.get(Patient, c.patient_id)
    return CallOut(
        id=c.id, reminder_id=c.reminder_id, patient_name=p.name, patient_code=p.code, programme=c.programme, operator=c.operator, language=c.language,
        audience=c.audience, status=c.status, outcome=c.outcome, turns=list(c.turns or []), red_flags=c.red_flags, notes=c.notes,
        expects=("yes_no" if calls.asks_yes_no(c) else "free") if c.status == "active" else None, alert_id=c.alert_id,
        started_at=c.started_at, ended_at=c.ended_at, sources=calls.sources(c.programme),
        voice="sarvam" if sarvam.enabled() and c.language in sarvam.TTS_LANGS else "device",
        channel="phone" if (c.notes or {}).get("phone") else "browser",
    )


def _call(db, cid: str, user: User) -> Call:
    c = db.get(Call, cid)
    if not c or c.facility_id != user.facility_id:
        raise HTTPException(404, "Call not found")
    _reminder(db, c.reminder_id, user)  # a health worker only reaches calls for their own patients
    return c


def alert_staff_by_sms(db, c: Call) -> None:
    """A danger sign or an unclear answer on a reminder call also texts the demo phone (standing in for the medical
    officer and the assigned health worker): the patient's code and what to do, never a name or a symptom."""
    if c.outcome not in ("danger_sign", "unclear") or not telephony.sms_ready() or (c.notes or {}).get("staff_sms"):
        return
    p = db.get(Patient, c.patient_id)
    body = telephony.staff_alert_text(c.outcome, p.code, al.facility_name(db, c.facility_id), c.ended_at or now())
    try:
        sid = telephony.send_sms(body)
        c.notes = {**(c.notes or {}), "staff_sms": {"sent": True, "to": telephony.mask(get_settings().telephony_demo_to), "sid": sid}}
    except telephony.TelephonyUnavailable as e:
        c.notes = {**(c.notes or {}), "staff_sms": {"sent": False, "error": str(e)}}


def _warm_voice(c: Call, bg: BackgroundTasks) -> None:
    """Have Sarvam speak the agent's newest line while the response travels, so the page's fetch finds it ready."""
    if c.operator == "agent" and sarvam.enabled() and c.language in sarvam.TTS_LANGS:
        line = next((t["text"] for t in reversed(c.turns or []) if t.get("who") == "agent"), None)

        def warm():
            try:
                sarvam.speak(line, c.language)
            except sarvam.SarvamUnavailable:
                pass  # the page falls back to the device's voice

        if line:
            bg.add_task(warm)


def _refused(e: calls.CallRefused):
    return HTTPException(e.status, str(e))


@router.post("/followups/{rid}/calls", response_model=CallOut)
def start_call(rid: str, body: CallStartIn, user: Reviewer, db: DB, bg: BackgroundTasks):
    """Start a reminder call in the browser: the agent's lines are shown and read aloud (Sarvam's voice when set up),
    and the patient's answers are typed, tapped or spoken there."""
    r = _reminder(db, rid, user)
    if body.channel == "phone":
        if body.operator != "agent":
            raise HTTPException(422, "A person calling uses their own phone; only the agent's call goes through Twilio")
        if not telephony.calls_ready():
            raise HTTPException(503, "Phone calls are not set up: " + "; ".join(telephony.status()["missing"]))
    try:
        c = calls.start(db, r, user, body.operator, body.language)
    except calls.CallRefused as e:
        raise _refused(e) from None
    if body.channel == "phone":
        c.notes = {**(c.notes or {}), "phone": {"to": telephony.mask(get_settings().telephony_demo_to), "played": 0, "answered": False}}
    db.commit()  # before dialling: Twilio may ask for the first line before the dial request returns
    if body.channel == "phone":
        try:
            sid = telephony.place_call(c.id)
        except telephony.TelephonyUnavailable as e:
            c.notes = {**c.notes, "phone": {**c.notes["phone"], "error": str(e)}}
            calls.hang_up(db, c, user, "no_answer")
            db.commit()
            raise HTTPException(502, f"The call could not be placed: {e}") from None
        c.notes = {**c.notes, "phone": {**c.notes["phone"], "sid": sid}}
        audit.record(db, user, "UPDATE", "call", c.id, f"Phone call placed through Twilio to the demo phone {c.notes['phone']['to']}",
                     db.get(Patient, c.patient_id).code, c.facility_id)
        db.commit()
    else:
        _warm_voice(c, bg)
    return _call_out(db, c)


@router.get("/followups/{rid}/calls", response_model=list[CallOut])
def list_calls(rid: str, user: Reviewer, db: DB):
    r = _reminder(db, rid, user)
    return [_call_out(db, c) for c in db.scalars(select(Call).where(Call.reminder_id == r.id).order_by(Call.started_at.desc()))]


@router.get("/calls/{cid}", response_model=CallOut)
def get_call(cid: str, user: Reviewer, db: DB):
    return _call_out(db, _call(db, cid, user))


@router.get("/calls/{cid}/turns/{i}/audio")
def call_audio(cid: str, i: int, user: Reviewer, db: DB):
    """One of the agent's lines, spoken by Sarvam's Bulbul voice (MP3). 503 when Sarvam is not configured or cannot be
    reached: the page then uses the device's own voice. The words are the fixed line already shown; nothing is added."""
    c = _call(db, cid, user)
    turns = c.turns or []
    if not (0 <= i < len(turns)) or turns[i].get("who") != "agent":
        raise HTTPException(404, "No agent line here")
    try:
        audio = sarvam.speak(turns[i]["text"], c.language)
    except sarvam.SarvamUnavailable as e:
        raise HTTPException(503, str(e)) from None
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/calls/{cid}/answer", response_model=CallOut)
def call_answer(cid: str, body: CallAnswerIn, user: Reviewer, db: DB, bg: BackgroundTasks):
    c = _call(db, cid, user)
    try:
        calls.answer(db, c, user, body.text, body.original_text)
    except calls.CallRefused as e:
        raise _refused(e) from None
    alert_staff_by_sms(db, c)
    db.commit()
    _warm_voice(c, bg)
    return _call_out(db, c)


@router.post("/calls/{cid}/end", response_model=CallOut)
def call_end(cid: str, body: CallEndIn, user: Reviewer, db: DB):
    c = _call(db, cid, user)
    sid = ((c.notes or {}).get("phone") or {}).get("sid")
    if sid and c.status == "active":
        try:
            telephony.end_call(sid)
        except telephony.TelephonyUnavailable:
            pass  # recorded as ended here either way
    try:
        calls.hang_up(db, c, user, body.outcome)
    except calls.CallRefused as e:
        raise _refused(e) from None
    db.commit()
    return _call_out(db, c)


@router.get("/telephony/status")
def telephony_status(user: Reviewer):
    """Whether real phone calls and SMS are set up, and which demo phone they go to (last four digits)."""
    return telephony.status()


@router.post("/followups/{rid}/sms", response_model=FollowupOut)
def followup_sms(rid: str, user: Reviewer, db: DB):
    """A reminder SMS in the patient's language, to the demo phone. It never names a pregnancy or a condition; on a
    phone that is not the patient's own it only asks the reader to pass on the visit."""
    r = _reminder(db, rid, user)
    p = db.get(Patient, r.patient_id)
    if r.status not in al.ACTIVE:
        raise HTTPException(409, "This follow-up is closed")
    if r.phone_belongs_to == "none" or not p.phone:
        raise HTTPException(422, "No phone to text — this needs a home visit")
    lang = p.language if p.language in calls.LANGS else "en"
    ctx = {"name": al.first_name(p), "facility": al.facility_name(db, r.facility_id), "date": aware(r.due_at).strftime("%d/%m")}
    text = telephony.sms_text(lang, "self" if r.phone_belongs_to == "self" else "other", ctx)
    try:
        telephony.send_sms(text)
    except telephony.TelephonyUnavailable as e:
        raise HTTPException(503, str(e)) from None
    to = telephony.mask(get_settings().telephony_demo_to)
    r.attempts = [*(r.attempts or []), {"at": now().isoformat(), "by": f"{user.name} ({user.role})", "outcome": "sms",
                                        "note": f"Reminder SMS sent in {lang} to the demo phone {to}: {text}"}]
    audit.record(db, user, "UPDATE", "reminder", r.id, f"Reminder SMS sent ({lang}) to the demo phone {to}", p.code, r.facility_id)
    db.commit()
    return _followup_out(db, r)


# ── Employer: department rates (D2) ───────────────────
@router.get("/employer/department-rates")
def department_rates(user: Employer, db: DB, days: int = Query(365, ge=30, le=730)):
    """Per department: workers screened, the share referred for occupational-health follow-up and the share with a
    protective-equipment gap. Counts only, never a symptom or a name; a department with fewer than 5 screened workers
    is not shown. A department is marked when its follow-up share is at least twice that of all other departments."""
    from ..triage.pipeline import ppe_gap

    org = my_org(db, user)
    since = now() - timedelta(days=days)
    latest: dict[str, Encounter] = {}
    q = select(Encounter).join(Patient).where(Patient.organisation_id == org.id, Encounter.created_at >= since).order_by(Encounter.created_at)
    for e in db.scalars(q).unique():
        if ((e.intake or {}).get("occupational") or {}).get("exposures"):
            latest[e.patient_id] = e  # the worker's most recent screening
    dept: dict[str, dict] = {}
    for e in latest.values():
        d = dept.setdefault(e.patient.department or "Unassigned", {"screened": 0, "follow_up": 0, "ppe_gap": 0})
        d["screened"] += 1
        d["follow_up"] += any(h["rule_id"].startswith("OCC-") for h in (e.note or {}).get("rules_fired") or [])
        d["ppe_gap"] += bool(ppe_gap((e.intake or {}).get("occupational") or {}))
    out = []
    for name, d in sorted(dept.items()):
        if d["screened"] < K_MIN:
            out.append({"department": name, "screened": None, "follow_up_pct": None, "ppe_gap_pct": None, "above_others": False, "suppressed": True})
            continue
        others = [x for n, x in dept.items() if n != name]
        o_scr, o_fu = sum(x["screened"] for x in others), sum(x["follow_up"] for x in others)
        rate = d["follow_up"] / d["screened"]
        o_rate = o_fu / o_scr if o_scr else None
        out.append({"department": name, "screened": d["screened"], "follow_up_pct": round(rate * 100), "ppe_gap_pct": round(d["ppe_gap"] / d["screened"] * 100),
                    "above_others": bool(o_scr >= K_MIN and rate > 0 and (o_rate == 0 or rate >= 2 * o_rate)), "suppressed": False})
    audit.record(db, user, "VIEW", "cohort", org.id, f"Employer viewed department screening rates ({days} days; no symptoms, departments under {K_MIN} hidden)")
    return {"days": days, "k_min": K_MIN, "departments": out,
            "note": "Follow-up means the screening rules asked for an occupational-health review. Symptoms, names and notes are never shown to the employer."}
