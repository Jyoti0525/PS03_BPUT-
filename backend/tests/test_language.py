"""Speech + translation. API tests run with no models installed (conftest points JEEVIA_MODELS_DIR at an empty
folder) and check that nothing is invented; the model tests load the real offline models when present."""

import io
from pathlib import Path

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app import language

REAL_MODELS = Path(__file__).resolve().parents[2] / "models"
needs = lambda *mods: pytest.mark.skipif(any(__import__("importlib").util.find_spec(m) is None for m in mods), reason=f"needs {mods}")  # noqa: E731


def wav_bytes(samples, rate=16_000) -> bytes:
    import wave

    import numpy as np

    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


# ── without models: honest failures ─────────────────────

def test_engines_report_not_installed(client, nurse):
    s = client.get(f"{API}/language/engines", headers=nurse).json()
    assert s["asr"]["installed"] is False and s["translation"]["installed"] is False


@needs("av", "numpy")
def test_transcribe_without_model_is_503_not_a_fake_transcript(client, nurse):
    import numpy as np

    t = np.arange(32_000) / 16_000
    r = client.post(f"{API}/speech/transcribe", headers=nurse, files={"audio": ("a.wav", wav_bytes(0.3 * np.sin(2 * np.pi * 220 * t)), "audio/wav")}, data={"language": "or"})
    assert r.status_code == 503 and "not downloaded" in r.json()["detail"]


@needs("av", "numpy")
def test_silent_or_short_audio_is_rejected(client, nurse):
    import numpy as np

    silent = client.post(f"{API}/speech/transcribe", headers=nurse, files={"audio": ("s.wav", wav_bytes(np.zeros(32_000)), "audio/wav")}, data={"language": "hi"})
    assert silent.status_code == 422 and "No speech" in silent.json()["detail"]
    short = client.post(f"{API}/speech/transcribe", headers=nurse, files={"audio": ("s.wav", wav_bytes(0.3 * np.ones(1_600)), "audio/wav")}, data={"language": "hi"})
    assert short.status_code == 422 and "too short" in short.json()["detail"]
    junk = client.post(f"{API}/speech/transcribe", headers=nurse, files={"audio": ("j.webm", b"not audio at all", "audio/webm")}, data={"language": "hi"})
    assert junk.status_code == 422


def test_employer_cannot_use_speech(client, employer):
    r = client.post(f"{API}/translate", headers=employer, json={"text": "ଜ୍ୱର", "source": "or", "target": "en"})
    assert r.status_code == 403


def test_untranslatable_symptom_keeps_patient_words_and_claims_no_engine(client, nurse):
    _, body = new_intake(client, nurse, symptoms=[{"text": "ମୋର ଜ୍ୱର ହେଉଛି", "original_text": "ମୋର ଜ୍ୱର ହେଉଛି", "language": "or", "source": "text"}])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    sym = enc["intake"]["symptoms"][0]
    assert sym["text"] == "ମୋର ଜ୍ୱର ହେଉଛି" and not sym.get("engine")


# ── with the real offline models ────────────────────────

@pytest.fixture
def real_models(monkeypatch):
    if not (REAL_MODELS / "indictrans2-indic-en-dist-200M" / "config.json").exists():
        pytest.skip("models not downloaded")
    monkeypatch.setattr(language, "models_dir", lambda: REAL_MODELS)


@needs("torch", "transformers", "IndicTransToolkit")
def test_odia_and_hindi_translate_to_english(real_models):
    out = language.translate(["ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର ହେଉଛି", "मुझे तीन दिन से सीने में दर्द है"], "or", "en")
    assert out["engine"] == language.MT_ENGINE
    odia, hindi = (t.lower() for t in out["texts"])
    assert "fever" in odia and "four" in odia
    assert "chest" in hindi and "pain" in hindi


@needs("torch", "transformers", "IndicTransToolkit")
def test_english_advice_translates_to_odia(real_models):
    out = language.translate(["Please go to the emergency room now."], "en", "or")
    assert any("଀" <= ch <= "୿" for ch in out["texts"][0])  # Odia script


