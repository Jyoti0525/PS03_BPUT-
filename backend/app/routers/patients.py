"""Patients (identity + household disambiguation) and consent capture (G1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select

from .. import audit
from ..models import Consent, Encounter, Facility, Patient, User
from ..schemas import ADMIN_ROLES, STAFF_ROLES, ConsentIn, ConsentOut, EncounterOut, PatientCandidate, PatientIn, PatientOut, PatientPatch
from ..security import DB, CurrentUser, require
from ..services import aware, encounter_out, next_patient_code, own_patient

router = APIRouter(tags=["patients"])
Staff = Annotated[User, Depends(require(*STAFF_ROLES))]
Registrar = Annotated[User, Depends(require(*STAFF_ROLES, "kiosk"))]


def _check_patient_access(db, user: User, p: Patient, *, kiosk_ok: bool = False):
    if user.role == "kiosk" and kiosk_ok:
        return
    if user.role == "patient":
        mine = own_patient(db, user)
        if not mine or mine.id != p.id:
            raise HTTPException(403, "Not your record")
    elif user.role not in STAFF_ROLES:
        raise HTTPException(403, "Not allowed")


@router.get("/patients", response_model=list[PatientCandidate])
def search(q: str, user: Staff, db: DB):
    s = q.strip().lower().replace(" ", "").replace("+91", "")
    if not s:
        return []
    like = f"%{s}%"
    rows = list(db.scalars(select(Patient).where(or_(Patient.code.ilike(like), Patient.phone.like(like), Patient.name.ilike(f"%{q.strip()}%"))).limit(20)))
    audit.record(db, user, "VIEW", "patient_search", None, f'Searched patients: "{q}" ({len(rows)} candidates)')
    out = []
    for p in rows:
        last = db.scalar(select(Encounter.created_at).where(Encounter.patient_id == p.id).order_by(Encounter.created_at.desc()).limit(1))
        reason = "Exact patient ID" if p.code.lower() == s else "Shared household phone" if p.phone and s in p.phone else "Name match"
        out.append(PatientCandidate(patient=PatientOut.model_validate(p), last_visit_at=aware(last), match_reason=reason))
    return out


@router.get("/patients/by-code/{code}", response_model=PatientOut)
def by_code(code: str, user: Staff, db: DB):
    p = db.scalar(select(Patient).where(Patient.code.ilike(code.strip())))
    if not p:
        raise HTTPException(404, f"No patient with ID {code}")
    audit.record(db, user, "VIEW", "patient", p.id, "Patient opened by ID / QR scan", p.code)
    return p


@router.post("/patients", response_model=PatientOut)
def create_patient(body: PatientIn, user: Registrar, db: DB):
    data = body.model_dump(exclude={"employee_code"})
    fac = db.get(Facility, user.facility_id) if user.facility_id else None
    code = (body.employee_code or "").strip()
    if code and fac and fac.organisation_id:
        # Worker check-in at an organisation's workplace: link to the roster entry if it is the same person.
        existing = db.scalar(select(Patient).where(Patient.organisation_id == fac.organisation_id, Patient.employee_code == code))
        if existing:
            same = (body.phone and existing.phone == body.phone) or existing.name.strip().lower() == body.name.strip().lower()
            if not same:
                raise HTTPException(409, "That employee code belongs to someone else — check it or leave it blank")
            audit.record(db, user, "VIEW", "patient", existing.id, f"Worker {code} matched at check-in", existing.code)
            return existing
        data.update(organisation_id=fac.organisation_id, employee_code=code)
    p = Patient(code=next_patient_code(db), **data)
    db.add(p)
    db.flush()
    audit.record(db, user, "CREATE", "patient", p.id, "Patient registered at intake", p.code)
    return p


@router.patch("/patients/{pid}", response_model=PatientOut)
def correct_patient(pid: str, body: PatientPatch, user: Staff, db: DB):
    """Front desk or clinicians correct identity details (name, age, sex, phone, language, village)."""
    p = db.get(Patient, pid)
    if not p:
        raise HTTPException(404, "Patient not found")
    seen_here = db.scalar(select(Encounter.id).where(Encounter.patient_id == pid, Encounter.facility_id == user.facility_id).limit(1))
    if not seen_here:
        raise HTTPException(403, "Only facilities that have seen this patient can correct their details")
    changed = [k for k, v in body.model_dump(exclude_unset=True).items() if v is not None and getattr(p, k) != v]
    for k in changed:
        setattr(p, k, getattr(body, k))
    audit.record(db, user, "UPDATE", "patient", pid, f"Patient details corrected: {', '.join(changed) or 'no changes'}", p.code)
    return p


@router.get("/patients/{pid}", response_model=PatientOut)
def get_patient(pid: str, user: CurrentUser, db: DB):
    p = db.get(Patient, pid)
    if not p:
        raise HTTPException(404, "Patient not found")
    _check_patient_access(db, user, p)
    audit.record(db, user, "VIEW", "patient", pid, "Patient identity viewed", p.code)
    return p


@router.get("/patients/{pid}/encounters", response_model=list[EncounterOut])
def patient_encounters(pid: str, user: CurrentUser, db: DB):
    if user.role in ADMIN_ROLES:
        raise HTTPException(403, "Facility admins cannot read clinical records")
    p = db.get(Patient, pid)
    if not p:
        raise HTTPException(404, "Patient not found")
    _check_patient_access(db, user, p)
    rows = list(db.scalars(select(Encounter).where(Encounter.patient_id == pid).order_by(Encounter.created_at.desc())))
    audit.record(db, user, "VIEW", "patient", pid, f"Encounter history viewed ({len(rows)})", p.code)
    return [encounter_out(e, user) for e in rows]


@router.post("/consents", response_model=ConsentOut)
def capture_consent(body: ConsentIn, user: CurrentUser, db: DB):
    p = db.get(Patient, body.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    _check_patient_access(db, user, p, kiosk_ok=True)
    if body.mode == "proxy" and not (body.proxy_name and body.proxy_relation):
        raise HTTPException(422, "Proxy name and relationship are required")
    c = Consent(**body.model_dump(), captured_by=user.name)
    db.add(c)
    db.flush()
    who = f"Proxy consent by {body.proxy_name} ({body.proxy_relation})" if body.mode == "proxy" else "Self consent"
    audit.record(db, user, "CONSENT", "consent", c.id, f"{who}; privacy: {body.privacy_context}; scopes: {', '.join(body.scopes)}", p.code)
    return c
