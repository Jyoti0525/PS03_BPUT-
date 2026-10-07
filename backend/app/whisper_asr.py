"""IndicWhisper: the offline second speech engine (B9).

AI4Bharat's Vistaar IndicWhisper models (whisper-medium fine-tuned per language; MIT licence) hear the same recording
as IndicConformer when the online engine (Sarvam) cannot: no network, no key, or a language Sarvam does not take. So the
cross-check of numbers and symptoms (app/asr_check.py) still runs on a facility machine with no connection.

Models live in <models_dir>/indicwhisper/<language>_models/whisper-medium-<code>_*/, one download per language
(https://indicwhisper.objectstore.e2enetworks.net/<language>_models.zip). Loaded on first use, one language at a time.
whisper-medium is 1.5 GB in fp32; setting asr_second_int8 makes an 8-bit copy at load time (docs/EVALUATION.md).
On a laptop CPU it hears Odia about 3x slower than real time, so the intake does not wait for it: the speech route runs
it as a background check (routers/language.py) and the screen picks up the result when it is ready.
"""

import gc
import logging
import threading
import time
from pathlib import Path

from .config import get_settings
from .language import SAMPLE_RATE, LanguageUnavailable, models_dir

log = logging.getLogger(__name__)

ENGINE = "IndicWhisper (AI4Bharat Vistaar, whisper-medium, offline)"
# Vistaar's twelve languages. Whisper has no Odia token; the Odia model was trained under Pashto's (its own language
# detection picks <|ps|> on FLEURS Odia), so that token is given rather than detected, which could pick another.
LANGS = {"bn", "gu", "hi", "kn", "ml", "mr", "or", "pa", "sa", "ta", "te", "ur"}
_TOKEN = {"or": "ps"}
# Whisper writes at most 448 tokens a window, and has no merges for Odia script: each letter is 3 byte tokens, about
# 37 a second of speech. So recordings are cut at a pause into windows of at most 10 s (370 tokens).
WINDOW_S, MIN_CUT_S = 10, 6

_loaded: tuple[str, object, object] | None = None  # (language, processor, model)
_lock = threading.Lock()


def model_dir(lang: str) -> Path | None:
    root = models_dir() / "indicwhisper"
    found = sorted(root.glob(f"*_models/whisper-medium-{lang}_*")) if root.exists() else []
    return next((p for p in found if (p / "config.json").exists()), None)


def available(lang: str) -> bool:
    if lang not in LANGS or model_dir(lang) is None:
        return False
    import importlib.util

    return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))


def _model(lang: str):
    global _loaded
    with _lock:
        if _loaded and _loaded[0] == lang:
            return _loaded[1], _loaded[2]
        path = model_dir(lang)
        if path is None:
            raise LanguageUnavailable(f"IndicWhisper model for '{lang}' not downloaded")
        try:
            import torch
            from transformers import WhisperForConditionalGeneration, WhisperProcessor
        except ImportError as e:
            raise LanguageUnavailable(f"Speech engine dependencies missing: {e.name}") from e
        _loaded = None  # one language at a time: free the previous model first
        t = time.perf_counter()
        processor = WhisperProcessor.from_pretrained(path)
        model = WhisperForConditionalGeneration.from_pretrained(path, low_cpu_mem_usage=True).eval()
        if get_settings().asr_second_int8:
            model = torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8, inplace=True)
            gc.collect()  # the fp32 weights the 8-bit layers replaced
        _loaded = (lang, processor, model)
        log.info("%s (%s) loaded in %.1fs", ENGINE, lang, time.perf_counter() - t)
        return processor, model


def windows(wav) -> list[tuple[int, int]]:
    """(start, end) samples: each window ends at the quietest 100 ms between MIN_CUT_S and WINDOW_S, so a word is
    not cut in two."""
    import numpy as np

    out, start, frame = [], 0, SAMPLE_RATE // 10
    while len(wav) - start > WINDOW_S * SAMPLE_RATE:
        lo, hi = start + MIN_CUT_S * SAMPLE_RATE, start + WINDOW_S * SAMPLE_RATE
        energy = [float(np.sqrt(np.mean(wav[i:i + frame] ** 2))) for i in range(lo, hi - frame + 1, frame)]
        cut = lo + int(np.argmin(energy)) * frame + frame // 2
        out.append((start, cut))
        start = cut
    if len(wav) - start >= SAMPLE_RATE // 2:  # under half a second left over: nothing to hear
        out.append((start, len(wav)))
    return out


def transcribe_wav(wav, lang: str) -> dict:
    """16 kHz mono float32 audio (language.decode_audio) → {text, engine}, a window at a time."""
    processor, model = _model(lang)
    import torch

    t = time.perf_counter()
    parts = []
    for a, b in windows(wav):
        feats = processor(wav[a:b], sampling_rate=SAMPLE_RATE, return_tensors="pt").input_features
        with torch.inference_mode():
            ids = model.generate(feats, task="transcribe", language=_TOKEN.get(lang, lang),
                                 max_new_tokens=model.config.max_target_positions - 8)
        parts.append(processor.batch_decode(ids, skip_special_tokens=True)[0].strip())
    return {"text": " ".join(" ".join(parts).split()), "language": lang, "engine": ENGINE,
            "seconds_taken": round(time.perf_counter() - t, 2)}


def transcribe(data: bytes, lang: str) -> dict:
    from .language import decode_audio

    if lang not in LANGS:
        raise LanguageUnavailable(f"No IndicWhisper model for language '{lang}'")
    return transcribe_wav(decode_audio(data), lang)
