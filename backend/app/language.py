"""Speech recognition and translation for intake. Every result names the engine that produced it.

Offline engines (run on the facility machine, no internet needed), loaded on first use:
* ASR — IndicConformer-600M multilingual (AI4Bharat, MIT): Conformer CTC/RNNT exported to ONNX,
  covers all 22 scheduled languages.
* Translation — IndicTrans2 distilled 200M (AI4Bharat, MIT), Indic → English and English → Indic.

Weights live in <repo>/models (backend/scripts/fetch_models.py). When an engine is not installed or
fails, callers get `LanguageUnavailable` — never a placeholder transcript or an untranslated string
dressed up as a translation.
"""

import io
import logging
import sys
import threading
import time
import types
from pathlib import Path

from .config import get_settings

log = logging.getLogger("jeevia.language")

# App language code → IndicTrans2 FLORES-style tag (script matters: ks/sd use Arabic script here,
# mni uses Bengali script, matching what the kiosk keyboard produces).
IT2_TAGS = {
    "en": "eng_Latn", "as": "asm_Beng", "bn": "ben_Beng", "brx": "brx_Deva", "doi": "doi_Deva",
    "gu": "guj_Gujr", "hi": "hin_Deva", "kn": "kan_Knda", "kok": "gom_Deva", "ks": "kas_Arab",
    "mai": "mai_Deva", "ml": "mal_Mlym", "mni": "mni_Beng", "mr": "mar_Deva", "ne": "npi_Deva",
    "or": "ory_Orya", "pa": "pan_Guru", "sa": "san_Deva", "sat": "sat_Olck", "sd": "snd_Arab",
    "ta": "tam_Taml", "te": "tel_Telu", "ur": "urd_Arab",
}
ASR_LANGS = set(IT2_TAGS) - {"en"}  # IndicConformer uses the same short codes

def asr_engine_name() -> str:
    return "IndicConformer-600M int8 (AI4Bharat, offline)" if "int8" in get_settings().asr_model else "IndicConformer-600M (AI4Bharat, offline)"


MT_ENGINE = "IndicTrans2-200M (AI4Bharat, offline)"

SAMPLE_RATE = 16_000
MIN_SECONDS = 0.6
MAX_SECONDS = 90
SILENCE_PEAK = 0.005  # loudest sample below this = nothing recorded (soft speakers measured at peak 0.025)
MAX_GAIN = 40.0


class LanguageUnavailable(RuntimeError):
    """The requested engine cannot run here (not installed, weights missing, or it failed)."""


class AudioRejected(ValueError):
    """The recording itself is unusable (too short, silent, too long, undecodable)."""


def models_dir() -> Path:
    p = Path(get_settings().models_dir)
    return p if p.is_absolute() else (Path(__file__).resolve().parents[1] / p).resolve()


# ---------------------------------------------------------------- audio

def decode_audio(data: bytes):
    """Any browser recording (webm/opus, ogg, mp4/aac, wav) → mono float32 numpy at 16 kHz."""
    try:
        import av
        import numpy as np
    except ImportError as e:
        raise LanguageUnavailable("Audio decoding is not installed (PyAV)") from e
    try:
        chunks = []
        with av.open(io.BytesIO(data)) as c:
            res = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
            for frame in c.decode(audio=0):
                chunks.extend(f.to_ndarray() for f in res.resample(frame))
            chunks.extend(f.to_ndarray() for f in res.resample(None))
    except Exception as e:  # corrupt or unsupported container
        raise AudioRejected("The recording could not be read — please record again") from e
    if not chunks:
        raise AudioRejected("The recording is empty — please record again")
    wav = np.concatenate(chunks, axis=1).reshape(-1).astype("float32")
    secs = len(wav) / SAMPLE_RATE
    if secs < MIN_SECONDS:
        raise AudioRejected("The recording is too short — hold the mic button while speaking")
    if secs > MAX_SECONDS:
        raise AudioRejected(f"Recordings are limited to {MAX_SECONDS} seconds — please record in parts")
    peak = float(np.max(np.abs(wav)))
    if peak < SILENCE_PEAK:
        raise AudioRejected("No speech was heard — please speak closer to the microphone")
    if peak < 0.5:  # soft voice or a distant mic: raise the level (bounded) before recognition
        wav = wav * min(MAX_GAIN, 0.9 / peak)
    return wav


# ---------------------------------------------------------------- ASR

_asr = None
_asr_lock = threading.Lock()


