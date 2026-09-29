"""Email one-time codes (optional second channel next to SMS).

* none  — email sign-in is switched off (default).
* mock  — the code is returned to the client (local development and tests only).
* brevo — Brevo transactional email API (https://api.brevo.com/v3/smtp/email). The API key lives only
          in the server environment (JEEVIA_BREVO_API_KEY); the sender must be verified in Brevo.
"""

import logging

import httpx
from fastapi import HTTPException

from .config import get_settings

log = logging.getLogger("jeevia.mail")
BREVO = "https://api.brevo.com/v3/smtp/email"

SUBJECT = {"signin": "Your Jeevia sign-in code", "register": "Verify your email for Jeevia", "add": "Confirm your email for Jeevia"}


def enabled() -> bool:
    s = get_settings()
    return s.email_provider == "mock" or (s.email_provider == "brevo" and bool(s.brevo_api_key and s.email_from))


def send_code(email: str, code: str, purpose: str = "signin") -> None:
    s = get_settings()
    if s.email_provider == "mock":
        log.info("mock email code issued")
        return
    if not enabled():
        raise HTTPException(503, "Email codes are not enabled on this server")
    minutes = max(1, s.otp_ttl_sec // 60)
    text = f"Your Jeevia code is {code}. It expires in {minutes} minutes. Never share it — Jeevia staff will never ask for it."
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;color:#1b1d2e">'
        '<h2 style="margin:0 0 12px">Jeevia</h2>'
        f"<p>Your one-time code is</p><p style=\"font-size:32px;font-weight:700;letter-spacing:6px;margin:8px 0 16px\">{code}</p>"
        f"<p>It expires in {minutes} minutes. If you did not ask for it, you can ignore this email.</p>"
        '<p style="color:#6b6f80;font-size:12px">Never share this code. Jeevia staff will never ask for it.</p></div>'
    )
    body = {
        "sender": {"name": s.email_from_name, "email": s.email_from},
        "to": [{"email": email}],
        "subject": SUBJECT.get(purpose, SUBJECT["signin"]),
        "htmlContent": html,
        "textContent": text,
        "tags": ["jeevia-otp"],
    }
    try:
        r = httpx.post(BREVO, json=body, headers={"api-key": s.brevo_api_key or "", "accept": "application/json"}, timeout=15)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the email provider — try again")
    if r.status_code >= 400:
        log.warning("brevo send failed", extra={"status": r.status_code})
        raise HTTPException(502, "The email could not be sent — check the address or try again")
