import secrets
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_, select

from .. import audit
from ..config import get_settings
from ..ratelimit import limit
from ..models import Facility, Organisation, OtpChallenge, RevokedToken, User
from ..schemas import ORG_FACILITY_TYPES, AuthResult, OtpChallengeOut, OtpRequest, OtpVerify, OtpVerifyOut, PinChangeIn, PinForgotIn, PinStepIn, AuthOptions, EmailConfirmIn, EmailStartIn, MePatch, RefreshIn, RegisterIn, UserOut
from .. import directory, mailer, otp
from ..security import PIN_ROLES, DB, CurrentUser, bearer, decode, hash_pin, hash_secret, issue_tokens, pin_problem, pin_step_token, registration_token, verify_secret
from ..services import aware, now
from .organisations import create_org_facility

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(db, u: User) -> UserOut:
    has_pin = u.pin_hash is not None
    return UserOut.model_validate({**{c: getattr(u, c) for c in ("id", "phone", "name", "role", "facility_id", "registration_no", "language", "is_active", "organisation_id", "on_duty", "email", "phone_verified")}, "has_pin": has_pin, "duty_changed_at": aware(u.duty_changed_at) if u.duty_changed_at else None, "created_at": aware(u.created_at)})


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "unknown")[:64]


def _wait_text(seconds: int) -> str:
    minutes = max(1, -(-seconds // 60))
    if minutes < 90:
        return f"about {minutes} minute{'s' if minutes != 1 else ''}"
    hours = round(minutes / 60)
    return f"about {hours} hour{'s' if hours != 1 else ''}"


def _limit(db, query, t, window: timedelta, allowed: int, message: str) -> None:
    """Refuse when `allowed` requests already fall inside the rolling window, saying exactly when to retry."""
    times = sorted(aware(x) for x in db.scalars(query.where(OtpChallenge.created_at > t - window)))
    if len(times) < allowed:
        return
    # A slot frees up when the oldest request that still counts leaves the window.
    free_at = times[len(times) - allowed] + window if allowed > 0 else t + window
    wait = max(1, int((free_at - t).total_seconds()))
    raise HTTPException(429, f"{message} — try again in {_wait_text(wait)}", headers={"Retry-After": str(wait)})


@router.get("/options", response_model=AuthOptions)
def options():
    """Which code channels this server offers (the sign-in page shows the email option only when enabled)."""
    return AuthOptions(sms=True, email=mailer.enabled())


@router.post("/otp/request", response_model=OtpChallengeOut)
def request_otp(body: OtpRequest, request: Request, db: DB):
    if body.email:
        return _request_email_code(db, request, body.email, body.purpose, lang=body.language)
    s = get_settings()
    t = now()
    ip = _client_ip(request)
    # Rate limits protect people from SMS spam and the SMS account from abuse. Sample numbers never send an SMS,
    # so they are exempt from every limit and do not count towards a network's allowance either.
    if not otp.is_demo(body.phone):
        by_phone = select(OtpChallenge.created_at).where(OtpChallenge.phone == body.phone)
        _limit(db, by_phone, t, timedelta(minutes=10), s.otp_per_phone_10min, "Too many codes requested for this number")
        _limit(db, by_phone, t, timedelta(hours=24), s.otp_per_phone_day, "Too many codes requested for this number today")
        _limit(db, _network_query(ip), t, timedelta(hours=1), s.otp_per_ip_hour, "Too many code requests from this network")
    local = otp.uses_local_code(body.phone)
    code = otp.local_code(body.phone) if local else ""
    if not local:
        otp.send(body.phone)
    ch = OtpChallenge(phone=body.phone, code_hash=hash_secret(code, body.phone) if local else "twilio", expires_at=t + timedelta(seconds=s.otp_ttl_sec), created_at=t, ip=ip)
    db.add(ch)
    db.commit()
    # The code is only returned for local-dev mock mode; sample accounts are documented separately.
    return OtpChallengeOut(challenge_id=ch.id, expires_in=s.otp_ttl_sec, dev_code=code if s.otp_provider == "mock" else None)


def _network_query(ip: str):
    q = select(OtpChallenge.created_at).where(OtpChallenge.ip == ip)
    demo = otp.demo_phones()
    return q.where(or_(OtpChallenge.phone.is_(None), OtpChallenge.phone.not_in(demo))) if demo else q


def _request_email_code(db, request: Request, email: str, purpose: str, user_id: str | None = None, lang: str | None = None) -> OtpChallengeOut:
    """Email codes follow the same limits as SMS: per address, per day and per network."""
    s = get_settings()
    if not mailer.enabled():
        raise HTTPException(503, "Email codes are not enabled on this server")
    t = now()
    ip = _client_ip(request)
    by_email = select(OtpChallenge.created_at).where(OtpChallenge.email == email)
    _limit(db, by_email, t, timedelta(minutes=10), s.otp_per_phone_10min, "Too many codes requested for this email")
    _limit(db, by_email, t, timedelta(hours=24), s.otp_per_phone_day, "Too many codes requested for this email today")
    _limit(db, _network_query(ip), t, timedelta(hours=1), s.otp_per_ip_hour, "Too many code requests from this network")
    code = f"{secrets.randbelow(10**6):06d}"
    # Greet the person by name, in their own language, when the address belongs to an account.
    owner = db.get(User, user_id) if user_id else db.scalar(select(User).where(User.email == email, User.email_verified_at.is_not(None)))
    mailer.send_code(email, code, purpose, name=owner.name if owner else None, lang=(owner.language if owner else None) or lang or "en")
    ch = OtpChallenge(email=email, user_id=user_id, code_hash=hash_secret(code, email), expires_at=t + timedelta(seconds=s.otp_ttl_sec), created_at=t, ip=ip)
    db.add(ch)
    db.commit()
    return OtpChallengeOut(challenge_id=ch.id, expires_in=s.otp_ttl_sec, dev_code=code if s.email_provider == "mock" else None)


def _check_challenge(db, challenge_id: str, code: str) -> OtpChallenge:
    s = get_settings()
    ch = db.get(OtpChallenge, challenge_id)
    if not ch or ch.consumed or aware(ch.expires_at) < now():
        raise HTTPException(400, "OTP expired — request a new one")
    if ch.attempts >= s.otp_max_attempts:
        raise HTTPException(429, "Too many attempts — request a new OTP")
    if ch.email:
        ok = verify_secret(code, ch.email, ch.code_hash)
    else:
        ok = otp.check(ch.phone, code) if ch.code_hash == "twilio" else verify_secret(code, ch.phone, ch.code_hash)
    if not ok:
        ch.attempts += 1
        db.commit()
        raise HTTPException(400, "Incorrect OTP")
    ch.consumed = True
    db.commit()
    return ch


@router.post("/otp/verify", response_model=OtpVerifyOut, response_model_exclude_none=True, dependencies=[Depends(limit("auth"))])
def verify_otp(body: OtpVerify, db: DB):
    ch = _check_challenge(db, body.challenge_id, body.code)
    if ch.user_id:
        raise HTTPException(400, "This code confirms an email address — use it on the email screen")
    if ch.email:
        user = db.scalar(select(User).where(User.email == ch.email, User.email_verified_at.is_not(None)))
    else:
        user = db.scalar(select(User).where(User.phone == ch.phone))
    if not user:
        if ch.phone and otp.is_demo(ch.phone):
            raise HTTPException(403, "Sample numbers are reserved for the walkthrough — register with your own mobile number")
        return OtpVerifyOut(status="new_user", registration_token=registration_token(phone=ch.phone, email=ch.email))
    if body.purpose == "register":
        what = "email address" if ch.email else "mobile number"
        raise HTTPException(409, f"This {what} is already registered. Each {what} can hold only one account — sign in instead, or register with your own {what}.")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated — contact your supervisor")
    if user.role in PIN_ROLES:
        # Second factor: the account PIN. No session is issued until it is entered.
        status = "pin_required" if user.pin_hash else "pin_setup_required"
        return OtpVerifyOut(status=status, pin_token=pin_step_token(user), name=user.name, can_reset_pin=user.role in ("supervisor", "employer"))
    audit.record(db, user, "LOGIN", "user", user.id, "Signed in with phone + OTP")
    return OtpVerifyOut(status="authenticated", tokens=issue_tokens(user), user=user_out(db, user))


def _pin_user(db, pin_token: str) -> User:
    user = db.get(User, decode(pin_token, "pin")["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "Account not found")
    return user


def _set_pin(user: User, pin: str) -> None:
    problem = pin_problem(pin)
    if problem:
        raise HTTPException(422, problem)
    user.pin_hash, user.pin_set_at, user.pin_failed_attempts, user.pin_locked_until = hash_pin(pin, user.id), now(), 0, None


@router.post("/pin/verify", response_model=AuthResult, dependencies=[Depends(limit("auth"))])
def pin_verify(body: PinStepIn, db: DB):
    """Step 2 of sign-in for staff and employers."""
    s = get_settings()
    user = _pin_user(db, body.pin_token)
    if not user.pin_hash:
        raise HTTPException(409, "Set up your PIN first")
    if user.pin_locked_until and user.pin_locked_until > now():
        mins = max(1, int((user.pin_locked_until - now()).total_seconds() // 60) + 1)
        raise HTTPException(423, f"PIN locked after too many wrong tries — try again in {mins} min")
    if not verify_secret(body.pin, f"pin:{user.id}", user.pin_hash):
        user.pin_failed_attempts += 1
        left = s.pin_max_attempts - user.pin_failed_attempts
        if left <= 0:
            user.pin_locked_until = now() + timedelta(minutes=s.pin_lock_minutes)
            user.pin_failed_attempts = 0
            audit.record(db, user, "LOGIN", "user", user.id, f"PIN locked for {s.pin_lock_minutes} min after repeated wrong PINs")
            raise HTTPException(423, f"PIN locked for {s.pin_lock_minutes} minutes after too many wrong tries")
        db.commit()
        raise HTTPException(400, f"Incorrect PIN — {left} {'try' if left == 1 else 'tries'} left")
    user.pin_failed_attempts, user.pin_locked_until = 0, None
    audit.record(db, user, "LOGIN", "user", user.id, "Signed in with phone OTP + PIN")
    return AuthResult(tokens=issue_tokens(user), user=user_out(db, user))


@router.post("/pin/setup", response_model=AuthResult)
def pin_setup(body: PinStepIn, db: DB):
    """First sign-in without a PIN (older accounts, or after a PIN reset): choose one now."""
    user = _pin_user(db, body.pin_token)
    if user.pin_hash:
        raise HTTPException(409, "A PIN is already set — enter it instead")
    _set_pin(user, body.pin)
    audit.record(db, user, "LOGIN", "user", user.id, "PIN created; signed in with phone OTP + PIN")
    return AuthResult(tokens=issue_tokens(user), user=user_out(db, user))


@router.post("/pin/forgot", response_model=OtpVerifyOut, response_model_exclude_none=True, dependencies=[Depends(limit("auth"))])
def pin_forgot(body: PinForgotIn, db: DB):
    """Supervisors and employers can reset their own PIN after OTP; other staff ask their supervisor."""
    user = _pin_user(db, body.pin_token)
    if user.role not in ("supervisor", "employer"):
        raise HTTPException(403, "Ask your facility supervisor to reset your PIN")
    user.pin_hash, user.pin_failed_attempts, user.pin_locked_until = None, 0, None
    audit.record(db, user, "UPDATE", "user", user.id, "PIN reset by the account holder after phone OTP")
    return OtpVerifyOut(status="pin_setup_required", pin_token=pin_step_token(user), name=user.name, can_reset_pin=True)


@router.post("/pin/change", status_code=204, dependencies=[Depends(limit("auth"))])
def pin_change(body: PinChangeIn, user: CurrentUser, db: DB):
    if user.role not in PIN_ROLES:
        raise HTTPException(403, "This account does not use a PIN")
    if not user.pin_hash or not verify_secret(body.current_pin, f"pin:{user.id}", user.pin_hash):
        raise HTTPException(400, "Current PIN is incorrect")
    if body.new_pin == body.current_pin:
        raise HTTPException(422, "Choose a different PIN")
    _set_pin(user, body.new_pin)
    audit.record(db, user, "UPDATE", "user", user.id, "PIN changed from the dashboard")


@router.post("/register", response_model=AuthResult, dependencies=[Depends(limit("auth"))])
def register(body: RegisterIn, db: DB):
    claims = decode(body.registration_token, "register")
    email = claims.get("email")
    phone = claims.get("phone") or body.phone
    if not phone:
        raise HTTPException(422, "Enter your 10-digit mobile number")
    if not body.accepted_terms:
        raise HTTPException(422, "Terms must be accepted")
    if db.scalar(select(User).where(User.phone == phone)):
        raise HTTPException(409, "This mobile number is already registered — sign in instead")
    if email and db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "This email address is already registered — sign in instead")
    if otp.is_demo(phone):
        raise HTTPException(403, "Sample numbers are reserved for the walkthrough")
    org_id = None
    if body.role == "employer":
        # An employer registers their organisation and its first workplace; only then does that
        # workplace appear in the list for doctors, nurses and front-desk staff.
        if not body.new_organisation:
            raise HTTPException(422, "Register your organisation to continue")
        no = body.new_organisation
        org = Organisation(name=no.name.strip(), kind=no.kind, registration_no=no.registration_no, state=no.state.strip(), district=no.district.strip(), address=no.address, contact_phone=no.contact_phone)
        db.add(org)
        db.flush()
        fac = create_org_facility(db, org, no.facility, created_by=phone)
        body.facility_id, org_id = fac.id, org.id
    else:
        chosen = sum(x is not None for x in (body.facility_id, body.directory_ref, body.new_facility))
        if chosen != 1:
            raise HTTPException(422, "Choose your workplace")
        if body.directory_ref:
            try:
                body.facility_id = directory.activate(db, body.directory_ref, created_by=phone).id
            except LookupError as e:
                raise HTTPException(422, str(e))
        elif body.new_facility:
            if body.role != "supervisor":
                raise HTTPException(403, "Only a supervisor can add a missing facility")
            nf = body.new_facility
            if nf.type in ORG_FACILITY_TYPES:
                raise HTTPException(422, "Company clinics, industrial units, campus centres and camps are added by their organisation")
            slug = "".join(ch for ch in nf.name.lower() if ch.isalnum())[:20] or "facility"
            fac = Facility(
                id=f"fac_{slug}_{uuid.uuid4().hex[:6]}", name=nf.name.strip(), type=nf.type, district=nf.district.strip(), state=nf.state.strip(),
                languages=[body.language, "en"] if body.language != "en" else ["en", "hi"],
                specialists=[{"key": "genmed", "label": "General Medicine", "available": True, "schedule": None}],
                referral_destination=nf.referral_destination or "", beds_total=0, beds_occupied=0, offline_mode=False, capabilities={},
                source="user_added", verified=False, pincode=nf.pincode, address=nf.address, created_by=phone,
            )
            db.add(fac)
            db.flush()
            body.facility_id = fac.id
        else:
            fac = db.get(Facility, body.facility_id)
            if not fac:
                raise HTTPException(422, "Unknown facility")
            if fac.source == "system":
                raise HTTPException(403, "Choose your real workplace")
            if fac.source == "sample":
                raise HTTPException(403, "This is a sample facility for the walkthrough — choose your real workplace")
    if body.role in PIN_ROLES:
        if not body.pin:
            raise HTTPException(422, "Choose a PIN to protect your account")
        problem = pin_problem(body.pin)
        if problem:
            raise HTTPException(422, problem)
    if body.role in ("doctor", "medical_officer", "nurse") and not (body.registration_no and len(body.registration_no.strip()) >= 4):
        raise HTTPException(422, "Registration number is required for clinical staff")
    user = User(phone=phone, name=body.name.strip(), role=body.role, facility_id=body.facility_id, registration_no=body.registration_no, language=body.language, organisation_id=org_id)
    if email:  # verified by an email code; the mobile number was typed, not verified
        user.email, user.email_verified_at, user.phone_verified = email, now(), False
    db.add(user)
    db.flush()
    if body.role in PIN_ROLES:
        _set_pin(user, body.pin)
    audit.record(db, user, "CREATE", "user", user.id, f"Registered as {body.role}; terms accepted")
    return AuthResult(tokens=issue_tokens(user, body.device_id), user=user_out(db, user))


@router.post("/refresh", dependencies=[Depends(limit("auth"))])
def refresh(body: RefreshIn, db: DB):
    data = decode(body.refresh_token, "refresh")
    if db.get(RevokedToken, data["jti"]):
        raise HTTPException(401, "Session ended")
    user = db.get(User, data["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "Account not found")
    db.add(RevokedToken(jti=data["jti"]))  # rotate: each refresh token works once
    try:
        db.commit()
    except IntegrityError:  # the same token used twice at once: only the first wins
        db.rollback()
        raise HTTPException(401, "Session ended")
    return issue_tokens(user, data.get("dev"))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser, db: DB):
    return user_out(db, user)


@router.post("/email/start", response_model=OtpChallengeOut)
def email_start(body: EmailStartIn, request: Request, user: CurrentUser, db: DB):
    """Add or change the account's email: a code is sent to the new address."""
    email = body.email.strip().lower()
    other = db.scalar(select(User).where(User.email == email))
    if other and other.id != user.id:
        raise HTTPException(409, "This email address is already used by another account")
    return _request_email_code(db, request, email, "add", user_id=user.id, lang=body.language or user.language)


@router.post("/email/confirm", response_model=UserOut, dependencies=[Depends(limit("auth"))])
def email_confirm(body: EmailConfirmIn, user: CurrentUser, db: DB):
    ch = _check_challenge(db, body.challenge_id, body.code)
    if ch.user_id != user.id or not ch.email:
        raise HTTPException(400, "This code was not issued for your account")
    if db.scalar(select(User).where(User.email == ch.email, User.id != user.id)):
        raise HTTPException(409, "This email address is already used by another account")
    user.email, user.email_verified_at = ch.email, now()
    audit.record(db, user, "UPDATE", "user", user.id, "Email address verified and added to the account")
    return user_out(db, user)


@router.delete("/email", response_model=UserOut)
def email_remove(user: CurrentUser, db: DB):
    if user.email:
        user.email, user.email_verified_at = None, None
        audit.record(db, user, "UPDATE", "user", user.id, "Email address removed from the account")
    return user_out(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(body: MePatch, user: CurrentUser, db: DB):
    """Own preferences. The language is applied to every screen whenever this user signs in."""
    if body.language and body.language != user.language:
        user.language = body.language
        audit.record(db, user, "UPDATE", "user", user.id, f"Preferred language set to {body.language}")
    return user_out(db, user)


@router.post("/logout", status_code=204)
def logout(user: CurrentUser, db: DB, creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    db.add(RevokedToken(jti=decode(creds.credentials, "access")["jti"]))
    audit.record(db, user, "LOGIN", "user", user.id, "Signed out; session token revoked")
