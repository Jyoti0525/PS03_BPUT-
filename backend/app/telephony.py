"""Reminder calls over a real phone line, and reminder SMS, through Twilio or Vonage (E6, E5).

The call is the same call as in the browser (calls.py): the same fixed lines, the same rules, the same hand-over to a
person. Only the channel changes. The provider rings the phone and plays each agent line, spoken by Sarvam's voice;
the patient answers yes / no / not sure on the keypad (1 / 2 / 3), which needs no speech recognition and works on any
phone. The last question ("anything else for the nurse?") is recorded, transcribed and translated, read by the same
danger-sign rules, and the recording is deleted straight after (Twilio; Vonage is asked to, and keeps none past
30 days).

Vonage (vonage.py) is used when its application is set: its free trial calls and texts the account's own number,
which is all a demo needs. Twilio's trial needs a bought number.

Safety and privacy:
* Every call and SMS goes to one demo number (JEEVIA_TELEPHONY_DEMO_TO), never to a patient's stored number: demo
  patients are synthetic and their numbers may belong to real people. Unset = nothing is ever dialled or sent.
* Webhooks carry a per-call token in the URL (HMAC of the call id); Twilio's are also checked against the
  X-Twilio-Signature (HMAC with the account's auth token).
* An SMS never names a pregnancy or a condition.

Plain REST over httpx, like otp.py; no Twilio package.
"""

import base64
import hashlib
import hmac
import logging
from xml.sax.saxutils import escape

import httpx

from . import calls
from .config import get_settings

log = logging.getLogger("jeevia.telephony")
API = "https://api.twilio.com/2010-04-01/Accounts"
DIAL_FAILED = ("busy", "no-answer", "failed", "canceled")
ENDED = ("completed", *DIAL_FAILED)
KEYPAD = {"1": "Yes", "2": "No", "3": "Not sure"}


class TelephonyUnavailable(Exception):
    pass


# ── set-up ────────────────────────────────────────────
def _auth() -> tuple[str, str] | None:
    s = get_settings()
    if not s.twilio_account_sid:
        return None
    if s.twilio_api_key_sid and s.twilio_api_key_secret:
        return s.twilio_api_key_sid, s.twilio_api_key_secret
    return (s.twilio_account_sid, s.twilio_auth_token) if s.twilio_auth_token else None


def provider() -> str:
    """vonage when its API key is set, else twilio."""
    s = get_settings()
    return "vonage" if s.vonage_api_key and s.vonage_api_secret else "twilio"


def _needs() -> list[tuple[str, object]]:
    from . import sarvam, vonage

    s = get_settings()
    common = [("JEEVIA_TELEPHONY_DEMO_TO", s.telephony_demo_to)]
    voice = [("JEEVIA_PUBLIC_BASE_URL", s.public_base_url), ("SARVAM_API_KEY (the voice)", sarvam.enabled())]
    if provider() == "vonage":
        return common + [("JEEVIA_VONAGE_APPLICATION_ID", s.vonage_application_id), ("the Vonage private key file", vonage.private_key())] + voice
    return common + [("JEEVIA_TWILIO_ACCOUNT_SID and an API key or JEEVIA_TWILIO_AUTH_TOKEN", _auth()),
                     ("JEEVIA_TWILIO_FROM_NUMBER", s.twilio_from_number)] + [
        ("JEEVIA_TWILIO_AUTH_TOKEN (checks webhooks)", s.twilio_auth_token)] + voice


def sms_ready() -> bool:
    s = get_settings()
    if not s.telephony_demo_to:
        return False
    return True if provider() == "vonage" else bool(_auth() and s.twilio_from_number)


def calls_ready() -> bool:
    """Phone calls also need a public address for the provider's webhooks, a way to check them, and a voice."""
    return all(ok for _, ok in _needs())


def status() -> dict:
    s = get_settings()
    return {"calls": calls_ready(), "sms": sms_ready(), "demo_to": mask(s.telephony_demo_to), "provider": provider(),
            "missing": [name for name, ok in _needs() if not ok]}


def mask(number: str | None) -> str | None:
    return f"…{number[-4:]}" if number else None


def _post(path: str, data: dict) -> dict:
    s = get_settings()
    auth = _auth()
    if not auth:
        raise TelephonyUnavailable("Twilio is not configured")
    try:
        r = httpx.post(f"{API}/{s.twilio_account_sid}/{path}", data=data, auth=auth, timeout=15)
    except httpx.HTTPError as e:
        raise TelephonyUnavailable("Could not reach Twilio") from e
    if r.status_code >= 400:
        detail = r.json().get("message", "") if r.headers.get("content-type", "").startswith("application/json") else ""
        log.warning("twilio error", extra={"path": path.split("/")[0], "status": r.status_code})
        raise TelephonyUnavailable(f"Twilio error {r.status_code}: {detail}".rstrip(": "))
    return r.json()


# ── webhooks: who is calling us ───────────────────────
def token(call_id: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), f"twilio:{call_id}".encode(), hashlib.sha256).hexdigest()[:32]


def check_token(call_id: str, t: str | None) -> bool:
    return bool(t) and hmac.compare_digest(token(call_id), t)


