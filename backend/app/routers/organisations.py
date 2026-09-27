"""Organisations (employers / institutions): profile, workplaces, worker roster, fitness cohorts.

An organisation sees only occupational fitness outcomes recorded by doctors — never symptoms,
notes, reports or visits.
"""

import csv
import io
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from .. import audit
from ..models import Facility, FitnessAssessment, Organisation, Patient, User
from ..schemas import (
    ORG_FACILITY_TYPES,
    CohortOut,
    FacilityOut,
    NewFacility,
    OrganisationHome,
    OrganisationOut,
    OrganisationPatch,
    WorkerImportIn,
    WorkerImportOut,
    WorkerIn,
    WorkerOut,
    WorkerPatch,
)
from ..security import DB, require
from ..services import next_patient_code

router = APIRouter(tags=["organisations"])
Employer = Annotated[User, Depends(require("employer"))]


def my_org(db, user: User) -> Organisation:
    if not user.organisation_id:
        raise HTTPException(404, "Your account is not linked to an organisation")
    org = db.get(Organisation, user.organisation_id)
    if not org:
        raise HTTPException(404, "Organisation not found")
    return org


def create_org_facility(db, org: Organisation, body: NewFacility, created_by: str) -> Facility:
    if body.type not in ORG_FACILITY_TYPES:
        raise HTTPException(422, "Organisations register company clinics, industrial units, campus health centres or health camps")
    slug = re.sub(r"[^a-z0-9]+", "", body.name.lower())[:20] or "workplace"
    f = Facility(
        id=f"fac_{slug}_{uuid.uuid4().hex[:6]}", name=body.name.strip(), type=body.type, district=body.district.strip(), state=body.state.strip(),
        languages=["en", "hi"], specialists=[{"key": "genmed", "label": "Occupational Health Physician" if body.type != "campus" else "General Medicine", "available": True, "schedule": None}],
        referral_destination=body.referral_destination or "", beds_total=0, beds_occupied=0, offline_mode=body.type == "health_camp", capabilities={},
        source="organisation", organisation_id=org.id, verified=False, pincode=body.pincode, address=body.address, created_by=created_by,
    )
    db.add(f)
    db.flush()
    return f


def latest_assessments(db, org_id: str) -> dict[str, FitnessAssessment]:
    out: dict[str, FitnessAssessment] = {}
    for a in db.scalars(select(FitnessAssessment).where(FitnessAssessment.organisation_id == org_id).order_by(FitnessAssessment.assessed_at)):
        out[a.patient_id] = a  # later rows overwrite earlier ones
    return out


def _worker_out(p: Patient, a: FitnessAssessment | None) -> WorkerOut:
    return WorkerOut(
        employee_code=p.employee_code or "", name=p.name, department=p.department, patient_code=p.code,
        fitness_status=a.status if a else "pending_review", restrictions=a.restrictions if a else None, valid_until=a.valid_until if a else None,
        last_assessed_at=a.assessed_at if a else None, assessed_by=a.assessed_by if a else None,
    )


@router.get("/organisations/me", response_model=OrganisationHome)
def home(user: Employer, db: DB):
    org = my_org(db, user)
    facs = list(db.scalars(select(Facility).where(Facility.organisation_id == org.id).order_by(Facility.name)))
    return OrganisationHome(organisation=OrganisationOut.model_validate(org), facilities=[FacilityOut.model_validate(f) for f in facs])


@router.patch("/organisations/me", response_model=OrganisationOut)
def update_org(body: OrganisationPatch, user: Employer, db: DB):
    org = my_org(db, user)
    changed = [k for k, v in body.model_dump(exclude_unset=True).items() if getattr(org, k) != v]
    for k in changed:
        setattr(org, k, getattr(body, k))
    audit.record(db, user, "CONFIG", "organisation", org.id, f"Organisation profile updated: {', '.join(changed) or 'no changes'}")
    db.refresh(org)
    return org


@router.post("/organisations/me/facilities", response_model=FacilityOut)
def add_facility(body: NewFacility, user: Employer, db: DB):
    org = my_org(db, user)
    f = create_org_facility(db, org, body, user.id)
    audit.record(db, user, "CONFIG", "facility", f.id, f"Workplace '{f.name}' ({f.type}) registered by {org.name}", facility_id=f.id)
    return f


@router.get("/organisations/me/workers", response_model=list[WorkerOut])
def workers(user: Employer, db: DB):
    org = my_org(db, user)
    latest = latest_assessments(db, org.id)
    rows = list(db.scalars(select(Patient).where(Patient.organisation_id == org.id).order_by(Patient.department, Patient.employee_code)))
    audit.record(db, user, "VIEW", "organisation", org.id, "Worker roster and fitness status viewed")
    return [_worker_out(p, latest.get(p.id)) for p in rows]


