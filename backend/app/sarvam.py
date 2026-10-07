"""Sarvam AI (online, India-hosted): Bulbul v3 voice, Saaras v3 speech-to-text and Sarvam Vision document reading.

* Voice reads the fixed reminder-call lines (E6) in 11 languages, so a call sounds right on a device without an Indian
  voice installed, and the same audio can go down a phone line. The words are ours (calls.yaml); Sarvam only speaks them.
* Speech-to-text is the online second engine beside the offline IndicConformer (B9).
* Vision reads photographed handwriting (prescriptions), which the offline OCR engines cannot (B1, B9).

Plain REST over httpx (as otp.py does for Twilio), so the deployed app needs no extra package. Unset key = not used:
calls fall back to the device's voice. What is sent: one line of a call at a time. The line with the patient's first
name never carries anything about health, and the questions never carry a name.
"""

import base64
import logging
from functools import lru_cache

import httpx

from .config import get_settings

log = logging.getLogger("jeevia.sarvam")
BASE = "https://api.sarvam.ai"

# App language code → Sarvam's. Bulbul v3 speaks these 11; Saaras v3 hears 22 Indian languages and English.
TTS_LANGS = {"en": "en-IN", "hi": "hi-IN", "or": "od-IN", "bn": "bn-IN", "ta": "ta-IN", "te": "te-IN", "gu": "gu-IN",
             "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN", "pa": "pa-IN"}
STT_LANGS = {**TTS_LANGS, "as": "as-IN", "ur": "ur-IN", "ne": "ne-IN", "kok": "kok-IN", "ks": "ks-IN", "sd": "sd-IN",
             "sa": "sa-IN", "sat": "sat-IN", "mni": "mni-IN", "brx": "brx-IN", "mai": "mai-IN", "doi": "doi-IN"}
STT_ENGINE = "Sarvam Saaras v3 (online)"
CODECS = {"mp3": "audio/mpeg", "wav": "audio/wav", "mulaw": "audio/basic"}


class SarvamUnavailable(Exception):
    """No key, a language Sarvam does not cover, or the service could not be reached."""


def enabled() -> bool:
    return bool(get_settings().sarvam_api_key)


def _headers() -> dict:
    key = get_settings().sarvam_api_key
    if not key:
        raise SarvamUnavailable("Sarvam is not configured")
    return {"api-subscription-key": key}


def _post(path: str, **kw) -> dict:
    try:
        r = httpx.post(f"{BASE}/{path}", headers=_headers(), timeout=get_settings().sarvam_timeout_s, **kw)
    except httpx.HTTPError as e:
        raise SarvamUnavailable("Could not reach Sarvam") from e
    if r.status_code >= 400:
        log.warning("sarvam error", extra={"path": path, "status": r.status_code})
        raise SarvamUnavailable(f"Sarvam error {r.status_code}")
    return r.json()


def speak(text: str, lang: str, codec: str = "mp3", sample_rate: int = 22050) -> bytes:
    """Fixed text → audio bytes. Kept in memory only (a line may carry a first name), never written to disk."""
    if lang not in TTS_LANGS:
        raise SarvamUnavailable(f"No Sarvam voice for language '{lang}'")
    if codec not in CODECS:
        raise ValueError(codec)
    return _speak(text, lang, codec, sample_rate, get_settings().sarvam_tts_speaker)


@lru_cache(maxsize=256)
def _speak(text: str, lang: str, codec: str, sample_rate: int, speaker: str) -> bytes:
    body = {"text": text, "language_code": TTS_LANGS[lang], "speaker": speaker, "model": "bulbul:v3",
            "speech_sample_rate": sample_rate, "output_audio_codec": codec}
    return base64.b64decode("".join(_post("text-to-speech", json=body)["audios"]))


VISION_ENGINE = "Sarvam Vision document digitisation (online)"
VISION_LANGS = {**STT_LANGS}  # Sarvam Vision reads English and the 22 scheduled languages, same codes


