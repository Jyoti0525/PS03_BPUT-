"""Patients (identity + household disambiguation) and consent capture (G1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select

from .. import audit
from ..models import Consent, Encounter, Patient, User
from ..schemas import ADMIN_ROLES, STAFF_ROLES, ConsentIn, ConsentOut, EncounterOut, PatientCandidate, PatientIn, PatientOut
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
    p = Patient(code=next_patient_code(db), **body.model_dump())
    db.add(p)
    db.flush()
    audit.record(db, user, "CREATE", "patient", p.id, "Patient registered at intake", p.code)
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
