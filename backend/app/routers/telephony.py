"""Twilio's and Vonage's webhooks for a reminder call over a real phone line (E6). No user session: every request
must carry the call's own token, and Twilio's also its signature. The rules are the same as the browser call
(calls.py)."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from .. import calls, sarvam, telephony, vonage
from ..db import SessionLocal
from ..models import Call, User
from ..security import DB
from .alerts import alert_staff_by_sms

log = logging.getLogger("jeevia.telephony")
router = APIRouter(prefix="/telephony", tags=["telephony"])
XML = "application/xml"


async def _verified(request: Request, db, cid: str) -> tuple[Call, dict]:
    form = {k: str(v) for k, v in (await request.form()).items()}
    t = request.query_params.get("t")
    signed = telephony.url(request.url.path.removeprefix("/api/v1/telephony/"), cid)
    if not telephony.check_token(cid, t) or not telephony.valid_signature(signed, form, request.headers.get("X-Twilio-Signature")):
        raise HTTPException(403, "Not from Twilio")
    c = db.get(Call, cid)
    if not c or not (c.notes or {}).get("phone"):
        raise HTTPException(404, "Call not found")
    return c, form


def _phone(c: Call, **kw) -> None:
    c.notes = {**(c.notes or {}), "phone": {**(c.notes or {}).get("phone", {}), **kw}}


def _starter(db, c: Call) -> User:
    return db.get(User, c.started_by)


def _reply(db, c: Call) -> Response:
    """Whatever the call needs next: the lines not yet played, then a keypad question, a recording, or hang up."""
    xml, played = telephony.twiml(c, c.notes["phone"].get("played", 0))
    _phone(c, played=played)
    alert_staff_by_sms(db, c)
    db.commit()
    return Response(xml, media_type=XML)


@router.post("/calls/{cid}/voice")
async def voice(cid: str, request: Request, db: DB):
    """The patient picked up: play the opening line."""
    c, _ = await _verified(request, db, cid)
    _phone(c, answered=True)
    return _reply(db, c)


@router.post("/calls/{cid}/keys")
async def keys(cid: str, request: Request, db: DB):
    """A key pressed (1 yes, 2 no, 3 not sure), or none: read by the same rules as a spoken answer."""
    c, form = await _verified(request, db, cid)
    if c.status == "active":
        d = form.get("Digits", "")
        calls.answer(db, c, _starter(db, c), telephony.KEYPAD.get(d, ""), f"Pressed {d}" if d else None)
    return _reply(db, c)


@router.post("/calls/{cid}/recording")
async def recording(cid: str, request: Request, db: DB):
    """The free answer: transcribed and translated (Sarvam, else the offline models), read for danger signs, and the
    recording deleted from Twilio. Something said that cannot be read pages a person."""
    c, form = await _verified(request, db, cid)
    rec = form.get("RecordingUrl")
    said = bool(rec) and form.get("RecordingDuration") not in (None, "", "0")
    await _take_recording(db, c, rec if said else None, telephony.fetch_recording, telephony.delete_recording)
    return _reply(db, c)


async def _take_recording(db, c: Call, rec: str | None, fetch, delete) -> None:
    """The free answer: transcribed and translated, read by the rules, and the recording deleted. Nothing recorded =
    nothing said; something recorded that cannot be read pages a person."""
    if c.status != "active":
        return
    if not rec:
        calls.answer(db, c, _starter(db, c), "", None)
        return
    try:
        original, english = await run_in_threadpool(_hear, rec, c.language, fetch)
    finally:
        await run_in_threadpool(delete, rec)
    if original is None:
        calls.finish(db, c, "unclear", [{"finding": None, "label": "Free answer that could not be read",
                                         "evidence": "Recorded on the phone; speech recognition failed"}], _starter(db, c))
    else:
        calls.answer(db, c, _starter(db, c), english or original, original)


def _hear(recording_url: str, lang: str, fetch) -> tuple[str | None, str | None]:
    try:
        audio = fetch(recording_url)
    except telephony.TelephonyUnavailable:
        return None, None
    try:
        original = sarvam.transcribe(audio, lang, "answer.mp3")["text"]
        english = original if lang == "en" else sarvam.transcribe(audio, lang, "answer.mp3", translate=True)["text"]
        return original, english
    except sarvam.SarvamUnavailable:
        pass
    try:  # offline: IndicConformer, then IndicTrans2
        from .. import language

        original = language.transcribe(audio, lang)["text"]
        english = original if lang == "en" else language.translate_patient(original, lang)["text"]
        return original, english
    except Exception:
        log.warning("phone answer could not be transcribed")
        return None, None


@router.post("/calls/{cid}/status")
async def call_status(cid: str, request: Request, db: DB):
    """Twilio's last word on the call: if our side was still waiting, it was not answered or was cut off."""
    c, form = await _verified(request, db, cid)
    st = form.get("CallStatus", "")
    _phone(c, status=st)
    if c.status == "active" and st in telephony.ENDED:
        answered = c.notes["phone"].get("answered") and st not in telephony.DIAL_FAILED
        calls.hang_up(db, c, _starter(db, c), "hung_up" if answered else "no_answer")
    db.commit()
    return Response(status_code=204)


