"""Encryption at rest for patient identifiers and stored files.

* Fields: `EncryptedStr` columns hold Fernet tokens (AES-128-CBC + HMAC-SHA256) prefixed "enc1:". A value written
  before encryption was switched on has no prefix and is read as it is; `encrypt_existing` rewrites such rows.
* Lookups: a phone number is also stored as `blind(phone)`, an HMAC-SHA256 under a separate derived key, so the
  kiosk can find a patient by phone without the number being readable in the database.
* Files: `seal`/`open_sealed` encrypt the bytes before they reach disk, S3 or Cloudinary; files stored earlier
  (no magic prefix) are read as they are.

The key comes from JEEVIA_DATA_KEY (any secret of 32+ characters). Unset in development, it is derived from the
JWT secret so encryption is still on; production refuses to start without its own key (see config.py).
"""

import base64
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from .config import get_settings

PREFIX = "enc1:"
FILE_MAGIC = b"JVENC1\n"


@lru_cache
def _keys() -> tuple[Fernet, bytes]:
    s = get_settings()
    root = (s.data_key or "dev-data-key:" + s.jwt_secret).encode()
    enc = hashlib.sha256(b"jeevia/fields+files/" + root).digest()
    mac = hashlib.sha256(b"jeevia/blind-index/" + root).digest()
    return Fernet(base64.urlsafe_b64encode(enc)), mac


def encrypt(value: str) -> str:
    return PREFIX + _keys()[0].encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value.startswith(PREFIX):
        return value  # stored before encryption was switched on
    try:
        return _keys()[0].decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        raise ValueError("Encrypted field cannot be read with this JEEVIA_DATA_KEY") from None


def blind(value: str | None) -> str | None:
    """Keyed hash for equality lookups (phone numbers). Same input, same output; not reversible without the key."""
    if not value:
        return None
    return hmac.new(_keys()[1], value.strip().encode(), hashlib.sha256).hexdigest()


def seal(data: bytes) -> bytes:
    return FILE_MAGIC + _keys()[0].encrypt(data)


def open_sealed(data: bytes) -> bytes:
    if not data.startswith(FILE_MAGIC):
        return data  # stored before file encryption
    return _keys()[0].decrypt(data[len(FILE_MAGIC):])


class EncryptedStr(TypeDecorator):
    """A string column stored encrypted. Not searchable in SQL: use a blind index or filter after loading."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or (isinstance(value, str) and value.startswith(PREFIX)):
            return value
        return encrypt(str(value))

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)


def encrypt_existing(db) -> int:
    """Rewrite rows stored before encryption: patient identifiers, proxy names; fill the phone lookup hash."""
    from sqlalchemy import text

    n = 0
    for table, cols in (("patients", ("name", "phone", "village")), ("consents", ("proxy_name",))):
        rows = db.execute(text(f"SELECT id, {', '.join(cols)} FROM {table}")).all()  # nosec B608: fixed names above
        for row in rows:
            vals = dict(zip(cols, row[1:]))
            plain = {c: v for c, v in vals.items() if v is not None and not v.startswith(PREFIX)}
            if table == "patients":
                ph = vals["phone"]
                ph = decrypt(ph) if ph else None
                plain_ph = {"phone_hash": blind(ph)}
            else:
                plain_ph = {}
            if not plain and not (table == "patients" and plain_ph["phone_hash"] and not _has_hash(db, row[0])):
                continue
            sets = {c: encrypt(v) for c, v in plain.items()} | plain_ph
            db.execute(text(f"UPDATE {table} SET " + ", ".join(f"{c} = :{c}" for c in sets) + " WHERE id = :id"), sets | {"id": row[0]})  # nosec B608
            n += 1
    db.commit()
    return n


def _has_hash(db, pid: str) -> bool:
    from sqlalchemy import text

    return bool(db.execute(text("SELECT phone_hash FROM patients WHERE id = :id"), {"id": pid}).scalar())