def valid_signature(url: str, params: dict, signature: str | None) -> bool:
    """Twilio's request signature: base64(HMAC-SHA1(auth token, URL + each POST param name and value, sorted))."""
    key = get_settings().twilio_auth_token
    if not (key and signature):
        return False
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    expected = base64.b64encode(hmac.new(key.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature)


def url(path: str, call_id: str | None = None) -> str:
    base = (get_settings().public_base_url or "").rstrip("/")
    return f"{base}/api/v1/telephony/{path}" + (f"?t={token(call_id)}" if call_id else "")


# ── placing a call, sending an SMS ────────────────────
def place_call(call_id: str) -> str:
    s = get_settings()
    if not calls_ready():
        raise TelephonyUnavailable("Phone calls are not set up: " + "; ".join(status()["missing"]))
    if provider() == "vonage":
        from . import vonage

        return vonage.place_call(call_id)
    out = _post("Calls.json", {
        "To": s.telephony_demo_to, "From": s.twilio_from_number, "Url": url(f"calls/{call_id}/voice", call_id), "Method": "POST",
        "StatusCallback": url(f"calls/{call_id}/status", call_id), "StatusCallbackMethod": "POST", "StatusCallbackEvent": "completed",
        "Timeout": "30",
    })
    return out["sid"]


def end_call(sid: str) -> None:
    if provider() == "vonage":
        from . import vonage

        return vonage.end_call(sid)
    _post(f"Calls/{sid}.json", {"Status": "completed"})


def send_sms(body: str) -> str:
    s = get_settings()
    if not sms_ready():
        raise TelephonyUnavailable("SMS is not set up: " + "; ".join(status()["missing"]))
    if provider() == "vonage":
        from . import vonage

        return vonage.send_sms(body)
    return _post("Messages.json", {"To": s.telephony_demo_to, "From": s.twilio_from_number, "Body": body})["sid"]


def fetch_recording(recording_url: str) -> bytes:
    try:
        r = httpx.get(f"{recording_url}.mp3", auth=_auth(), timeout=20, follow_redirects=True)
    except httpx.HTTPError as e:
        raise TelephonyUnavailable("Could not fetch the recording") from e
    if r.status_code >= 400:
        raise TelephonyUnavailable(f"Recording not available ({r.status_code})")
    return r.content


def delete_recording(recording_url: str) -> None:
    """The patient's voice is not kept anywhere once it is transcribed."""
    try:
        httpx.delete(f"{recording_url}.json", auth=_auth(), timeout=15)
    except httpx.HTTPError:
        log.warning("could not delete a Twilio recording")


# ── what Twilio says and does on the call (TwiML) ─────
def sms_text(lang: str, audience: str, ctx: dict) -> str:
    """The patient's reminder, signed by the health centre (the other-phone text already says who it is from)."""
    if audience != "self":
        return calls.config()["sms"]["other"][lang].format(**ctx)
    return calls.config()["sms"]["self"][lang].format(**ctx) + f" - {ctx['facility']}"


def staff_alert_text(outcome: str, patient_code: str, facility: str, at) -> str:
    """For the medical officer and the health worker: plain characters, one SMS (160) with room for a trial suffix.
    The patient's code and what to do; never a name or a symptom."""
    from zoneinfo import ZoneInfo

    when = at.astimezone(ZoneInfo(get_settings().timezone)).strftime("%H:%M")
    what = "Danger sign" if outcome == "danger_sign" else "No clear answer"
    act = "Call back now and record the action in Jeevia." if outcome == "danger_sign" else "A person must call back now."
    return f"JEEVIA ALERT: {what} on reminder call. Patient {patient_code}, {facility}, {when}. {act}"


def twiml(call, played: int) -> tuple[str, int]:
    """Play the agent lines not yet played, then collect the next answer, or hang up when the call has ended."""
    out = ['<?xml version="1.0" encoding="UTF-8"?><Response>']
    turns = call.turns or []
    for i in range(played, len(turns)):
        if turns[i].get("who") == "agent":
            out.append(f"<Play>{escape(url(f'calls/{call.id}/turns/{i}/audio', call.id))}</Play>")
    if call.status != "active":
        out.append("<Hangup/>")
    elif calls.asks_yes_no(call):
        keys = escape(url(f"calls/{call.id}/keys", call.id))
        prompt = escape(url(f"prompts/{call.language}/keypad"))
        out.append(f'<Gather input="dtmf" numDigits="1" timeout="10" action="{keys}" method="POST"><Play>{prompt}</Play></Gather>')
        out.append(f'<Redirect method="POST">{keys}</Redirect>')  # no key pressed: the same handler, with no Digits
    else:
        rec = escape(url(f"calls/{call.id}/recording", call.id))
        beep = escape(url(f"prompts/{call.language}/after_beep"))
        out.append(f'<Play>{beep}</Play><Record maxLength="30" timeout="4" playBeep="true" trim="trim-silence" action="{rec}" method="POST"/>')
        out.append(f'<Redirect method="POST">{rec}</Redirect>')
    out.append("</Response>")
    return "".join(out), len(turns)