@router.get("/calls/{cid}/turns/{i}/audio")
def turn_audio(cid: str, i: int, t: str, db: DB):
    """One agent line for Twilio to play (Sarvam's voice). The call's token is the only key: Twilio's media fetches
    are not signed."""
    if not telephony.check_token(cid, t):
        raise HTTPException(403, "Bad token")
    c = db.get(Call, cid)
    turns = (c.turns or []) if c else []
    if not (0 <= i < len(turns)) or turns[i].get("who") != "agent":
        raise HTTPException(404, "No agent line here")
    try:
        return Response(sarvam.speak(turns[i]["text"], c.language), media_type="audio/mpeg")
    except sarvam.SarvamUnavailable as e:
        raise HTTPException(503, str(e)) from None


@router.get("/prompts/{lang}/{key}")
def prompt_audio(lang: str, key: str):
    """The fixed keypad and beep prompts. Nothing personal, so no token."""
    lines = calls.config()["phone"]
    if key not in lines or lang not in calls.LANGS:
        raise HTTPException(404, "No such prompt")
    try:
        return Response(sarvam.speak(lines[key][lang], lang), media_type="audio/mpeg")
    except sarvam.SarvamUnavailable as e:
        raise HTTPException(503, str(e)) from None


# ── Vonage ────────────────────────────────────────────
def _vonage_call(db, cid: str, t: str | None) -> Call:
    if not telephony.check_token(cid, t):
        raise HTTPException(403, "Bad token")
    c = db.get(Call, cid)
    if not c or not (c.notes or {}).get("phone"):
        raise HTTPException(404, "Call not found")
    return c


def _vonage_reply(db, c: Call) -> list[dict]:
    actions, played = vonage.ncco(c, c.notes["phone"].get("played", 0))
    _phone(c, played=played)
    alert_staff_by_sms(db, c)
    db.commit()
    return actions


async def _json(request: Request) -> dict:
    try:
        return await request.json()
    except ValueError:
        return {}


@router.get("/vonage/calls/{cid}/answer")
def vonage_answer(cid: str, t: str, db: DB):
    """The patient picked up: play the opening line."""
    c = _vonage_call(db, cid, t)
    _phone(c, answered=True)
    return _vonage_reply(db, c)


@router.post("/vonage/calls/{cid}/keys")
async def vonage_keys(cid: str, t: str, request: Request, db: DB):
    c = _vonage_call(db, cid, t)
    d = str(((await _json(request)).get("dtmf") or {}).get("digits") or "")[:1]
    if c.status == "active":
        calls.answer(db, c, _starter(db, c), telephony.KEYPAD.get(d, ""), f"Pressed {d}" if d else None)
    return _vonage_reply(db, c)


@router.post("/vonage/calls/{cid}/recording")
async def vonage_recording(cid: str, t: str, request: Request, db: DB):
    """Vonage reports the free answer's recording separately from the call's flow."""
    c = _vonage_call(db, cid, t)
    body = await _json(request)
    rec = body.get("recording_url")
    said = bool(rec) and int(body.get("size") or 0) > 0
    await _take_recording(db, c, rec if said else None, vonage.fetch_recording, vonage.delete_recording)
    _phone(c, recording_read=True)
    db.commit()
    return Response(status_code=204)


@router.post("/vonage/calls/{cid}/after_record")
async def vonage_after_record(cid: str, t: str, db: DB):
    """What comes after the free answer, once its recording has been read (up to 15 s). If it never arrives, a person
    must call: something may have been said that no one has read."""
    c = _vonage_call(db, cid, t)
    for _ in range(30):
        with SessionLocal() as fresh:
            done = ((fresh.get(Call, cid).notes or {}).get("phone") or {}).get("recording_read")
        if done:
            break
        await asyncio.sleep(0.5)
    db.expire_all()
    c = db.get(Call, cid)
    if c.status == "active" and not c.notes["phone"].get("recording_read"):
        calls.finish(db, c, "unclear", [{"finding": None, "label": "Free answer not received",
                                         "evidence": "The phone recording did not arrive in time"}], _starter(db, c))
    return _vonage_reply(db, c)


@router.post("/vonage/calls/{cid}/event")
async def vonage_event(cid: str, t: str, request: Request, db: DB):
    """Vonage's call status: if our side was still waiting, the call was not answered or was cut off."""
    c = _vonage_call(db, cid, t)
    body = await _json(request)
    st = body.get("status", "")
    _phone(c, status=st, **({"detail": str(body["detail"])[:200]} if body.get("detail") else {}))  # why a call was rejected or failed
    log.info("vonage call event", extra={"path": f"{st} {body.get('detail') or ''}".strip()})
    if st == "answered":
        _phone(c, answered=True)
    if c.status == "active" and st in vonage.ENDED:
        answered = c.notes["phone"].get("answered") and st not in vonage.DIAL_FAILED
        calls.hang_up(db, c, _starter(db, c), "hung_up" if answered else "no_answer")
    db.commit()
    return Response(status_code=204)


@router.get("/vonage/answer")
def vonage_inbound():
    """The application's own answer URL (calls into the app): nothing is offered there."""
    return [{"action": "talk", "text": "This number does not take calls. Goodbye."}]


@router.post("/vonage/event")
def vonage_inbound_event():
    return Response(status_code=204)
