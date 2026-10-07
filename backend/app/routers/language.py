"""Speech-to-text and translation for intake (offline AI4Bharat models; see app/language.py)."""

import asyncio
import logging
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .. import asr_check, bhashini, filetypes, language, sarvam, tts, whisper_asr
from ..config import get_settings
from ..ratelimit import limit
from ..schemas import ADMIN_ROLES
from ..security import CurrentUser

router = APIRouter(tags=["language"])
log = logging.getLogger(__name__)


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source: str
    target: str


def _clinical(user) -> None:
    if user.role in ADMIN_ROLES or user.role == "employer":
        raise HTTPException(403, "This role cannot use intake speech services")


@router.get("/language/engines")
def engines(user: CurrentUser):
    langs = sorted(lang for lang in whisper_asr.LANGS if whisper_asr.model_dir(lang))
    return {**language.status(), "mt_online": {"engine": bhashini.ENGINE, "configured": bhashini.enabled()},
            "tts_offline": {"engine": tts.ENGINE, "languages": tts.languages()}, "asr_second": {
        "online": {"engine": sarvam.STT_ENGINE, "configured": sarvam.enabled(), "languages": sorted(sarvam.STT_LANGS)},
        "offline": {"engine": whisper_asr.ENGINE, "enabled": get_settings().asr_second_offline,
                    "installed": bool(langs) and whisper_asr.available(langs[0]), "languages": langs}}}


@router.post("/speech/transcribe", dependencies=[Depends(limit("ai"))])
async def transcribe(user: CurrentUser, audio: Annotated[UploadFile, File()], language_code: Annotated[str, Form(alias="language")], translate: Annotated[bool, Form()] = True,
                     second_opinion: Annotated[bool, Form()] = False):
    """Recorded audio → transcript in the speaker's language, plus an English translation. Audio is not stored here.

    second_opinion (only when the patient allowed AI assistance): a second engine hears the same audio and the two
    transcripts are compared (B9); where they differ on a number, a symptom or most words, both are returned so the
    patient can be asked. The second engine is Sarvam Saaras (online); with no key, no connection, nothing heard or a
    language Sarvam does not take, IndicWhisper (offline) hears it instead, after this reply: second_opinion is then
    {engine, pending: id} until GET /speech/second/{id} has the comparison. Where IndicConformer is not installed (the
    hosted link), the second engine alone transcribes, named as such."""
    _clinical(user)
    s = get_settings()
    data = await audio.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Recording too large (max {s.max_upload_mb} MB)")
    if filetypes.family(filetypes.sniff(data) or "none") != "audio":
        raise HTTPException(422, "That does not look like a recording — please speak again, or type instead")
    online = None
    if second_opinion and sarvam.enabled() and language_code in sarvam.STT_LANGS:
        online = asyncio.create_task(_sarvam(data, language_code, audio.filename or "speech.webm"))
    try:
        result = await run_in_threadpool(language.transcribe, data, language_code)
    except language.AudioRejected as e:
        if online:
            online.cancel()
        raise HTTPException(422, str(e)) from e
    except language.LanguageUnavailable as e:
        second = await online if online else None
        if second_opinion and not _heard(second) and _offline_second(language_code):
            second = await run_in_threadpool(_whisper, data, language_code)  # the only engine left: wait for it
        if isinstance(second, dict) and not second["text"]:
            raise HTTPException(422, "No words were recognised — please speak again, or type instead") from e
        if not isinstance(second, dict):
            raise HTTPException(503, str(e)) from e
        result = {**second, "seconds_audio": None, "seconds_taken": None, "offline_unavailable": str(e)}
        second_opinion = False
    if result.get("confidence") is not None:
        result["confidence_threshold"] = language.min_confidence(language_code)
        result["low_confidence"] = result["confidence"] < result["confidence_threshold"]
    if second_opinion:
        second = await online if online else None
        if _heard(second):
            result["second_opinion"] = asr_check.compare(result["text"], second["text"], language_code, result["engine"], second["engine"])
        elif _offline_second(language_code):
            # Sarvam unset, unreachable, deaf to this language or heard nothing: IndicWhisper (offline) hears it. It
            # is ~3x slower than real time on a laptop, so the patient is not kept waiting: the check runs after
            # this reply and the screen asks for it (GET /speech/second/{id}).
            result["second_opinion"] = {"engine": whisper_asr.ENGINE, "pending": _start_check(
                user.id, data, language_code, result["text"], result["engine"], translate)}
        elif online:
            result["second_opinion"] = {"engine": sarvam.STT_ENGINE, "error": str(second) if second else "No words were recognised"}
    result["translation"] = None
    if translate:
        try:
            tr = await run_in_threadpool(_english, result["text"], language_code)
            if tr:
                result["translation"] = {"text": tr["text"], "language": "en", "engine": tr["engine"], "rewrites": tr["rewrites"], "unsure": tr["unsure"]}
            chk = result.get("second_opinion") or {}
            if chk.get("disagree") and language_code != "en":  # the doctor reads both, in English too
                chk["translation"] = (await run_in_threadpool(_english, chk["text"], language_code) or {}).get("text")
        except language.LanguageUnavailable as e:
            result["translation_error"] = str(e)
    return result


