"""Facilities, facility admin (F1), kiosk devices, staff list."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from .. import audit, regions
from ..models import Device, Encounter, Escalation, Facility, Referral, User
from ..schemas import ADMIN_ROLES, STAFF_ROLES, DeviceIn, DutyIn, DeviceOut, FacilityOut, FacilityPatch, FacilityStats, UserOut, UserPatch
from ..security import DB, CurrentUser, require
from ..services import auto_escalate, aware, calendar_context, now, wait_minutes
from ..triage.timeline import onset
from .auth import user_out

router = APIRouter(tags=["facilities"])
Admin = Annotated[User, Depends(require(*ADMIN_ROLES))]  # front desk + supervisor
Supervisor = Annotated[User, Depends(require("supervisor"))]
Staff = Annotated[User, Depends(require(*STAFF_ROLES))]


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(db: DB):
    # Public: needed on the registration screen before an account exists. No clinical data.
    return list(db.scalars(select(Facility).order_by(Facility.name)))


@router.get("/facilities/{fid}", response_model=FacilityOut)
def get_facility(fid: str, db: DB):
    f = db.get(Facility, fid)
    if not f:
        raise HTTPException(404, "Facility not found")
    return f


@router.patch("/facilities/{fid}", response_model=FacilityOut)
def update_facility(fid: str, body: FacilityPatch, user: Supervisor, db: DB):
    if user.facility_id != fid:
        raise HTTPException(403, "You can only configure your own facility")
    f = db.get(Facility, fid)
    if not f:
        raise HTTPException(404, "Facility not found")
    patch = body.model_dump(exclude_unset=True, mode="json")
    changed = []
    for k, v in patch.items():
        if k == "specialists" and v is not None:
            v = [dict(s) for s in v]
        if getattr(f, k) != v:
            setattr(f, k, v)
            changed.append(k)
    audit.record(db, user, "CONFIG", "facility", fid, f"Facility configuration updated: {', '.join(changed) or 'no changes'}")
    db.refresh(f)
    return f


def _facility(db, fid: str) -> Facility:
    f = db.get(Facility, fid)
    if not f:
        raise HTTPException(404, "Facility not found")
    return f


@router.get("/facilities/{fid}/calendar")
def facility_calendar(fid: str, user: Staff, db: DB, on: date | None = None):
    """F5: the festivals (about a year back, four months ahead) and seasons this facility's notes date onsets by,
    with the worker names it uses. Public data only; no patient information."""
    f = _facility(db, fid)
    on = on or calendar_context(f, now())["on"]
    return {**regions.for_facility(f).view(on), "facility_id": fid, "region_config": f.region_config or {}}


@router.get("/facilities/{fid}/onset")
def try_onset(fid: str, user: Staff, db: DB, text: str = Query(min_length=2, max_length=300), on: date | None = None):
    """Try a phrase ("since Diwali", "ରଜଠାରୁ") against this facility's calendar, as the note would read it."""
    f = _facility(db, fid)
    on = on or calendar_context(f, now())["on"]
    return {"on": on.isoformat(), **onset({"chief_complaint": text}, regions.for_facility(f), on)}


@router.get("/facilities/{fid}/stats", response_model=FacilityStats)
def facility_stats(fid: str, user: CurrentUser, db: DB):
    if user.role not in STAFF_ROLES or user.facility_id != fid:
        raise HTTPException(403, "Not allowed")
    auto_escalate(db)
    start = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=6)
    today = [e for e in db.scalars(select(Encounter).where(Encounter.facility_id == fid)) if aware(e.created_at) >= start]
    waiting = [e for e in today if e.status in ("queued", "escalated")]
    ids = {e.id for e in today}
    return FacilityStats(
        facility_id=fid,
        today_total=len(today),
        by_urgency={u: sum(1 for e in today if e.urgency == u) for u in ("red", "yellow", "green")},
        avg_wait_minutes=round(sum(wait_minutes(e) for e in waiting) / len(waiting)) if waiting else 0,
        open_escalations=sum(1 for x in db.scalars(select(Escalation).where(Escalation.status == "open")) if x.encounter_id in ids),
        referrals_today=sum(1 for r in db.scalars(select(Referral)) if r.encounter_id in ids),
        offline_synced_today=sum(1 for e in today if (e.intake or {}).get("captured_offline")),
    )


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(user: Staff, db: DB):
    return list(db.scalars(select(Device).where(Device.facility_id == user.facility_id).order_by(Device.bound_at.desc())))


