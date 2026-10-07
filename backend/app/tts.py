"""A7: offline voice on this server — Meta MMS-TTS (VITS), one small model per language, CPU.

Windows has no Odia voice, so the kiosk asks the server to read a line aloud. Text stays on this server.
Models: facebook/mms-tts-{ory,hin,kan} in models/mms-tts-*, CC-BY-NC 4.0 (fine for this non-commercial POC;
a commercial deployment needs another voice, such as AI4Bharat Indic Parler-TTS or Sarvam Bulbul online).
"""
import io
import threading
import wave
from functools import lru_cache
from pathlib import Path

from .config import get_settings

ENGINE = "MMS-TTS (Meta, offline)"
CODES = {"or": "ory", "hi": "hin", "kn": "kan"}
_lock = threading.Lock()


def model_dir(lang: str) -> Path | None:
    code = CODES.get(lang)
    if not code:
        return None
    p = Path(get_settings().models_dir) / f"mms-tts-{code}"
    return p if (p / "config.json").exists() else None


def available(lang: str) -> bool:
    return model_dir(lang) is not None


def languages() -> list[str]:
    return sorted(lang for lang in CODES if available(lang))


@lru_cache(maxsize=3)
def _load(lang: str):
    from transformers import AutoTokenizer, VitsModel

    p = model_dir(lang)
    return VitsModel.from_pretrained(p).eval(), AutoTokenizer.from_pretrained(p)  # nosec B615: a local folder, never the Hub


def speak(text: str, lang: str) -> bytes:
    """Text → 16-bit mono WAV. Raises LookupError when no offline voice is installed for the language."""
    if not available(lang):
        raise LookupError(f"No offline voice for '{lang}'")
    import torch

    with _lock:
        model, tok = _load(lang)
        inputs = tok(text, return_tensors="pt")
        with torch.no_grad():
            w = model(**inputs).waveform[0]
    pcm = (w.clamp(-1, 1) * 32767).to(torch.int16).numpy().tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(model.config.sampling_rate)
        f.writeframes(pcm)
    return buf.getvalue()
