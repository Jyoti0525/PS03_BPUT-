"""JWT issuance, PIN/OTP hashing and role-based dependencies."""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import RevokedToken, User

bearer = HTTPBearer(auto_error=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_secret(secret: str, salt: str) -> str:
    """PBKDF2-SHA256. For PINs the salt includes the device id, binding the PIN to that device."""
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 200_000)
    return dk.hex()


def verify_secret(secret: str, salt: str, expected: str) -> bool:
    return hmac.compare_digest(hash_secret(secret, salt), expected)


def _encode(payload: dict, ttl: timedelta) -> str:
    s = get_settings()
    now = _now()
    body = {**payload, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    return jwt.encode(body, s.jwt_secret, algorithm=s.jwt_alg)


def decode(token: str, expected_type: str) -> dict:
    s = get_settings()
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_alg])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired — please sign in again")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    if data.get("typ") != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    return data


def issue_tokens(user: User, device_id: str | None = None) -> dict:
    s = get_settings()
    claims = {"sub": user.id, "role": user.role, "fac": user.facility_id, "dev": device_id}
    return {
        "access_token": _encode({**claims, "typ": "access"}, timedelta(minutes=s.access_ttl_min)),
        "refresh_token": _encode({**claims, "typ": "refresh"}, timedelta(days=s.refresh_ttl_days)),
        "token_type": "bearer",
        "expires_in": s.access_ttl_min * 60,
    }


def registration_token(phone: str | None = None, email: str | None = None) -> str:
    """Proof that a new user verified their phone (SMS) or their email; carried into registration."""
    claims = {"typ": "register", **({"phone": phone} if phone else {}), **({"email": email} if email else {})}
    return _encode(claims, timedelta(minutes=get_settings().registration_ttl_min))


PIN_ROLES = {"doctor", "nurse", "receptionist", "supervisor", "employer"}
_WEAK = {"1234", "12345", "123456", "4321", "54321", "654321", "1212", "121212", "1122", "112233", "2580", "0852", "1111", "0000", "123123", "147258", "159753"}


def pin_problem(pin: str) -> str | None:
    """Reject PINs that are trivially guessable."""
    if not pin.isdigit() or not 4 <= len(pin) <= 6:
        return "PIN must be 4 to 6 digits"
    if pin in _WEAK or len(set(pin)) == 1:
        return "That PIN is too easy to guess — choose a less obvious one"
    steps = {int(b) - int(a) for a, b in zip(pin, pin[1:])}
    if steps in ({1}, {-1}):
        return "Avoid sequences like 3456 — choose a less obvious PIN"
    return None


def hash_pin(pin: str, user_id: str) -> str:
    return hash_secret(pin, f"pin:{user_id}")


def pin_step_token(user: "User") -> str:
    """Issued after a successful OTP when the account also needs its PIN. Grants nothing else."""
    return _encode({"typ": "pin", "sub": user.id}, timedelta(minutes=get_settings().pin_step_ttl_min))


def file_token(file_id: str, user_id: str) -> str:
    """Short-lived signed URL token so <img> tags can load a file without an auth header."""
    return _encode({"typ": "file", "fid": file_id, "sub": user_id}, timedelta(minutes=get_settings().file_url_ttl_min))


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    data = decode(creds.credentials, "access")
    if db.get(RevokedToken, data["jti"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended")
    user = db.get(User, data["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
DB = Annotated[Session, Depends(get_db)]
DeviceHeader = Annotated[str | None, Header(alias="X-Device-Id")]


def require(*roles: str):
    allowed = set(roles)

    def dep(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"This action is not available to the {user.role} role")
        return user

    return dep