def read_page(data: bytes, filename: str, lang: str = "en", wait_s: float = 90) -> list[dict]:
    """One photographed page → text blocks [{text, conf, bbox (x, y, w, h, 0–1)}], by Sarvam Vision (Digitise job:
    start, poll, download the JSON). Used for handwriting, which the offline engines cannot read. The image is sent
    only with the patient's AI consent; Sarvam keeps job outputs behind a signed link, which is not stored."""
    import io
    import json
    import time
    import zipfile

    s = get_settings()
    job = _post("doc-ai/v1/job/digitise", data={"language": VISION_LANGS.get(lang, "en-IN"), "output_format": "json"},
                files={"file": (filename, data)})["job_id"]
    deadline = time.monotonic() + wait_s
    while True:
        try:
            st = httpx.get(f"{BASE}/doc-ai/v1/job/{job}/status", headers=_headers(), timeout=s.sarvam_timeout_s).json()
        except httpx.HTTPError as e:
            raise SarvamUnavailable("Could not reach Sarvam") from e
        if str(st.get("status", "")).lower() in ("completed", "partially_completed"):
            break
        if str(st.get("status", "")).lower() in ("failed", "rejected") or time.monotonic() > deadline:
            raise SarvamUnavailable(f"Sarvam Vision job {st.get('status', 'timed out')}")
        time.sleep(1.5)
    try:
        url = httpx.get(f"{BASE}/doc-ai/v1/job/{job}/download-url", headers=_headers(), timeout=s.sarvam_timeout_s).json()["url"]
        z = zipfile.ZipFile(io.BytesIO(httpx.get(url, timeout=s.sarvam_timeout_s).content))
    except (httpx.HTTPError, KeyError, zipfile.BadZipFile) as e:
        raise SarvamUnavailable("Sarvam Vision output could not be read") from e
    out = []
    for name in z.namelist():
        if not name.endswith(".json") or name == "manifest.json":
            continue
        for page in json.loads(z.read(name)).get("pages", []):
            for b in sorted(page.get("blocks", []), key=lambda b: b.get("reading_order", 0)):
                x0, y0, x1, y1 = b.get("bbox_norm") or [0, 0, 1, 1]
                out += block_lines(b.get("text") or "", float(b.get("confidence") or 0), [x0, y0, x1 - x0, y1 - y0])
    return out


def block_lines(text: str, conf: float, bbox: list[float]) -> list[dict]:
    """A Digitise block → plain lines, each with its share of the block's box. Blocks come as Markdown and, for printed
    tables, as HTML ("<table><tr><td>Rx</td><td>Name</td>…"): one line per table row, cells two spaces apart."""
    import html
    import re

    text = re.sub(r"</t[dh]>[ 	]*", "  ", re.sub(r"</tr>|<br\s*/?>", "\n", text, flags=re.I), flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    parts = [p for p in (re.sub(r"\*\*|__|`", "", p).strip(" \t-*\"|") for p in text.split("\n")) if p]
    x, y, w, h = bbox
    return [{"text": part, "conf": conf, "bbox": [x, y + i * h / len(parts), w, h / len(parts)]} for i, part in enumerate(parts)]


def transcribe(audio: bytes, lang: str, filename: str = "audio.webm", translate: bool = False) -> dict:
    """Recorded audio → text in the speaker's language (or English, translate=True), by Saaras v3."""
    if lang not in STT_LANGS:
        raise SarvamUnavailable(f"No Sarvam speech model for language '{lang}'")
    data = {"model": "saaras:v3", "mode": "translate" if translate else "transcribe", "language_code": STT_LANGS[lang]}
    out = _post("speech-to-text", data=data, files={"file": (filename, audio)})
    return {"text": (out.get("transcript") or "").strip(), "language": "en" if translate else lang, "engine": STT_ENGINE}