def _upsert_worker(db, org: Organisation, w: WorkerIn) -> tuple[Patient, bool]:
    p = db.scalar(select(Patient).where(Patient.organisation_id == org.id, Patient.employee_code == w.employee_code.strip()))
    if p:
        p.name, p.department = w.name.strip(), w.department or p.department
        if w.phone:
            p.phone = w.phone
        return p, False
    p = Patient(
        code=next_patient_code(db), name=w.name.strip(), age=w.age, sex=w.sex, phone=w.phone, language=w.language, category="normal",
        organisation_id=org.id, employee_code=w.employee_code.strip(), department=w.department,
    )
    db.add(p)
    db.flush()
    return p, True


@router.post("/organisations/me/workers", response_model=WorkerOut)
def add_worker(body: WorkerIn, user: Employer, db: DB):
    org = my_org(db, user)
    p, created = _upsert_worker(db, org, body)
    audit.record(db, user, "CREATE" if created else "UPDATE", "worker", p.id, f"Worker {body.employee_code} {'added to' if created else 'updated in'} roster", p.code)
    return _worker_out(p, latest_assessments(db, org.id).get(p.id))


@router.post("/organisations/me/workers/import", response_model=WorkerImportOut)
def import_workers(body: WorkerImportIn, user: Employer, db: DB):
    """CSV columns: employee_code, name, age, sex, department, phone (header row required)."""
    org = my_org(db, user)
    reader = csv.DictReader(io.StringIO(body.csv.strip()))
    need = {"employee_code", "name", "age", "sex"}
    if not reader.fieldnames or not need.issubset({h.strip().lower() for h in reader.fieldnames}):
        raise HTTPException(422, "CSV needs a header row with at least: employee_code, name, age, sex")
    created = updated = 0
    errors: list[str] = []
    for i, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            w = WorkerIn(
                employee_code=row["employee_code"], name=row["name"], age=int(row["age"]), sex=row["sex"].upper()[:1],
                department=row.get("department") or None, phone=row.get("phone") or None,
            )
            _, was_new = _upsert_worker(db, org, w)
            created += was_new
            updated += not was_new
        except Exception as e:  # report the row and keep going
            errors.append(f"Row {i}: {str(e).splitlines()[0][:120]}")
        if len(errors) > 50:
            errors.append("Stopped after 50 errors")
            break
    audit.record(db, user, "CREATE", "worker", None, f"Roster import: {created} added, {updated} updated, {len(errors)} errors")
    return WorkerImportOut(created=created, updated=updated, errors=errors)


@router.patch("/organisations/me/workers/{code}", response_model=WorkerOut | None)
def update_worker(code: str, body: WorkerPatch, user: Employer, db: DB):
    org = my_org(db, user)
    p = db.scalar(select(Patient).where(Patient.organisation_id == org.id, Patient.employee_code == code))
    if not p:
        raise HTTPException(404, "Worker not found")
    if body.active is False:
        p.organisation_id, p.employee_code = None, None
        audit.record(db, user, "UPDATE", "worker", p.id, f"Worker {code} removed from roster (health record kept)", p.code)
        return None
    for k in ("department", "name", "phone"):
        v = getattr(body, k)
        if v is not None:
            setattr(p, k, v)
    audit.record(db, user, "UPDATE", "worker", p.id, f"Worker {code} updated", p.code)
    return _worker_out(p, latest_assessments(db, org.id).get(p.id))


@router.get("/employer/cohorts", response_model=list[CohortOut])
def cohorts(user: Employer, db: DB):
    """Fitness by department. Status only — never any clinical detail."""
    org = my_org(db, user)
    latest = latest_assessments(db, org.id)
    groups: dict[str, list[dict]] = {}
    for p in db.scalars(select(Patient).where(Patient.organisation_id == org.id).order_by(Patient.employee_code)):
        a = latest.get(p.id)
        groups.setdefault(p.department or "Unassigned", []).append(
            {"worker_code": p.employee_code, "department": p.department or "Unassigned", "fitness_status": a.status if a else "pending_review", "last_screened_at": a.assessed_at.isoformat() if a else None}
        )
    audit.record(db, user, "VIEW", "cohort", org.id, "Employer viewed fitness cohorts (no clinical records)")
    return [CohortOut(id=f"{org.id}:{d}", name=d, employer_name=org.name, screening_type="Occupational fitness", workers=w) for d, w in sorted(groups.items())]
