"""Alerts (capacity, fever cluster, missed visit), maternal follow-ups, syndromic export and employer department rates."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select

from .. import alerts as al
from .. import audit
from ..models import Alert, Encounter, Patient, Reminder, User
from ..privacy import K_MIN
from ..schemas import DOCTOR_ROLES, REVIEWER_ROLES, STAFF_ROLES, AckIn, AlertOut, CapacityOut, FollowupAttemptIn, FollowupOut
from ..security import DB, require
from ..services import auto_escalate, now
from .organisations import my_org

router = APIRouter(tags=["alerts"])
Reviewer = Annotated[User, Depends(require(*REVIEWER_ROLES))]
Officer = Annotated[User, Depends(require(*DOCTOR_ROLES))]
Employer = Annotated[User, Depends(require("employer"))]
Staff = Annotated[User, Depends(require(*STAFF_ROLES))]


def _visible(a: Alert, user: User) -> bool:
    """A health worker sees the missed visits assigned to them (or to nobody); everyone else on the clinical side sees all."""
    if user.role == "health_worker":
        return a.kind == "missed_visit" and a.assigned_to in (None, user.id)
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
    a.status, a.acknowledged_by, a.acknowledged_at, a.ack_note, a.updated_at = "acknowledged", user.name, now(), body.note or None, now()
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


# ── Maternal follow-ups (D4) ──────────────────────────
def _followup_out(db, r: Reminder) -> FollowupOut:
    p = db.get(Patient, r.patient_id)
    worker = db.get(User, r.assigned_to) if r.assigned_to else None
    enc = db.get(Encounter, r.encounter_id) if r.encounter_id else None
    gw = ((enc.intake or {}).get("maternal") or {}).get("gestation_weeks") if enc else None
    return FollowupOut(
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
def followups(user: Reviewer, db: DB, scope: str = Query("active", pattern="^(active|all)$")):
    """A health worker sees the women assigned to them (and unassigned ones); nurses, doctors and the MO see the facility."""
    al.check_missed_visits(db, user.facility_id)
    q = select(Reminder).where(Reminder.facility_id == user.facility_id, Reminder.kind == "anc_checkup").order_by(Reminder.due_at)
    if scope == "active":
        q = q.where(Reminder.status.in_(al.ACTIVE))
    if user.role == "health_worker":
        q = q.where((Reminder.assigned_to == user.id) | (Reminder.assigned_to.is_(None)))
    rows = [_followup_out(db, r) for r in db.scalars(q)]
    order = {"call_due": 0, "missed": 1, "contacted": 2, "scheduled": 3}
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


@router.post("/followups/{rid}/call", response_model=FollowupOut)
def followup_call(rid: str, user: Reviewer, db: DB):
    """Place the reminder call. Simulated in this build: the script is recorded but no call is made (English only)."""
    r = _reminder(db, rid, user)
    p = db.get(Patient, r.patient_id)
    script = al.call_script(r, p, al.facility_name(db, r.facility_id))
    if script is None:
        raise HTTPException(422, "No phone to call — this needs a home visit")
    if r.status not in ("missed", "call_due", "contacted"):
        raise HTTPException(409, "A call is placed only after a missed check-up")
    attempts = list(r.attempts or [])
    attempts.append({"at": now().isoformat(), "by": f"{user.name} ({user.role})", "outcome": "call_placed", "note": "simulated — no call made in this build",
                     "script": script, "to": r.phone_belongs_to or "unknown"})
    r.attempts = attempts
    audit.record(db, user, "UPDATE", "reminder", r.id, f"Reminder call placed (simulated) to the {r.phone_belongs_to or 'unknown-owner'} phone; "
                 f"{'mentions the check-up' if r.phone_belongs_to == 'self' else 'neutral wording, nothing reproductive said'}", p.code, r.facility_id)
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