@needs("torch", "transformers", "IndicTransToolkit")
def test_intake_symptoms_get_english_with_engine_named(real_models):
    intake = language.translate_symptoms({"symptoms": [
        {"text": "मुझे बुखार है", "original_text": "मुझे बुखार है", "language": "hi", "source": "voice"},
        {"text": "I have a cough", "original_text": "I have a cough", "language": "en", "source": "text"},
    ]})
    hi, en = intake["symptoms"]
    assert "fever" in hi["text"].lower() and hi["original_text"] == "मुझे बुखार है"
    assert hi["engine"] == f"Browser speech recognition + {language.MT_ENGINE}"
    assert en["text"] == "I have a cough" and not en.get("engine")


@needs("torch", "onnxruntime", "transformers", "av", "numpy")
def test_speech_model_runs_end_to_end(real_models):
    """No recorded Odia clip ships with the repo, so this checks the pipeline runs on the real model;
    accuracy is measured separately on recorded samples."""
    import numpy as np

    rng = np.random.default_rng(0)
    t = np.arange(48_000) / 16_000
    noisy_tone = 0.2 * np.sin(2 * np.pi * 180 * t) * (1 + np.sin(2 * np.pi * 3 * t)) + 0.02 * rng.standard_normal(t.size)
    try:
        out = language.transcribe(wav_bytes(noisy_tone), "or")
        assert out["engine"] == language.asr_engine_name() and out["seconds_audio"] == 3.0
    except language.AudioRejected as e:
        assert "No words were recognised" in str(e)  # the model ran and honestly found no words


def test_rules_read_the_original_words_when_translation_is_wrong(client, nurse):
    """Measured 4 Oct: IndicTrans2 rendered "ବହୁତ ଝାଡ଼ା ହେଉଛି" (a lot of loose stools) as "sweating a lot".
    The diarrhoea finding must still come from the Odia original, and the reviewer is told to check."""
    from app.triage.findings import extract

    sym = {"text": "The child has not eaten for two days and is sweating a lot.", "original_text": "ପିଲାଟି ଦୁଇ ଦିନ ହେଲା ଖାଉନି ଓ ବହୁତ ଝାଡ଼ା ହେଉଛି",
           "language": "or", "source": "voice", "confirmed_by_readback": True, "engine": f"{language.asr_engine_name()} + {language.MT_ENGINE}"}
    found = extract({"chief_complaint": "", "symptoms": [sym]})
    assert found["diarrhoea"].value is True
    assert any("original or" in ev for ev in found["diarrhoea"].evidence)

    _, body = new_intake(client, nurse, symptoms=[sym])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    flag = next(f for f in enc["note"]["flags"] if f["code"] == "MT-CHECK")
    assert language.MT_ENGINE in flag["reason"] and "or" in flag["reason"]


def test_overlapping_translations_do_not_hang(monkeypatch):
    """IndicProcessor hands placeholder maps from preprocess to postprocess through one shared queue and clears it
    afterwards; two overlapping translations used to leave one waiting forever (seen live, 5 Oct)."""
    import queue
    import threading
    import time

    import torch

    class Processor:  # same queue behaviour as IndicTransToolkit.processor.IndicProcessor
        def __init__(self):
            self.q = queue.Queue()

        def preprocess_batch(self, texts, src_lang, tgt_lang):
            for _ in texts:
                self.q.put({})
            time.sleep(0.05)
            return list(texts)

        def postprocess_batch(self, sents, lang):
            maps = [self.q.get(timeout=2) for _ in sents]  # the real one has no timeout: it hangs
            self.q.queue.clear()
            return [s for s, _ in zip(sents, maps)]

    class Tok:
        def __call__(self, batch, **kw):
            class Enc(dict):
                def to(self, device):
                    return self
            return Enc(input_ids=torch.zeros((len(batch), 1)))

        def batch_decode(self, out, **kw):
            return ["x"] * len(out)

    class Model:
        def generate(self, **kw):
            time.sleep(0.05)
            return kw["input_ids"]

    monkeypatch.setattr(language, "_indictrans", lambda d: (Tok(), Model(), Processor.shared, "cpu"))
    Processor.shared = Processor()
    errors = []

    def run():
        try:
            language.translate(["ଜ୍ୱର"], "or", "en")
        except Exception as e:  # noqa: BLE001 — collected and asserted below
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not errors and not any(t.is_alive() for t in threads)
