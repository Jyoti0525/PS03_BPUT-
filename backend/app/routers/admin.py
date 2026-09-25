"""Audit log (G4), retention status, patient self-service, employer cohorts."""

import csv
import io
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_, select

from .. import audit, storage
from ..models import AuditEvent, Cohort, Encounter, FileObject, Reminder, User
from ..schemas import ADMIN_ROLES, AuditOut, AuditVerify, CohortOut, MyRecord, PatientOut, ReminderOut, RetentionOut
from ..security import DB, require
from ..services import encounter_out, now, own_patient
from .files import file_out

router = APIRouter(tags=["governance"])
Auditor = Annotated[User, Depends(require(*ADMIN_ROLES, "doctor"))]
Admin = Annotated[User, Depends(require(*ADMIN_ROLES))]


@router.get("/audit", response_model=list[AuditOut])
def list_audit(user: Auditor, db: DB, action: str | None = None, q: str | None = None, limit: int = 500):
    stmt = select(AuditEvent).where(or_(AuditEvent.facility_id == user.facility_id, AuditEvent.facility_id.is_(None))).order_by(AuditEvent.id.desc()).limit(min(limit, 2000))
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(AuditEvent.actor_name.ilike(like), AuditEvent.detail.ilike(like), AuditEvent.patient_code.ilike(like)))
    return list(db.scalars(stmt))


@router.get("/audit/verify", response_model=AuditVerify)
def verify_audit(user: Auditor, db: DB):
    ok, n, broken = audit.verify(db)
    return AuditVerify(ok=ok, checked=n, broken_at=broken)


@router.get("/audit/export")
def export_audit(user: Auditor, db: DB):
    audit.record(db, user, "EXPORT", "audit", None, "Audit log exported as CSV")
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL)
    w.writerow(["id", "ts", "actor", "role", "action", "resource", "patient", "detail", "prev_hash", "hash"])
    for a in db.scalars(select(AuditEvent).where(or_(AuditEvent.facility_id == user.facility_id, AuditEvent.facility_id.is_(None))).order_by(AuditEvent.id)):
        w.writerow([a.id, a.ts.isoformat(), a.actor_name, a.actor_role, a.action, f"{a.resource_type}:{a.resource_id or ''}", a.patient_code or "", a.detail, a.prev_hash, a.hash])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="jeevia-audit-log.csv"'})


@router.get("/retention", response_model=RetentionOut)
def retention(user: Admin, db: DB):
    t = now()
    files = list(db.scalars(select(FileObject).order_by(FileObject.expires_at)))
    return RetentionOut(
        policy_hours={k: storage.retention_hours(k) for k in ("audio", "image", "report")},
        active=sum(1 for f in files if not f.purged_at and f.expires_at > t),
        pending_purge=sum(1 for f in files if not f.purged_at and f.expires_at <= t),
        purged_last_7d=sum(1 for f in files if f.purged_at and t - f.purged_at < timedelta(days=7)),
        files=[file_out(f) for f in files],  # metadata only: no URL for admins
    )


@router.get("/me/record", response_model=MyRecord)
def my_record(user: Annotated[User, Depends(require("patient"))], db: DB):
    p = own_patient(db, user)
    if not p:
        raise HTTPException(404, "No patient record linked to this phone yet")
    encs = db.scalars(select(Encounter).where(Encounter.patient_id == p.id).order_by(Encounter.created_at.desc()))
    rems = db.scalars(select(Reminder).where(Reminder.patient_id == p.id).order_by(Reminder.due_at))
    audit.record(db, user, "VIEW", "patient", p.id, "Patient viewed own record", p.code)
    return MyRecord(patient=PatientOut.model_validate(p), encounters=[encounter_out(e, user) for e in encs], reminders=[ReminderOut.model_validate(r) for r in rems])


@router.get("/employer/cohorts", response_model=list[CohortOut])
def cohorts(user: Annotated[User, Depends(require("employer"))], db: DB):
    audit.record(db, user, "VIEW", "cohort", None, "Employer viewed fitness cohorts (no clinical records)")
    return list(db.scalars(select(Cohort).where(Cohort.facility_id == user.facility_id)))