def _english(text: str, lang: str) -> dict | None:
    if lang == "en":
        return None
    try:
        return language.translate_patient(text, lang)
    except language.LanguageUnavailable:
        out = language.translate_any([text], lang, "en")  # Bhashini when the offline model cannot run; raises if neither
        return {"text": out["texts"][0], "engine": out["engine"], "rewrites": [], "unsure": []}


async def _sarvam(data: bytes, lang: str, filename: str) -> dict | Exception:
    try:
        return await run_in_threadpool(sarvam.transcribe, data, lang, filename)
    except sarvam.SarvamUnavailable as e:
        return e


def _heard(second) -> bool:
    return isinstance(second, dict) and bool(second["text"])


def _offline_second(lang: str) -> bool:
    return get_settings().asr_second_offline and whisper_asr.available(lang)


def _whisper(data: bytes, lang: str) -> dict | Exception:
    try:
        return whisper_asr.transcribe(data, lang)
    except (language.LanguageUnavailable, language.AudioRejected) as e:
        return e


# Offline second-engine checks: id → {user, at, result}. One at a time (one model in memory, and IndicConformer keeps
# the rest of the CPU); kept in memory for CHECK_KEEP_S, the recording dropped once heard.
_checks: dict[str, dict] = {}
_check_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asr-second")
CHECK_KEEP_S = 600


def _start_check(user_id, data: bytes, lang: str, first_text: str, first_engine: str, translate: bool) -> str:
    now = time.monotonic()
    for k in [k for k, v in _checks.items() if now - v["at"] > CHECK_KEEP_S]:
        del _checks[k]
    job = secrets.token_urlsafe(12)
    _checks[job] = {"user": user_id, "at": now, "result": None}

    def run():
        try:
            heard = _whisper(data, lang)
            if not _heard(heard):
                out = {"engine": whisper_asr.ENGINE, "error": str(heard) if isinstance(heard, Exception) else "No words were recognised"}
            else:
                out = asr_check.compare(first_text, heard["text"], lang, first_engine, heard["engine"])
                if translate and out.get("disagree") and lang != "en":  # the doctor reads both, in English too
                    try:
                        out["translation"] = (_english(out["text"], lang) or {}).get("text")
                    except language.LanguageUnavailable:
                        out["translation"] = None
        except Exception as e:  # noqa: BLE001 — a check that fails must say so, not stay "pending"
            log.exception("offline second check failed")
            out = {"engine": whisper_asr.ENGINE, "error": f"The second engine failed: {type(e).__name__}"}
        _checks[job]["result"] = out

    _check_pool.submit(run)
    return job


@router.get("/speech/second/{job}")
def second_check(job: str, user: CurrentUser):
    """The offline second engine's check of a transcript (B9): {pending} until it has heard the recording, then the
    comparison, as /speech/transcribe returns it for Sarvam."""
    c = _checks.get(job)
    if not c or c["user"] != user.id:
        raise HTTPException(404, "No such check")
    return c["result"] or {"engine": whisper_asr.ENGINE, "pending": job}


@router.post("/translate", dependencies=[Depends(limit("ai"))])
async def translate(body: TranslateIn, user: CurrentUser):
    _clinical(user)
    try:
        tr = await run_in_threadpool(language.translate_any, [body.text], body.source, body.target)
    except language.LanguageUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return {"text": tr["texts"][0], "source": body.source, "target": body.target, "engine": tr["engine"]}


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    language: str = Field(min_length=2, max_length=4)
    allow_online: bool = True  # False for the patient's own words without AI-helper consent: offline voice only


@router.post("/language/speak", dependencies=[Depends(limit("ai"))])
async def speak(body: SpeakIn, user: CurrentUser):
    """A7: read a kiosk line aloud when the device has no voice for the language (Windows has no Odia voice).
    Sarvam Bulbul, online, in India. The kiosk sends the patient's own words only when they chose AI helpers.
    Audio is kept in memory only; nothing is stored.
    The offline voice on this server (MMS-TTS: Odia, Hindi, Kannada) is tried first; Sarvam only if it has none."""
    if tts.available(body.language):
        try:
            wav = await run_in_threadpool(tts.speak, body.text.strip(), body.language)
            return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store", "X-Voice-Engine": tts.ENGINE})
        except Exception:  # noqa: BLE001 — a broken offline voice falls through to the online one
            pass
    if not body.allow_online:
        raise HTTPException(422, "No offline voice for this language, and online was not allowed")
    if not sarvam.enabled():
        raise HTTPException(503, "No online voice configured on this server")
    if body.language not in sarvam.TTS_LANGS:
        raise HTTPException(422, f"No online voice for '{body.language}'")
    try:
        audio = await run_in_threadpool(sarvam.speak, body.text.strip(), body.language)
    except sarvam.SarvamUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
