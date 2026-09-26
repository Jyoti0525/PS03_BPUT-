"""Public kiosk links and the front-desk token board.

A supervisor issues a link per facility (e.g. /k/7QX4MPA2). Anyone opening it — a waiting-room
tablet, a health worker's phone, a patient's own phone — gets a kiosk session that can only:
register a patient, capture consent, upload files and submit an intake. Each submission gets the
facility's next daily token, which appears immediately in the reviewer queue and the token board.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from .. import audit
from ..config import get_settings
from ..models import Encounter, Facility, KioskLink, Patient, User
from ..schemas import ADMIN_ROLES, STAFF_ROLES, AuthResult, KioskIdentifyIn, KioskInfo, KioskLinkIn, KioskLinkOut, KioskSessionIn, PatientOut, TokenBoardItem
from ..security import DB, CurrentUser, issue_tokens, require
from ..services import local_day, now
from .auth import user_out

router = APIRouter(tags=["kiosk"])
Admin = Annotated[User, Depends(require(*ADMIN_ROLES))]
Kiosk = Annotated[User, Depends(require("kiosk"))]
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I — easy to read aloud


def _link_out(db, k: KioskLink) -> KioskLinkOut:
    day = local_day(now())
    intakes = db.scalar(select(func.count(Encounter.id)).where(Encounter.facility_id == k.facility_id, Encounter.token_date == day, Encounter.channel == "kiosk_link")) or 0
    return KioskLinkOut(
        id=k.id, code=k.code, label=k.label, facility_id=k.facility_id, url=f"{get_settings().web_base_url.rstrip('/')}/k/{k.code}",
        created_by=k.created_by, created_at=k.created_at, revoked=k.revoked, last_used_at=k.last_used_at, sessions=k.sessions, intakes_today=intakes,
    )


def _active(db, code: str) -> KioskLink:
    k = db.scalar(select(KioskLink).where(KioskLink.code == code.strip().upper()))
    if not k or k.revoked:
        raise HTTPException(404, "This kiosk link is not active. Ask the facility for a new one.")
    return k


def create_link(db, facility_id: str, label: str, created_by: User | None, code: str | None = None) -> KioskLink:
    code = code or "".join(secrets.choice(ALPHABET) for _ in range(8))
    kiosk_user = User(phone=f"kiosk-{code}", name=f"Kiosk · {label}", role="kiosk", facility_id=facility_id, language="en")
    db.add(kiosk_user)
    db.flush()
    k = KioskLink(code=code, label=label, facility_id=facility_id, user_id=kiosk_user.id, created_by=created_by.name if created_by else "System")
    db.add(k)
    db.flush()
    return k


# ── Admin ─────────────────────────────────────────────
@router.get("/kiosk-links", response_model=list[KioskLinkOut])
def list_links(user: Admin, db: DB):
    rows = db.scalars(select(KioskLink).where(KioskLink.facility_id == user.facility_id).order_by(KioskLink.created_at.desc()))
    return [_link_out(db, k) for k in rows]


@router.post("/kiosk-links", response_model=KioskLinkOut)
def new_link(body: KioskLinkIn, user: Admin, db: DB):
    k = create_link(db, user.facility_id, body.label.strip(), user)
    audit.record(db, user, "DEVICE", "kiosk_link", k.id, f"Kiosk link '{k.label}' created ({k.code})")
    return _link_out(db, k)


@router.delete("/kiosk-links/{lid}", status_code=204)
def revoke_link(lid: str, user: Admin, db: DB):
    k = db.get(KioskLink, lid)
    if not k or k.facility_id != user.facility_id:
        raise HTTPException(404, "Kiosk link not found")
    k.revoked = True
    ku = db.get(User, k.user_id)
    if ku:
        ku.is_active = False  # ends every open session on that link
    audit.record(db, user, "DEVICE", "kiosk_link", k.id, f"Kiosk link '{k.label}' revoked")


# ── Public kiosk ──────────────────────────────────────
@router.get("/kiosk/{code}", response_model=KioskInfo)
def kiosk_info(code: str, db: DB):
    k = _active(db, code)
    f = db.get(Facility, k.facility_id)
    return KioskInfo(code=k.code, label=k.label, facility_id=f.id, facility_name=f.name, district=f.district, state=f.state, languages=f.languages)


@router.post("/kiosk/{code}/session", response_model=AuthResult)
def kiosk_session(code: str, body: KioskSessionIn, db: DB):
    k = _active(db, code)
    ku = db.get(User, k.user_id)
    if not ku or not ku.is_active:
        raise HTTPException(404, "This kiosk link is not active.")
    k.sessions += 1
    k.last_used_at = now()
    audit.record(db, ku, "LOGIN", "kiosk_link", k.id, f"Kiosk session opened on device {body.device_id[:12]}")
    return AuthResult(tokens=issue_tokens(ku, body.device_id), user=user_out(db, ku))


@router.post("/kiosk/identify", response_model=PatientOut)
def identify(body: KioskIdentifyIn, user: Kiosk, db: DB):
    """Returning patient: both the ID on their old token and their phone must match. No search, no lists."""
    p = db.scalar(select(Patient).where(Patient.code.ilike(body.patient_code.strip()), Patient.phone == body.phone))
    if not p:
        raise HTTPException(404, "No match — check the ID and phone, or register as new")
    audit.record(db, user, "VIEW", "patient", p.id, "Returning patient identified at kiosk (ID + phone)", p.code)
    return p


# ── Token board (front desk) ──────────────────────────
@router.get("/facilities/{fid}/tokens", response_model=list[TokenBoardItem])
def token_board(fid: str, user: CurrentUser, db: DB):
    if user.role not in STAFF_ROLES or user.facility_id != fid:
        raise HTTPException(403, "Not allowed")
    day = local_day(now())
    t = now()
    rows = db.scalars(select(Encounter).where(Encounter.facility_id == fid, Encounter.token_date == day).order_by(Encounter.created_at.desc()))
    return [
        TokenBoardItem(
            encounter_id=e.id, token=e.token, patient_name=e.patient.name, patient_code=e.patient.code, status=e.status, channel=e.channel,
            created_at=e.created_at, wait_minutes=max(0, round((t - e.created_at).total_seconds() / 60)),
        )
        for e in rows
    ]