def _conformer():
    global _asr
    with _asr_lock:
        if _asr is None:
            root = models_dir() / get_settings().asr_model
            if not (root / "assets" / "encoder.onnx").exists():
                raise LanguageUnavailable(f"Speech model {get_settings().asr_model} not downloaded (run backend/scripts/fetch_models.py, then quantize_asr.py)")
            try:
                sys.path.insert(0, str(root))
                import model_onnx  # the model repo's own loader
                import onnxruntime as ort
            except ImportError as e:
                raise LanguageUnavailable(f"Speech engine dependencies missing: {e.name}") from e
            finally:
                sys.path.remove(str(root))
            # No pre-allocated memory arena: on a 16 GB machine shared with the browser it only adds RAM.
            opts = ort.SessionOptions()
            opts.enable_cpu_mem_arena = False
            opts.enable_mem_pattern = False
            session = ort.InferenceSession
            model_onnx.ort = types.SimpleNamespace(InferenceSession=lambda path, providers=None, **kw: session(path, sess_options=opts, providers=providers))
            IndicASRConfig, IndicASRModel = model_onnx.IndicASRConfig, model_onnx.IndicASRModel
            t = time.perf_counter()
            # Built directly from the local folder: the repo's from_pretrained() would re-download.
            _asr = IndicASRModel(IndicASRConfig(ts_folder=str(root), FRAME_DURATION_MS=0.08))
            log.info("%s loaded in %.1fs", asr_engine_name(), time.perf_counter() - t)
        return _asr


def transcribe(data: bytes, lang: str) -> dict:
    """Recorded audio → transcript in the speaker's language (not translated)."""
    if lang not in ASR_LANGS:
        raise LanguageUnavailable(f"No offline speech model for language '{lang}'")
    wav = decode_audio(data)
    model = _conformer()
    import torch

    t = time.perf_counter()
    with torch.inference_mode():
        text = model(torch.from_numpy(wav).unsqueeze(0), lang, get_settings().asr_decoding)
    text = " ".join(str(text).split())
    if not text:
        raise AudioRejected("No words were recognised — please speak again, or type instead")
    return {
        "text": text,
        "language": lang,
        "engine": asr_engine_name(),
        "seconds_audio": round(len(wav) / SAMPLE_RATE, 1),
        "seconds_taken": round(time.perf_counter() - t, 2),
    }


# ---------------------------------------------------------------- translation

_mt: dict[str, tuple] = {}
_mt_lock = threading.Lock()
# One translation at a time per direction: IndicProcessor passes placeholder maps from preprocess to postprocess
# through a shared queue and clears it afterwards, so two overlapping calls (two kiosks, or start-up warm-up during
# the first intake) would leave one waiting on an empty queue forever.
_mt_run = {"indic-en": threading.Lock(), "en-indic": threading.Lock()}


