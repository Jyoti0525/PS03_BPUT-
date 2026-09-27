"""One-time-password delivery.

* mock   — code is generated locally and returned to the client (local development only).
* twilio — Twilio Verify sends and checks the code; Jeevia never sees it.

Sample accounts listed in JEEVIA_DEMO_PHONES keep working with JEEVIA_DEMO_OTP so the
walkthrough accounts can be used without a real handset.
"""

import logging
import secrets

import httpx
from fastapi import HTTPException

from .config import get_settings

log = logging.getLogger("jeevia.otp")
VERIFY = "https://verify.twilio.com/v2/Services"


def is_demo(phone: str) -> bool:
    s = get_settings()
    return bool(s.demo_otp) and phone in {p.strip() for p in s.demo_phones.split(",") if p.strip()}


def uses_local_code(phone: str) -> bool:
    return get_settings().otp_provider != "twilio" or is_demo(phone)


def _twilio_auth() -> tuple[str, str]:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_verify_service_sid and ((s.twilio_api_key_sid and s.twilio_api_key_secret))):
        raise HTTPException(503, "SMS provider is not configured")
    return s.twilio_api_key_sid, s.twilio_api_key_secret  # type: ignore[return-value]


def local_code(phone: str) -> str:
    s = get_settings()
    if is_demo(phone) or (s.otp_provider == "mock" and s.demo_otp):
        return s.demo_otp  # type: ignore[return-value]
    return f"{secrets.randbelow(10**6):06d}"


def send(phone: str) -> None:
    """Ask Twilio Verify to text a code to the phone."""
    s = get_settings()
    try:
        r = httpx.post(
            f"{VERIFY}/{s.twilio_verify_service_sid}/Verifications",
            data={"To": f"{s.sms_country_code}{phone}", "Channel": "sms"},
            auth=_twilio_auth(),
            timeout=15,
        )
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the SMS provider — try again")
    if r.status_code >= 400:
        log.warning("twilio send failed", extra={"status": r.status_code})
        detail = r.json().get("message", "SMS could not be sent") if r.headers.get("content-type", "").startswith("application/json") else "SMS could not be sent"
        raise HTTPException(502, f"SMS provider error: {detail}")


def check(phone: str, code: str) -> bool:
    s = get_settings()
    try:
        r = httpx.post(
            f"{VERIFY}/{s.twilio_verify_service_sid}/VerificationCheck",
            data={"To": f"{s.sms_country_code}{phone}", "Code": code},
            auth=_twilio_auth(),
            timeout=15,
        )
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the SMS provider — try again")
    if r.status_code == 404:  # expired or already used
        return False
    if r.status_code >= 400:
        raise HTTPException(502, "SMS provider error")
    return r.json().get("status") == "approved"
