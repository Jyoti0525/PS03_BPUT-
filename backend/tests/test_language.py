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


def test_translation_from_an_unmeasured_language_always_warns(client, nurse):
    """Measured 8 Oct (scripts/santali_e2e.py): IndicTrans2 turned a Santali "chest pain to the left arm" into "the
    outbreak of the virus has spread", and the note came out YELLOW instead of RED. No word list can catch that in
    Santali, so the reviewer is always told to ask again."""
    sym = {"text": "The outbreak of the virus has spread from day to day.", "original_text": "ᱵᱳᱭᱫᱟ ᱨᱮᱭᱟᱜ ᱜᱷᱟᱹᱞ", "language": "sat",
           "source": "text", "engine": language.MT_ENGINE}
    _, body = new_intake(client, nurse, symptoms=[sym])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    flag = next(f for f in enc["note"]["flags"] if f["code"] == "MT-CHECK")
    assert flag["severity"] == "warning" and "has not been measured" in flag["reason"]


@needs("torch")
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
            return type("Out", (), {"sequences": kw["input_ids"]})()

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


# ── translation checks, from a live kiosk test on 5 Oct (Odia and Hindi, laptop microphone) ──
# What IndicConformer heard, and what IndicTrans2 made of it before these checks existed:
HEARD = [
    ("ମୋର ବହୁତ ଦିନ ହେଲା ଜର ଆଉ ମୁଣ୍ଡ ବିନ୍ଧୁଛି", "I've had a headache for a long time."),  # fever dropped
    ("ପିଲାଟି ଦିଇ ଦିନ ହେଲା କିଛି ଖାଉନି ଆଉ ତାକୁ ବହୁତ ଝାଡ଼ା ବି ହୋଇଉଛି", "The child has not eaten for days and is sweating a lot."),  # diarrhoea → sweating
    ("ମୋ ବୟସ ଛପନ ବର୍ଷ ଆଉ ମୋର ଛାତି ବି ଦରଦ ହଉଛି", "I'm sixty-six years old and my chest hurts too."),  # 56 → 66
    ("मुझे दो दिन से तेज बुखार और खांसी है", "I have a high fever and cough for two days."),
    ("मुझे सीने में दिक्कत है और सांस लेने में तकलीफ है", "I have chest pain and shortness of breath."),
]


def test_spoken_odia_and_hindi_spellings_are_read_from_the_patients_own_words():
    from app.triage.findings import scan_text

    found = [{f for f, x in scan_text(orig, "").items() if x.value is True} - {"pain"} for orig, _ in HEARD]
    assert found == [{"fever", "headache"}, {"diarrhoea"}, {"chest_pain"}, {"fever", "cough"}, {"chest_pain", "breathless"}]
    assert not any(x.value for x in scan_text("ଏହା ଜରୁରୀ ନୁହେଁ", "").values())  # ଜରୁରୀ ("urgent") is not ଜର (fever)
    assert scan_text("ତିନି ଦିନ ହେଲା ଝାଡ଼ା ହୋଇନି", "")["diarrhoea"].value is False


def test_translation_errors_are_caught_against_the_patients_words_and_labelled():
    from app.triage.findings import extract, translation_check

    sym = [{"text": en, "original_text": orig, "language": "or" if i < 3 else "hi", "source": "voice", "confirmed_by_readback": True} for i, (orig, en) in enumerate(HEARD)]
    checks = [translation_check(s) for s in sym]
    assert checks[0]["missed"] == ["fever"] and checks[1] == {**checks[1], "missed": ["diarrhoea"], "added": ["sweating"]}
    assert checks[3] is None and checks[4] is None
    sweat = extract({"chief_complaint": "", "symptoms": sym})["sweating"]
    assert sweat.value is True and "machine translation only" in sweat.evidence[0]  # still counted (over-triage is safer), but labelled


