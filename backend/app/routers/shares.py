"""QR summary links for referral hand-off.

A reviewer creates a link for one encounter. The QR encodes only the link (a random token);
opening it also requires the 6-digit access code printed next to the QR, so a photographed QR
alone is not enough. Links expire, can be revoked, lock after repeated wrong codes, and every
opening is written to the audit log. Documents are served through short-lived signed URLs.
"""

import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from .. import audit
from ..config import get_settings
from ..exports import DISCLAIMER
from ..models import Facility, FileObject, Referral, ShareLink, User
from ..schemas import REVIEWER_ROLES, SharedDocument, SharedSummary, ShareIn, ShareOpenIn, ShareOut
from ..security import DB, file_token, hash_secret, require, verify_secret
from ..services import load_encounter, now

router = APIRouter(tags=["shares"])
Reviewer = Annotated[User, Depends(require(*REVIEWER_ROLES))]
MAX_FAILED = 8


def _out(s: ShareLink, code: str | None = None) -> ShareOut:
    return ShareOut(
        id=s.id, url=f"{get_settings().web_base_url.rstrip('/')}/s/{s.token}", access_code=code, purpose=s.purpose,
        created_by=s.created_by, created_at=s.created_at, expires_at=s.expires_at, revoked=s.revoked, views=s.views,
    )


@router.post("/encounters/{eid}/shares", response_model=ShareOut)
def create_share(eid: str, body: ShareIn, user: Reviewer, db: DB):
    e = load_encounter(db, eid, user)
    code = f"{secrets.randbelow(10**6):06d}"
    token = secrets.token_urlsafe(24)
    s = ShareLink(token=token, code_hash=hash_secret(code, token), encounter_id=e.id, purpose=body.purpose, created_by=user.name, expires_at=now() + timedelta(hours=body.hours))
    db.add(s)
    db.flush()
    audit.record(db, user, "EXPORT", "share", s.id, f"QR summary link created ({body.purpose}, valid {body.hours}h)", e.patient.code, e.facility_id)
    return _out(s, code)


@router.get("/encounters/{eid}/shares", response_model=list[ShareOut])
def list_shares(eid: str, user: Reviewer, db: DB):
    load_encounter(db, eid, user)
    return [_out(s) for s in db.scalars(select(ShareLink).where(ShareLink.encounter_id == eid).order_by(ShareLink.created_at.desc()))]


@router.delete("/shares/{sid}", status_code=204)
def revoke_share(sid: str, user: Reviewer, db: DB):
    s = db.get(ShareLink, sid)
    if not s or s.encounter.facility_id != user.facility_id:
        raise HTTPException(404, "Share link not found")
    s.revoked = True
    audit.record(db, user, "UPDATE", "share", s.id, "QR summary link revoked", s.encounter.patient.code, user.facility_id)


def _active(db, token: str) -> ShareLink:
    s = db.scalar(select(ShareLink).where(ShareLink.token == token))
    if not s or s.revoked:
        raise HTTPException(404, "This summary link is not valid.")
    if s.expires_at < now():
        raise HTTPException(410, "This summary link has expired. Ask the referring facility for a new one.")
    if s.failed_attempts >= MAX_FAILED:
        raise HTTPException(423, "Locked after too many wrong codes. Ask the referring facility for a new link.")
    return s


@router.get("/share/{token}")
def share_meta(token: str, db: DB):
    """Public: enough to show the code prompt, nothing clinical."""
    s = _active(db, token)
    f = db.get(Facility, s.encounter.facility_id)
    return {"facility_name": f.name if f else "", "purpose": s.purpose, "expires_at": s.expires_at}


@router.post("/share/{token}/open", response_model=SharedSummary)
def open_share(token: str, body: ShareOpenIn, request: Request, db: DB):
    s = _active(db, token)
    if not verify_secret(body.access_code, s.token, s.code_hash):
        s.failed_attempts += 1
        db.commit()
        left = MAX_FAILED - s.failed_attempts
        raise HTTPException(403, f"Wrong access code. {left} attempt{'s' if left != 1 else ''} left.")
    s.views += 1
    e = s.encounter
    f = db.get(Facility, e.facility_id)
    ref = db.scalar(select(Referral).where(Referral.encounter_id == e.id).order_by(Referral.created_at.desc()))
    files = [x for x in db.scalars(select(FileObject).where(FileObject.encounter_id == e.id, FileObject.kind != "audio"))]
    docs = []
    for x in files:
        url = None
        if not x.purged_at and x.expires_at > now():
            url = str(request.url_for("file_content", fid=x.id)) + f"?sig={file_token(x.id, 'share:' + s.id)}"
        docs.append(SharedDocument(id=x.id, filename=x.filename, kind=x.kind, content_type=x.content_type, uploaded_at=x.uploaded_at, url=url))
    note = None
    if e.note:
        n = e.note
        note = {k: n.get(k) for k in ("summary", "flags", "vitals", "labs", "timeline", "missing_info", "disagreements", "rules_fired")}
    audit.record(db, None, "VIEW", "share", s.id, f"QR summary opened (view {s.views}) from {request.client.host if request.client else 'unknown'}", e.patient.code, e.facility_id)
    p = e.patient
    return SharedSummary(
        facility={"name": f.name, "district": f.district, "state": f.state, "type": f.type} if f else {},
        patient={"name": p.name, "code": p.code, "age": p.age, "sex": p.sex, "language": p.language, "phone": p.phone},
        encounter={
            "token": e.token, "created_at": e.created_at, "category": e.category, "chief_complaint": e.chief_complaint, "status": e.status,
            "urgency": e.urgency, "urgency_source": e.urgency_source, "override": e.override, "reviewed_by": e.reviewed_by, "reviewed_at": e.reviewed_at,
            "maternal": (e.intake or {}).get("maternal"), "chronic": (e.intake or {}).get("chronic"),
            "consent": {"mode": e.consent.mode, "proxy_name": e.consent.proxy_name, "proxy_relation": e.consent.proxy_relation} if e.consent else None,
        },
        note=note,
        referral={"destination": ref.destination, "specialty": ref.specialty, "reason": ref.reason, "transport": ref.transport, "created_by": ref.created_by, "created_at": ref.created_at, "note_text": ref.note_text} if ref else None,
        documents=docs,
        shared_by=s.created_by,
        expires_at=s.expires_at,
        disclaimer=DISCLAIMER,
    )
