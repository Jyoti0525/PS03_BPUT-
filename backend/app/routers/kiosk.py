"""Public kiosk links and the front-desk token board.

A supervisor issues a link per facility (e.g. /k/7QX4MPA2). Anyone opening it — a waiting-room
tablet, a health worker's phone, a patient's own phone — gets a kiosk session that can only:
register a patient, capture consent, upload files and submit an intake. Each submission gets the
facility's next daily token, which appears immediately in the reviewer queue and the token board.

A link marked for_home is the one the facility shares for filling in before coming (SMS, poster, website). Its
intakes get an H- reference and wait on the token board as "expected"; they join the queue, with a T- token, when the
desk checks the patient in, so filling in early never moves anyone ahead of people already waiting (C3).
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select

from .. import audit
from ..config import get_settings
from ..crypto import blind
from ..ratelimit import limit, per_phone
from ..models import Encounter, Facility, KioskLink, Organisation, Patient, User
from ..schemas import ADMIN_ROLES, STAFF_ROLES, AuthResult, KioskFinderHit, KioskIdentifyIn, KioskInfo, KioskLinkIn, KioskLinkOut, KioskSessionIn, PatientOut, TokenBoardItem
from ..security import DB, CurrentUser, issue_tokens, require
from ..services import lapse_expected, local_day, now, wait_minutes
from .auth import user_out

router = APIRouter(tags=["kiosk"])
Admin = Annotated[User, Depends(require(*ADMIN_ROLES))]
Supervisor = Annotated[User, Depends(require("supervisor"))]
Kiosk = Annotated[User, Depends(require("kiosk"))]
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I — easy to read aloud


def _link_out(db, k: KioskLink) -> KioskLinkOut:
    day = local_day(now())
    intakes = db.scalar(select(func.count(Encounter.id)).where(Encounter.facility_id == k.facility_id, Encounter.token_date == day,
                                                         Encounter.channel.in_(("kiosk_link", "home_link")))) or 0
    return KioskLinkOut(
        id=k.id, code=k.code, label=k.label, facility_id=k.facility_id, url=f"{get_settings().web_base_url.rstrip('/')}/k/{k.code}",
        created_by=k.created_by, created_at=k.created_at, revoked=k.revoked, last_used_at=k.last_used_at, sessions=k.sessions, intakes_today=intakes,
        for_home=bool(k.for_home),
    )


def _active(db, code: str) -> KioskLink:
    k = db.scalar(select(KioskLink).where(KioskLink.code == code.strip().upper()))
    if not k or k.revoked:
        raise HTTPException(404, "This kiosk link is not active. Ask the facility for a new one.")
    return k


def create_link(db, facility_id: str, label: str, created_by: User | None, code: str | None = None, for_home: bool = False) -> KioskLink:
    code = code or "".join(secrets.choice(ALPHABET) for _ in range(8))
    kiosk_user = User(phone=f"kiosk-{code}", name=f"Kiosk · {label}", role="kiosk", facility_id=facility_id, language="en")
    db.add(kiosk_user)
    db.flush()
    k = KioskLink(code=code, label=label, facility_id=facility_id, user_id=kiosk_user.id, created_by=created_by.name if created_by else "System",
                   for_home=for_home)
    db.add(k)
    db.flush()
    return k


def ensure_any_centre(db) -> None:
    """The "fill in now, take it to any centre" link (/k/ANYCARE). Its facility is a holder, never a workplace: it is
    hidden from search, cannot be joined, and its intakes move to whichever facility claims the reference."""
    from ..services import ANY_FACILITY, ANY_LINK

    if not db.get(Facility, ANY_FACILITY):
        db.add(Facility(id=ANY_FACILITY, name="Any health centre", type="any_centre", district="", state="India", languages=["or", "hi", "en"],
                        specialists=[], source="system", offline_mode=False))
        db.flush()
    if not db.scalar(select(KioskLink).where(KioskLink.code == ANY_LINK)):
        create_link(db, ANY_FACILITY, "Fill in now, take it to any centre", None, code=ANY_LINK, for_home=True)
    db.commit()


# ── Admin ─────────────────────────────────────────────
@router.get("/kiosk-links", response_model=list[KioskLinkOut])
def list_links(user: Supervisor, db: DB):
    rows = db.scalars(select(KioskLink).where(KioskLink.facility_id == user.facility_id).order_by(KioskLink.created_at.desc()))
    return [_link_out(db, k) for k in rows]


@router.post("/kiosk-links", response_model=KioskLinkOut)
def new_link(body: KioskLinkIn, user: Supervisor, db: DB):
    k = create_link(db, user.facility_id, body.label.strip(), user, for_home=body.for_home)
    audit.record(db, user, "DEVICE", "kiosk_link", k.id, f"Kiosk link '{k.label}' created ({k.code}){' for filling in from home' if k.for_home else ''}")
    return _link_out(db, k)


@router.delete("/kiosk-links/{lid}", status_code=204)
def revoke_link(lid: str, user: Supervisor, db: DB):
    k = db.get(KioskLink, lid)
    if not k or k.facility_id != user.facility_id:
        raise HTTPException(404, "Kiosk link not found")
    k.revoked = True
    ku = db.get(User, k.user_id)
    if ku:
        ku.is_active = False  # ends every open session on that link
    audit.record(db, user, "DEVICE", "kiosk_link", k.id, f"Kiosk link '{k.label}' revoked")


# ── Public kiosk ──────────────────────────────────────
@router.get("/kiosk-finder", response_model=list[KioskFinderHit], dependencies=[Depends(limit("public"))])
def kiosk_finder(db: DB, q: str = "", lat: float | None = None, lon: float | None = None):
    """For a patient who has no code: nearby health facilities, nearest first when the browser shares a location.

    Facilities on Jeevia with a from-home link come with that link's code (fill in before going). Every other facility
    from the national directory (115k, OpenStreetMap) is listed too, without a code, so the patient still sees the
    nearest place to walk in. Only from-home links are offered, never a waiting-room link, so a form sent from
    anywhere waits for desk check-in and never moves ahead of people already waiting."""
    import math
    import re

    from ..directory import KIND_LABEL
    from ..models import DirectoryFacility

    def km(a, b):
        if lat is None or lon is None or a is None or b is None:
            return None
        p1, p2, dl = math.radians(lat), math.radians(a), math.radians(b - lon)
        return round(6371 * math.acos(max(-1.0, min(1.0, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))), 1)

    tokens = [t for t in re.split(r"[\s,]+", q.lower()) if t][:5]
    pin = next((t for t in tokens if re.fullmatch(r"\d{6}", t)), None)
    words = [t for t in tokens if t != pin]
    if not tokens and (lat is None or lon is None):
        return []

    hits: dict[str, KioskFinderHit] = {}
    for k, f in db.execute(select(KioskLink, Facility).join(Facility, Facility.id == KioskLink.facility_id)
                           .where(KioskLink.for_home.is_(True), KioskLink.revoked.is_(False), Facility.source != "system")).all():
        hay = " ".join(x or "" for x in (f.name, f.district, f.state, f.pincode, f.type)).lower()
        if (pin and f.pincode != pin) or not all(w in hay for w in words):
            continue
        d = km(f.lat, f.lon)
        if not tokens and (d is None or d > 50):
            continue
        hits.setdefault(f.directory_ref or f.id, KioskFinderHit(code=k.code, facility_name=f.name, facility_type=f.type, district=f.district,
                                                                state=f.state, pincode=f.pincode, km=d))

    dq = select(DirectoryFacility)
    if pin:
        dq = dq.where(DirectoryFacility.pincode == pin)
    for w in words:
        like = f"%{w}%"
        dq = dq.where(func.lower(DirectoryFacility.name).like(like) | func.lower(func.coalesce(DirectoryFacility.district, "")).like(like)
                      | func.lower(func.coalesce(DirectoryFacility.city, "")).like(like))
    if lat is not None and lon is not None:
        box = 0.25 if tokens else 0.15  # about 25 km / 15 km
        for r in (0, 1, 2):  # widen until something is found (remote villages)
            rows = db.scalars(dq.where(DirectoryFacility.lat.between(lat - box, lat + box), DirectoryFacility.lon.between(lon - box, lon + box)).limit(400)).all()
            if rows or tokens:
                break
            box *= 2.5
        if not rows and tokens:
            rows = db.scalars(dq.limit(200)).all()
    else:
        exact = [w for w in words if len(w) > 2]
        if exact:  # a place name typed: centres in that district or town first, then anything that merely contains it
            place = or_(*[func.lower(func.coalesce(DirectoryFacility.district, "")) == w for w in exact],
                        *[func.lower(func.coalesce(DirectoryFacility.city, "")) == w for w in exact])
            rows = db.scalars(dq.where(place).limit(200)).all() or db.scalars(dq.limit(200)).all()
        else:
            rows = db.scalars(dq.limit(200)).all()
    for r in rows:
        if r.ref in hits:
            continue
        hits[r.ref] = KioskFinderHit(code=None, facility_name=r.name, facility_type=KIND_LABEL.get(r.kind, r.kind), district=r.district or "",
                                     state=r.state, pincode=r.pincode, km=km(r.lat, r.lon), phone=r.phone, lat=r.lat, lon=r.lon)
    out = sorted(hits.values(), key=lambda h: (h.km is None, h.km if h.km is not None else 0, h.code is None, h.facility_name))
    return out[:25]


@router.get("/kiosk/{code}", response_model=KioskInfo, dependencies=[Depends(limit("public"))])
def kiosk_info(code: str, db: DB):
    k = _active(db, code)
    f = db.get(Facility, k.facility_id)
    org = db.get(Organisation, f.organisation_id) if f.organisation_id else None
    return KioskInfo(code=k.code, label=k.label, facility_id=f.id, facility_name=f.name, organisation_name=org.name if org else None, district=f.district, state=f.state, languages=f.languages,
                     for_home=bool(k.for_home))


@router.post("/kiosk/{code}/session", response_model=AuthResult, dependencies=[Depends(limit("public"))])
def kiosk_session(code: str, body: KioskSessionIn, db: DB):
    k = _active(db, code)
    ku = db.get(User, k.user_id)
    if not ku or not ku.is_active:
        raise HTTPException(404, "This kiosk link is not active.")
    k.sessions += 1
    k.last_used_at = now()
    audit.record(db, ku, "LOGIN", "kiosk_link", k.id, f"Kiosk session opened on device {body.device_id[:12]}")
    return AuthResult(tokens=issue_tokens(ku, body.device_id), user=user_out(db, ku))


@router.post("/kiosk/identify", response_model=PatientOut, dependencies=[Depends(limit("public"))])
def identify(body: KioskIdentifyIn, user: Kiosk, db: DB):
    """Returning patient: both the ID on their old token and their phone must match. No search, no lists."""
    per_phone(body.phone, "kiosk-identify")
    p = db.scalar(select(Patient).where(Patient.code.ilike(body.patient_code.strip()), Patient.phone_hash == blind(body.phone)))
    if not p:
        raise HTTPException(404, "No match — check the ID and phone, or register as new")
    audit.record(db, user, "VIEW", "patient", p.id, "Returning patient identified at kiosk (ID + phone)", p.code)
    return p


# ── Token board (front desk) ──────────────────────────
@router.get("/facilities/{fid}/tokens", response_model=list[TokenBoardItem])
def token_board(fid: str, user: CurrentUser, db: DB):
    if user.role not in STAFF_ROLES or user.facility_id != fid:
        raise HTTPException(403, "Not allowed")
    lapse_expected(db, fid)
    day = local_day(now())
    t = now()
    # today's tokens, plus intakes sent from home (since yesterday) whose patient has not been checked in yet
    rows = db.scalars(select(Encounter).where(Encounter.facility_id == fid, (Encounter.token_date == day) | (Encounter.status == "expected"))
                      .order_by(Encounter.created_at.desc()))
    return [
        TokenBoardItem(
            encounter_id=e.id, token=e.token, patient_id=e.patient_id, patient_name=e.patient.name, patient_code=e.patient.code, status=e.status, channel=e.channel,
            created_at=e.created_at, arrived_at=e.arrived_at, wait_minutes=0 if e.status == "expected" else wait_minutes(e, t),
        )
        for e in rows
    ]