def test_translator_is_given_standard_words_and_digits_but_the_record_keeps_the_patients_words():
    from app.mt_checks import prepare

    assert prepare(HEARD[0][0], "or")[0] == "ମୋର ବହୁତ ଦିନ ହେଲା ଜ୍ୱର ଆଉ ମୁଣ୍ଡ ବିନ୍ଧୁଛି"
    assert prepare(HEARD[1][0], "or")[0] == "ପିଲାଟି ଦିଇ ଦିନ ହେଲା କିଛି ଖାଉନି ଆଉ ତାକୁ ବହୁତ ଅତିସାର ବି ହୋଇଉଛି"
    given, changes = prepare(HEARD[2][0], "or")
    assert given.startswith("ମୋ ବୟସ 56 ବର୍ଷ") and changes[0] == {"from": "ଛପନ", "to": "56", "why": "number word written as digits"}
    assert prepare("ଝାଡ଼ାରେ ରକ୍ତ ଯାଉଛି", "or")[0] == "ମଳରେ ରକ୍ତ ଯାଉଛି"
    assert prepare("ତିନି ଦିନ ହେଲା ଝାଡ଼ା ହୋଇନି", "or")[0] == "3 ଦିନ ହେଲା ମଳ ବାହାରୁ ନାହିଁ"
    assert prepare("मुझे दो दिन से बुखार है, दवा दो", "hi")[0] == "मुझे 2 दिन से बुखार है, दवा दो"  # "give the medicine" stays a word


def test_unsure_translation_numbers_and_symptoms_are_named():
    from app.mt_checks import english_numbers, unsure

    assert english_numbers("I'm sixty-six, fever for 3 days, twenty two times") == [66, 3, 22]
    alts = [("I'm sixty-six years old and my chest hurts too.", -0.546), ("I'm fifty-six years old and my chest hurts too.", -0.547),
            ("I'm sixty-six years old and my chest is hurting too.", -0.583)]
    assert unsure("ମୋ ବୟସ ଛପନ ବର୍ଷ", alts[0][0], alts) == ["number unclear: 66 or 56"]
    assert unsure("ମୋ ବୟସ 56 ବର୍ଷ", "I am 6 years old", [("I am 6 years old", -0.4)]) == ["the patient's words have 56, the translation does not"]
    stool = [("The child is sweating a lot", -0.50), ("The child has a lot of diarrhoea", -0.55), ("The child has fever", -0.9)]
    assert unsure("…", stool[0][0], stool) == ["may also mean: diarrhoea", "unsure of: sweating with symptoms"]  # far candidate ignored


def test_note_names_the_translation_problem_and_keeps_each_onset_with_its_own_complaint(client, nurse, monkeypatch):
    """The kiosk's English is kept only when the server cannot translate; the lexicon check still catches its errors."""
    def unavailable(direction):
        raise language.LanguageUnavailable("not in this test")

    monkeypatch.setattr(language, "_indictrans", unavailable)  # an earlier test may have loaded the real model
    sym = [{"text": en, "original_text": orig, "language": "or" if i < 3 else "hi", "source": "voice", "confirmed_by_readback": True} for i, (orig, en) in enumerate(HEARD)]
    _, body = new_intake(client, nurse, symptoms=sym, chief_complaint=HEARD[0][1])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    flag = next(f for f in enc["note"]["flags"] if f["code"] == "MT-CHECK")
    assert flag["severity"] == "warning" and "translation leaves out fever" in flag["reason"]
    assert "translation says sweating with symptoms, the patient's words do not" in flag["reason"]
    onsets = {t["event"]: (t["certainty"], t["raw"]) for t in enc["note"]["timeline"] if t["event"].startswith("Onset")}
    assert onsets[f"Onset: {HEARD[3][1]}"] == ("STATED", "दो दिन")  # two days belongs to the fever and cough …
    assert onsets[f"Onset: {HEARD[0][1]}"][0] == "VAGUE"  # … not to the headache "for a long time"
    assert "OR, HI" in enc["note"]["timeline"][-1]["event"]


@needs("torch", "transformers", "IndicTransToolkit")
def test_real_translator_gets_the_three_odia_sentences_right_after_preparation(real_models):
    out = [language.translate_patient(orig, "or") for orig, _ in HEARD[:3]]
    assert "fever" in out[0]["text"].lower() and "headache" in out[0]["text"].lower()
    assert "diarrh" in out[1]["text"].lower() and "sweat" not in out[1]["text"].lower()
    assert "56" in out[2]["text"] and "chest" in out[2]["text"].lower()
