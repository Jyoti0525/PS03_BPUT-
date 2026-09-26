import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from .. import audit
from ..config import get_settings
from ..models import Facility, OtpChallenge, Patient, RevokedToken, User, UserPin
from ..schemas import AuthResult, OtpChallengeOut, OtpRequest, OtpVerify, OtpVerifyOut, PinLogin, PinSet, RefreshIn, RegisterIn, UserOut
from .. import otp
from ..security import DB, CurrentUser, bearer, decode, hash_secret, issue_tokens, registration_token, verify_secret
from ..services import aware, next_patient_code, now

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(db, u: User) -> UserOut:
    has_pin = db.scalar(select(UserPin.id).where(UserPin.user_id == u.id)) is not None
    return UserOut.model_validate({**{c: getattr(u, c) for c in ("id", "phone", "name", "role", "facility_id", "registration_no", "language")}, "has_pin": has_pin, "created_at": aware(u.created_at)})


@router.post("/otp/request", response_model=OtpChallengeOut)
def request_otp(body: OtpRequest, db: DB):
    s = get_settings()
    local = otp.uses_local_code(body.phone)
    code = otp.local_code(body.phone) if local else ""
    if not local:
        otp.send(body.phone)
    ch = OtpChallenge(phone=body.phone, code_hash=hash_secret(code, body.phone) if local else "twilio", expires_at=now() + timedelta(seconds=s.otp_ttl_sec))
    db.add(ch)
    db.commit()
    # The code is only returned for local-dev mock mode; sample accounts are documented separately.
    return OtpChallengeOut(challenge_id=ch.id, expires_in=s.otp_ttl_sec, dev_code=code if s.otp_provider == "mock" else None)


@router.post("/otp/verify", response_model=OtpVerifyOut, response_model_exclude_none=True)
def verify_otp(body: OtpVerify, db: DB):
    s = get_settings()
    ch = db.get(OtpChallenge, body.challenge_id)
    if not ch or ch.consumed or aware(ch.expires_at) < now():
        raise HTTPException(400, "OTP expired — request a new one")
    if ch.attempts >= s.otp_max_attempts:
        raise HTTPException(429, "Too many attempts — request a new OTP")
    ok = otp.check(ch.phone, body.code) if ch.code_hash == "twilio" else verify_secret(body.code, ch.phone, ch.code_hash)
    if not ok:
        ch.attempts += 1
        db.commit()
        raise HTTPException(400, "Incorrect OTP")
    ch.consumed = True
    db.commit()
    user = db.scalar(select(User).where(User.phone == ch.phone))
    if not user:
        return OtpVerifyOut(status="new_user", registration_token=registration_token(ch.phone))
    audit.record(db, user, "LOGIN", "user", user.id, "Signed in with phone + OTP")
    return OtpVerifyOut(status="authenticated", tokens=issue_tokens(user), user=user_out(db, user))


@router.post("/register", response_model=AuthResult)
def register(body: RegisterIn, db: DB):
    phone = decode(body.registration_token, "register")["phone"]
    if not body.accepted_terms:
        raise HTTPException(422, "Terms must be accepted")
    if db.scalar(select(User).where(User.phone == phone)):
        raise HTTPException(409, "This phone is already registered")
    if body.role == "supervisor" and body.new_facility and not body.facility_id:
        nf = body.new_facility
        slug = "".join(ch for ch in nf.name.lower() if ch.isalnum())[:20] or "facility"
        fac = Facility(
            id=f"fac_{slug}_{uuid.uuid4().hex[:6]}", name=nf.name.strip(), type=nf.type, district=nf.district.strip(), state=nf.state.strip(),
            languages=[body.language, "en"] if body.language != "en" else ["en", "hi"],
            specialists=[{"key": "genmed", "label": "General Medicine", "available": True, "schedule": None}],
            referral_destination=nf.referral_destination or "", beds_total=0, beds_occupied=0, offline_mode=nf.type == "health_camp", capabilities={},
        )
        db.add(fac)
        db.flush()
        body.facility_id = fac.id
    if body.role not in ("patient",) and not body.facility_id:
        raise HTTPException(422, "Staff must select a facility")
    if body.facility_id and not db.get(Facility, body.facility_id):
        raise HTTPException(422, "Unknown facility")
    if body.role in ("doctor", "nurse") and not (body.registration_no and len(body.registration_no.strip()) >= 4):
        raise HTTPException(422, "Registration number is required for clinical staff")
    user = User(phone=phone, name=body.name.strip(), role=body.role, facility_id=body.facility_id if body.role != "patient" else None, registration_no=body.registration_no, language=body.language)
    db.add(user)
    db.flush()
    if body.role == "patient" and not db.scalar(select(Patient).where(Patient.phone == phone, Patient.name == user.name)):
        db.add(Patient(code=next_patient_code(db), name=user.name, age=30, sex="O", phone=phone, language=body.language, category="normal"))
    audit.record(db, user, "CREATE", "user", user.id, f"Registered as {body.role}; terms accepted")
    return AuthResult(tokens=issue_tokens(user, body.device_id), user=user_out(db, user))


@router.post("/pin", status_code=204)
def set_pin(body: PinSet, user: CurrentUser, db: DB):
    pin = db.scalar(select(UserPin).where(UserPin.user_id == user.id, UserPin.device_id == body.device_id))
    h = hash_secret(body.pin, f"{user.id}:{body.device_id}")
    if pin:
        pin.pin_hash, pin.failed_attempts = h, 0
    else:
        db.add(UserPin(user_id=user.id, device_id=body.device_id, pin_hash=h))
    audit.record(db, user, "DEVICE", "user", user.id, "PIN set and bound to this device")


@router.post("/pin/login", response_model=AuthResult)
def pin_login(body: PinLogin, db: DB):
    user = db.scalar(select(User).where(User.phone == body.phone))
    pin = user and db.scalar(select(UserPin).where(UserPin.user_id == user.id, UserPin.device_id == body.device_id))
    if not user or not pin:
        raise HTTPException(400, "PIN login is not set up on this device — use OTP")
    if pin.failed_attempts >= 5:
        raise HTTPException(429, "PIN locked after 5 failed attempts — sign in with OTP")
    if not verify_secret(body.pin, f"{user.id}:{body.device_id}", pin.pin_hash):
        pin.failed_attempts += 1
        db.commit()
        raise HTTPException(400, "Incorrect PIN")
    pin.failed_attempts = 0
    audit.record(db, user, "LOGIN", "user", user.id, "Signed in with device-bound PIN")
    return AuthResult(tokens=issue_tokens(user, body.device_id), user=user_out(db, user))


@router.post("/refresh")
def refresh(body: RefreshIn, db: DB):
    data = decode(body.refresh_token, "refresh")
    if db.get(RevokedToken, data["jti"]):
        raise HTTPException(401, "Session ended")
    user = db.get(User, data["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "Account not found")
    db.add(RevokedToken(jti=data["jti"]))  # rotate: each refresh token works once
    db.commit()
    return issue_tokens(user, data.get("dev"))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser, db: DB):
    return user_out(db, user)


@router.post("/logout", status_code=204)
def logout(user: CurrentUser, db: DB, creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    db.add(RevokedToken(jti=decode(creds.credentials, "access")["jti"]))
    audit.record(db, user, "LOGIN", "user", user.id, "Signed out; session token revoked")
