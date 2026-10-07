"""Vonage: the same reminder call and SMS as Twilio (telephony.py), for accounts on Vonage's free trial, which calls
and texts the number the account was registered with and needs no bought number.

* Voice API: a call is created with a JWT signed by the Vonage application's private key; Vonage asks our answer URL
  for an NCCO (the list of things to do on the call): play each agent line (Sarvam's voice), then wait for one key
  (1 yes, 2 no, 3 not sure) or record the free answer. Every webhook carries the call's own token.
* SMS API: plain key and secret. On the trial Vonage adds "[FREE SMS DEMO, TEST MESSAGE]" to each text.

Plain REST over httpx; PyJWT (with cryptography) signs the RS256 token. No Vonage package.
"""

import logging
import time
import uuid
from functools import lru_cache
from pathlib import Path

import httpx
import jwt

from . import calls
from .config import get_settings

log = logging.getLogger("jeevia.vonage")
VOICE = "https://api.nexmo.com/v1/calls"
SMS = "https://rest.nexmo.com/sms/json"
DIAL_FAILED = ("busy", "failed", "timeout", "unanswered", "rejected", "cancelled")
ENDED = ("completed", *DIAL_FAILED)


def private_key() -> bytes | None:
    path = get_settings().vonage_private_key_path
    if not path:
        return None
    p = Path(path) if Path(path).is_absolute() else Path(__file__).resolve().parents[1] / path
    return _read(str(p))


@lru_cache
def _read(path: str) -> bytes | None:
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def _jwt() -> str:
    s = get_settings()
    key = private_key()
    if not (s.vonage_application_id and key):
        from .telephony import TelephonyUnavailable

        raise TelephonyUnavailable("The Vonage application is not set up")
    now = int(time.time())
    return jwt.encode({"application_id": s.vonage_application_id, "iat": now, "exp": now + 300, "jti": uuid.uuid4().hex}, key, algorithm="RS256")


def _number(e164: str) -> str:
    return e164.lstrip("+")


def _call(method: str, url: str, **kw) -> httpx.Response:
    from .telephony import TelephonyUnavailable

    try:
        r = httpx.request(method, url, headers={"Authorization": f"Bearer {_jwt()}"}, timeout=15, **kw)
    except httpx.HTTPError as e:
        raise TelephonyUnavailable("Could not reach Vonage") from e
    if r.status_code >= 400:
        detail = r.json().get("title", "") if r.headers.get("content-type", "").startswith("application/json") else ""
        log.warning("vonage error", extra={"status": r.status_code})
        raise TelephonyUnavailable(f"Vonage error {r.status_code}: {detail}".rstrip(": "))
    return r


# ── calls ─────────────────────────────────────────────
def url(path: str, call_id: str | None = None) -> str:
    from .telephony import url as base_url

    return base_url(f"vonage/{path}", call_id)


def place_call(call_id: str) -> str:
    s = get_settings()
    body = {
        "to": [{"type": "phone", "number": _number(s.telephony_demo_to)}],
        "from": {"type": "phone", "number": s.vonage_from_number},
        "answer_url": [url(f"calls/{call_id}/answer", call_id)], "answer_method": "GET",
        "event_url": [url(f"calls/{call_id}/event", call_id)], "event_method": "POST",
        "ringing_timer": 30,
    }
    return _call("POST", VOICE, json=body).json()["uuid"]


def end_call(call_uuid: str) -> None:
    _call("PUT", f"{VOICE}/{call_uuid}", json={"action": "hangup"})


def fetch_recording(recording_url: str) -> bytes:
    return _call("GET", recording_url).content


def delete_recording(recording_url: str) -> None:
    """Ask Vonage to delete the patient's voice once transcribed (it keeps none past 30 days either way)."""
    from .telephony import TelephonyUnavailable

    try:
        _call("DELETE", recording_url)
    except TelephonyUnavailable:
        log.warning("could not delete a Vonage recording")


def ncco(call, played: int) -> tuple[list[dict], int]:
    """Play the agent lines not yet played, then wait for one key, or record the free answer, or end the call."""
    from .telephony import url as base_url

    turns = call.turns or []
    out = [{"action": "stream", "streamUrl": [base_url(f"calls/{call.id}/turns/{i}/audio", call.id)]}
           for i in range(played, len(turns)) if turns[i].get("who") == "agent"]
    if call.status != "active":
        return out, len(turns)  # the call ends when the list runs out
    if calls.asks_yes_no(call):
        out.append({"action": "stream", "streamUrl": [base_url(f"prompts/{call.language}/keypad")], "bargeIn": True})
        out.append({"action": "input", "type": ["dtmf"], "dtmf": {"maxDigits": 1, "timeOut": 10},
                    "eventUrl": [url(f"calls/{call.id}/keys", call.id)], "eventMethod": "POST"})
    else:
        out.append({"action": "stream", "streamUrl": [base_url(f"prompts/{call.language}/after_beep")]})
        out.append({"action": "record", "format": "mp3", "beepStart": True, "endOnSilence": 3, "timeOut": 30,
                    "eventUrl": [url(f"calls/{call.id}/recording", call.id)], "eventMethod": "POST"})
        # The recording arrives separately; this short wait asks us what comes next once it has been read
        out.append({"action": "input", "type": ["dtmf"], "dtmf": {"maxDigits": 1, "timeOut": 2},
                    "eventUrl": [url(f"calls/{call.id}/after_record", call.id)], "eventMethod": "POST"})
    return out, len(turns)


# ── SMS ───────────────────────────────────────────────
def send_sms(body: str) -> str:
    from .telephony import TelephonyUnavailable

    s = get_settings()
    data = {"api_key": s.vonage_api_key, "api_secret": s.vonage_api_secret, "to": _number(s.telephony_demo_to),
            "from": s.vonage_sms_from, "text": body, "type": "text" if body.isascii() else "unicode"}  # unicode halves an SMS
    try:
        r = httpx.post(SMS, data=data, timeout=15)
    except httpx.HTTPError as e:
        raise TelephonyUnavailable("Could not reach Vonage") from e
    msg = (r.json().get("messages") or [{}])[0] if r.status_code < 400 else {}
    if msg.get("status") != "0":
        raise TelephonyUnavailable(f"Vonage SMS error: {msg.get('error-text') or r.status_code}")
    return msg.get("message-id", "")
