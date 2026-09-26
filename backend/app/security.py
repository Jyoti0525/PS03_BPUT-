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


def registration_token(phone: str) -> str:
    return _encode({"typ": "register", "phone": phone}, timedelta(minutes=get_settings().registration_ttl_min))


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
