"""Per-language confidence threshold, Bhashini fallback, Kannada in the speech evaluation set."""
import pytest

from test_wednesday import intake


def _flags(e):
    return {f["code"]: f for f in e["note"]["flags"]}


def _voice(text, conf, lang="or"):
    return {"text": "chest pain since morning", "original_text": text, "language": lang, "source": "voice",
            "confirmed_by_readback": True, "engine": "IndicConformer-600M int8 (AI4Bharat, offline)", "confidence": conf}


def test_low_confidence_voice_becomes_a_question_and_rules_still_read_it(client, nurse):
    _, e = intake(client, nurse, language="or", chief_complaint="Chest pain", symptoms=[_voice("ଛାତି ଯନ୍ତ୍ରଣା", 0.80)])
    f = _flags(e)
    assert "ASR-LOW-CONF" in f and "80 %" in f["ASR-LOW-CONF"]["reason"] and "92 %" in f["ASR-LOW-CONF"]["reason"]
    assert "ଛାତି ଯନ୍ତ୍ରଣା" in f["ASR-LOW-CONF"]["reason"]
    assert e["urgency"] in ("yellow", "red")  # chest pain still counts: a possible danger sign is never dropped


def test_confident_voice_is_not_flagged(client, nurse):
    _, e = intake(client, nurse, language="or", chief_complaint="Chest pain", symptoms=[_voice("ଛାତି ଯନ୍ତ୍ରଣା", 0.97)])
    assert "ASR-LOW-CONF" not in _flags(e)


def test_confidence_must_be_a_probability(client, nurse):
    from conftest import API

    with pytest.raises(AssertionError):
        intake(client, nurse, symptoms=[_voice("x", 1.7)])
    assert API


def test_threshold_per_language_with_default():
    from app import language

    assert language.min_confidence("or") == 0.92 and language.min_confidence("hi") == 0.85
    assert language.min_confidence("ta") == 0.92  # unmeasured languages get the default


def test_bhashini_used_only_when_offline_translation_cannot_run(monkeypatch):
    from app import bhashini, language

    def off(*a, **k):
        raise language.LanguageUnavailable("Translation model not downloaded")

    monkeypatch.setattr(language, "translate", off)
    monkeypatch.setattr(bhashini, "enabled", lambda: False)
    with pytest.raises(language.LanguageUnavailable):
        language.translate_any(["Drink water"], "en", "kn")
    monkeypatch.setattr(bhashini, "enabled", lambda: True)
    monkeypatch.setattr(bhashini, "translate", lambda t, s, g: {"texts": ["ನೀರು ಕುಡಿಯಿರಿ"], "engine": bhashini.ENGINE})
    assert language.translate_any(["Drink water"], "en", "kn") == {"texts": ["ನೀರು ಕುಡಿಯಿರಿ"], "engine": "Bhashini (online)"}


def test_bhashini_off_in_stub_profile(monkeypatch):
    from app.config import Settings

    s = Settings(profile="stub", bhashini_user_id="u", bhashini_api_key="k")
    assert s.bhashini_user_id == "u"  # an explicit setting wins over the profile
    assert Settings(profile="stub").bhashini_api_key is None


def test_offline_odia_voice_needs_no_network(client, nurse, monkeypatch):
    from pathlib import Path

    from conftest import API

    from app import tts

    real = Path(__file__).resolve().parents[2] / "models"
    monkeypatch.setattr(tts, "model_dir", lambda lang: (real / f"mms-tts-{tts.CODES[lang]}") if lang in tts.CODES and (real / f"mms-tts-{tts.CODES[lang]}" / "config.json").exists() else None)
    if not tts.available("or"):
        pytest.skip("MMS-TTS Odia model not downloaded")
    r = client.post(f"{API}/language/speak", json={"text": "ନମସ୍କାର", "language": "or", "allow_online": False}, headers=nurse)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"
    assert r.headers["x-voice-engine"] == tts.ENGINE


def test_no_offline_voice_and_online_not_allowed_is_refused(client, nurse):
    from conftest import API

    r = client.post(f"{API}/language/speak", json={"text": "வணக்கம்", "language": "ta", "allow_online": False}, headers=nurse)
    assert r.status_code == 422