def _indictrans(direction: str):
    """direction: 'indic-en' or 'en-indic' → (tokenizer, model, processor, device)."""
    with _mt_lock:
        if direction not in _mt:
            root = models_dir() / f"indictrans2-{direction}-dist-200M"
            if not (root / "config.json").exists():
                raise LanguageUnavailable("Translation model not downloaded (run backend/scripts/fetch_models.py)")
            try:
                import torch
                from IndicTransToolkit.processor import IndicProcessor
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            except ImportError as e:
                raise LanguageUnavailable(f"Translation engine dependencies missing: {e.name}") from e
            t = time.perf_counter()
            device = "cuda" if torch.cuda.is_available() else "cpu"
            tok = AutoTokenizer.from_pretrained(str(root), trust_remote_code=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(
                str(root), trust_remote_code=True, dtype=torch.float16 if device == "cuda" else torch.float32
            ).to(device).eval()
            _mt[direction] = (tok, model, IndicProcessor(inference=True), device)
            log.info("IndicTrans2 %s loaded on %s in %.1fs", direction, device, time.perf_counter() - t)
        return _mt[direction]


BEAMS = 5


def translate(texts: list[str], src: str, tgt: str, alternatives: bool = False) -> dict:
    """Translate a batch of sentences. One of src/tgt must be English. With `alternatives`, also returns every beam's
    candidate with its average log-probability, best first ({'alternatives': [[(text, score), …], …]})."""
    if src == tgt:
        return {"texts": list(texts), "engine": None}
    if src not in IT2_TAGS or tgt not in IT2_TAGS or "en" not in (src, tgt):
        raise LanguageUnavailable(f"No offline translation for {src} → {tgt}")
    direction = "indic-en" if tgt == "en" else "en-indic"
    tok, model, ip, device = _indictrans(direction)
    import torch

    n = BEAMS if alternatives else 1
    with _mt_run[direction]:
        # postprocess_batch takes one placeholder map per output sentence off the processor's queue, so with n
        # outputs per input the input is preprocessed n times (one copy each is used).
        batch = ip.preprocess_batch([t for t in texts for _ in range(n)], src_lang=IT2_TAGS[src], tgt_lang=IT2_TAGS[tgt])[::n]
        enc = tok(batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True).to(device)
        with torch.inference_mode():
            # use_cache=False: the model repo's decoder expects the legacy tuple KV-cache that transformers 4.4x+ replaced.
            out = model.generate(**enc, use_cache=False, min_length=0, max_length=256, num_beams=BEAMS, num_return_sequences=n,
                                 output_scores=alternatives, return_dict_in_generate=True)
        decoded = ip.postprocess_batch(tok.batch_decode(out.sequences, skip_special_tokens=True, clean_up_tokenization_spaces=True), lang=IT2_TAGS[tgt])
    if not alternatives:
        return {"texts": decoded, "engine": MT_ENGINE}
    scores = out.sequences_scores.tolist()
    alts = [[(decoded[i * n + j], round(scores[i * n + j], 4)) for j in range(n)] for i in range(len(texts))]
    return {"texts": [a[0][0] for a in alts], "alternatives": alts, "engine": MT_ENGINE}


def translate_patient(text: str, lang: str) -> dict:
    """A patient's sentence → English, with the checks in mt_checks: what was rewritten for the translator, and
    where the translation is unsure. {'text', 'engine', 'rewrites', 'unsure'}."""
    from .mt_checks import prepare, unsure

    given, rewrites = prepare(text, lang)
    out = translate([given], lang, "en", alternatives=True)
    best = out["texts"][0]
    return {"text": best, "engine": out["engine"], "rewrites": rewrites, "unsure": unsure(given, best, out["alternatives"][0])}


def translate_symptoms(intake: dict) -> dict:
    """English for every free-text symptom entered in another language, translated here from the patient's own
    words (`original_text`, kept unchanged) — English sent by the browser is not trusted. If translation cannot
    run, whatever English came with the entry stays and no engine is claimed for it."""
    out = []
    for s in intake.get("symptoms") or []:
        s = dict(s)
        lang = s.get("language") or "en"
        if lang != "en" and s.get("original_text"):
            try:
                tr = translate_patient(s["original_text"], lang)
                prior = s.get("engine") or ""
                heard_by = prior.split(" + ")[0] if prior and prior != MT_ENGINE else ("Browser speech recognition" if s.get("source") == "voice" else None)
                s["text"] = tr["text"]
                s["engine"] = f"{heard_by} + {MT_ENGINE}" if heard_by else MT_ENGINE
                s["mt_rewrites"], s["mt_unsure"] = tr["rewrites"], tr["unsure"]
            except LanguageUnavailable as e:
                log.warning("symptom left untranslated: %s", e)
            except Exception:
                log.exception("translation failed; symptom left untranslated")
        out.append(s)
    return {**intake, "symptoms": out}


# ---------------------------------------------------------------- status

def status() -> dict:
    """Which engines are installed and loaded — shown to staff so nobody assumes a model that is not there."""
    root = models_dir()

    def importable(*mods: str) -> bool:
        import importlib.util

        return all(importlib.util.find_spec(m) is not None for m in mods)

    return {
        "asr": {
            "engine": asr_engine_name(),
            "installed": (root / get_settings().asr_model / "assets" / "encoder.onnx").exists()
            and importable("torch", "onnxruntime", "transformers", "av"),
            "loaded": _asr is not None,
            "languages": sorted(ASR_LANGS),
        },
        "translation": {
            "engine": MT_ENGINE,
            "installed": all((root / f"indictrans2-{d}-dist-200M" / "config.json").exists() for d in ("indic-en", "en-indic"))
            and importable("torch", "transformers", "IndicTransToolkit"),
            "loaded": sorted(_mt),
            "languages": sorted(set(IT2_TAGS) - {"en"}),
        },
    }


def preload() -> None:
    """Warm the models in the background so the first patient does not wait for loading."""

    def run():
        # The first generate() call is several times slower than later ones, so translate one phrase.
        # English → Indic (~1.4 GB) is not warmed: intake never needs it, so it loads only when asked for.
        warm = (("asr", _conformer), ("indic-en", lambda: translate(["ଜ୍ୱର"], "or", "en")))
        for name, fn in warm:
            try:
                fn()
            except LanguageUnavailable as e:
                log.info("%s not preloaded: %s", name, e)
            except Exception:
                log.exception("%s preload failed", name)

    threading.Thread(target=run, name="language-preload", daemon=True).start()
