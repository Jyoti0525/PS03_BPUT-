"""Speech-to-text and translation for intake (offline AI4Bharat models; see app/language.py)."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .. import language
from ..config import get_settings
from ..schemas import ADMIN_ROLES
from ..security import CurrentUser

router = APIRouter(tags=["language"])


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source: str
    target: str


def _clinical(user) -> None:
    if user.role in ADMIN_ROLES or user.role == "employer":
        raise HTTPException(403, "This role cannot use intake speech services")


@router.get("/language/engines")
def engines(user: CurrentUser):
    return language.status()


@router.post("/speech/transcribe")
async def transcribe(user: CurrentUser, audio: Annotated[UploadFile, File()], language_code: Annotated[str, Form(alias="language")], translate: Annotated[bool, Form()] = True):
    """Recorded audio → transcript in the speaker's language, plus an English translation. Audio is not stored here."""
    _clinical(user)
    s = get_settings()
    data = await audio.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Recording too large (max {s.max_upload_mb} MB)")
    try:
        result = await run_in_threadpool(language.transcribe, data, language_code)
    except language.AudioRejected as e:
        raise HTTPException(422, str(e)) from e
    except language.LanguageUnavailable as e:
        raise HTTPException(503, str(e)) from e
    result["translation"] = None
    if translate:
        try:
            tr = await run_in_threadpool(language.translate_patient, result["text"], language_code)
            result["translation"] = {"text": tr["text"], "language": "en", "engine": tr["engine"], "rewrites": tr["rewrites"], "unsure": tr["unsure"]}
        except language.LanguageUnavailable as e:
            result["translation_error"] = str(e)
    return result


@router.post("/translate")
async def translate(body: TranslateIn, user: CurrentUser):
    _clinical(user)
    try:
        tr = await run_in_threadpool(language.translate, [body.text], body.source, body.target)
    except language.LanguageUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return {"text": tr["texts"][0], "source": body.source, "target": body.target, "engine": tr["engine"]}