@router.post("/devices", response_model=DeviceOut)
def bind_device(body: DeviceIn, user: Staff, db: DB):
    d = db.get(Device, body.device_id)
    if d and d.facility_id != user.facility_id:
        raise HTTPException(409, "Device is bound to another facility")
    if d:
        d.revoked, d.label, d.last_seen_at = False, body.label, now()
        msg = f"Kiosk device '{body.label}' re-bound"
    else:
        d = Device(id=body.device_id, label=body.label, facility_id=user.facility_id, bound_by=user.name, bound_by_id=user.id, last_seen_at=now())
        db.add(d)
        msg = f"Kiosk device '{body.label}' bound to facility"
    audit.record(db, user, "DEVICE", "device", body.device_id, msg)
    return d


@router.delete("/devices/{device_id}", status_code=204)
def revoke_device(device_id: str, user: Supervisor, db: DB):
    d = db.get(Device, device_id)
    if not d or d.facility_id != user.facility_id:
        raise HTTPException(404, "Device not found")
    d.revoked = True
    audit.record(db, user, "DEVICE", "device", device_id, f"Kiosk device '{d.label}' revoked")


@router.patch("/users/{uid}", response_model=UserOut)
def update_user(uid: str, body: UserPatch, user: Annotated[User, Depends(require("supervisor"))], db: DB):
    """Supervisor: change a staff member's role or deactivate them (sessions end immediately)."""
    u = db.get(User, uid)
    if not u or u.facility_id != user.facility_id or u.role not in STAFF_ROLES:
        raise HTTPException(404, "Staff member not found")
    if u.id == user.id:
        raise HTTPException(422, "You cannot change your own role or access")
    changes = []
    if body.role and body.role != u.role:
        changes.append(f"role {u.role} → {body.role}")
        u.role = body.role
    if body.is_active is not None and body.is_active != u.is_active:
        changes.append("reactivated" if body.is_active else "deactivated")
        u.is_active = body.is_active
    audit.record(db, user, "UPDATE", "user", u.id, f"Staff {u.name}: {', '.join(changes) or 'no changes'}")
    return user_out(db, u)


@router.post("/users/{uid}/reset-pin", status_code=204)
def reset_staff_pin(uid: str, user: Annotated[User, Depends(require("supervisor"))], db: DB):
    """Forgotten PIN: the staff member sets a new one at their next sign-in (after phone OTP)."""
    u = db.get(User, uid)
    if not u or u.facility_id != user.facility_id or u.role not in STAFF_ROLES or u.id == user.id:
        raise HTTPException(404, "Staff member not found")
    u.pin_hash, u.pin_failed_attempts, u.pin_locked_until = None, 0, None
    audit.record(db, user, "UPDATE", "user", u.id, f"PIN reset for {u.name}; a new PIN is required at next sign-in")


@router.get("/users", response_model=list[UserOut])
def list_users(user: Admin, db: DB):
    """Supervisor: every staff account. Front desk: the doctors and nurses (for duty and time management)."""
    q = select(User).where(User.facility_id == user.facility_id, User.role.in_(STAFF_ROLES)).order_by(User.name)
    if user.role != "supervisor":
        q = q.where(User.role.in_(("doctor", "medical_officer", "nurse", "health_worker")))
    return [user_out(db, u) for u in list(db.scalars(q))]


@router.patch("/users/{uid}/duty", response_model=UserOut)
def set_duty(uid: str, body: DutyIn, user: Admin, db: DB):
    """Front desk / supervisor: mark a clinician (doctor, medical officer, nurse or health worker) on or off duty."""
    u = db.get(User, uid)
    if not u or u.facility_id != user.facility_id or u.role not in ("doctor", "medical_officer", "nurse", "health_worker"):
        raise HTTPException(404, "Clinician not found")
    if u.on_duty != body.on_duty:
        u.on_duty, u.duty_changed_at = body.on_duty, now()
        audit.record(db, user, "UPDATE", "user", u.id, f"{u.name} marked {'on' if body.on_duty else 'off'} duty")
    return user_out(db, u)
