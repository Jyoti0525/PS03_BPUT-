"""B9: a second speech engine (Sarvam Saaras, online) hears the same recording; where the two disagree on a number, a
symptom or most words, the note says so and shows both. Against a stand-in Sarvam and offline engine: no credits spent,
no models loaded."""

import time

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app import asr_check, language, sarvam, whisper_asr

OFFLINE = "IndicConformer-600M int8 (AI4Bharat, offline)"


# ── the comparison ─────────────────────────────────────
@pytest.mark.parametrize("text,lang,want", [
    ("ଶହେ ଆଠ ପ୍ରକାର", "or", "108 ପ୍ରକାର"),
    ("ଉଣେଇଶ ହଜାର ପାଞ୍ଚଶହ ବର୍ଗ", "or", "19500 ବର୍ଗ"),
    ("19,500 ବର୍ଗ 14ଟି", "or", "19500 ବର୍ଗ 14"),
    ("ଅଠରଟି ପଦକ", "or", "18 ପଦକ"),
    ("ଦୁଇ ତିନି ଦିନ", "or", "2 3 ଦିନ"),  # two numbers, not five
    ("एक सौ चालीस बटा नब्बे", "hi", "140 बटा 90"),
    ("बुखार 101.5", "hi", "बुखार 101.5"),
    ("୧୦୨ ଜ୍ୱର", "or", "102 ଜର"),  # Odia digits; the silent ୱ, as the lexicon's loose form
])
def test_spoken_numbers_and_spellings_compare_as_one(text, lang, want):
    assert asr_check.normalise(text, lang) == want


def test_same_words_written_differently_agree():
    # FLEURS Odia: the offline engine writes number words, Sarvam writes digits
    a = "ରବୀନ୍ ଉଥାପ୍ପା ଏଗାରଟି ଚୌକା ଓ ଦୁଇ ଛକ୍କା ମାରି ଏକଚାଳିଶଟି ବଲ୍ରେ ସତୁରି ରନ୍ କରିଥିଲେ"
    b = "ରବିନ ଉଥାପ୍ପା ୧୧ଟି ଚୌକା ଓ ୨ ଛକା ମାରି ୪୧ଟି ବଲ୍ରେ ୭୦ ରନ୍ କରିଥିଲେ।"
    c = asr_check.compare(a, b, "or", "offline", "online")
    assert not c["disagree"] and c["agreement"] > 0.9


def test_live_test_cases_6_oct():
    """Sarvam's voice reading clinical sentences, heard by both engines through the API."""
    # Real catch: the offline engine heard सौ as सो and lost the diastolic 100 (its translation said "162")
    bp = asr_check.compare("मेरा बीपी एक सौ साठ बटा सो आया था", "मेरा बीपी एक सौ साठ बटा सौ आया था।", "hi", "offline", "online")
    assert bp["differences"] == ["numbers: 160 (offline) vs 100, 160 (online)"]
    # Not a disagreement: a number joined to its unit, and ଵ written for the silent ୱ
    same = asr_check.compare("ମୋର ଚାରିଦିନ ହେଲା ଜ୍ଵର ଓ ଝାଡ଼ ହେଉଛି", "ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର ଓ ଝାଡ଼ ହେଉଛି।", "or", "offline", "online")
    assert not same["disagree"] and same["agreement"] == 1.0


def test_spoken_odia_spellings_the_live_test_found():
    from app.mt_checks import prepare
    from app.triage.findings import scan_text

    heard = "ମୋର ଚାରିଦିନ ହେଲା ଜ୍ଵର ଓ ଝାଡ଼ ହେଉଛି"  # ଵ for ୱ; ଝାଡ଼ without its ା (both engines)
    assert {f for f, x in scan_text(heard, "").items() if x.value} == {"fever", "diarrhoea"}
    assert prepare(heard, "or")[0] == "ମୋର ଚାରିଦିନ ହେଲା ଜ୍ୱର ଓ ଅତିସାର ହେଉଛି"  # the translator had said "cough"
    for other in ("ଗଛ ଝାଡ଼ ମୂଳେ ବସିଛି", "ଝାଡ଼ ହେଉନି"):  # a bush; "no stool": never read as diarrhoea
        assert "diarrhoea" not in {f for f, x in scan_text(other, "").items() if x.value}


def test_odia_number_words_with_a_vowel_sign_slipped_are_still_numbers():
    # IndicWhisper on FLEURS Odia: "11 fours and 2 sixes off 41 balls, 70 runs"; a 19,500 km² park
    said = asr_check.normalise("ଏଗାର ଟି ଚୌକା ଓ ଦୁଇ ଛକା ମାରି ଏକଚାଳଶ ଟି ବଲ୍ରେ ସତୋରୀ ରନ୍", "or")
    assert asr_check._NUM.findall(said) == ["11", "2", "41", "70"]
    assert asr_check.normalise("ଊଣାଇଶ ହଜାର ପାଞ୍ଚ ଶହେ ବର୍ଗ", "or") == "19500 ବର୍ଗ"
    assert asr_check.normalise("ବିସ୍ତାର", "or") != "72"  # an ordinary word two vowel signs from ବାସ୍ତରି stays a word


def test_a_different_number_or_symptom_is_always_a_disagreement():
    days = asr_check.compare("ମୋର ତିନି ଦିନ ହେଲା ଜର", "ମୋର ତେର ଦିନ ହେଲା ଜର", "or", "offline", "online")
    assert days["disagree"] and days["differences"] == ["numbers: 3 (offline) vs 13 (online)"]
    chest = asr_check.compare("मुझे तीन दिन से बुखार है", "मुझे तीन दिन से बुखार है और सीने में दर्द है", "hi", "offline", "online")
    assert chest["disagree"] and "chest pain: heard by online only" in chest["differences"]
    other = asr_check.compare("मुझे तीन दिन से बुखार है", "कल रात खाना नहीं खाया गया", "hi", "offline", "online")
    assert other["disagree"] and other["differences"][-1].startswith("only ")


# ── the speech endpoint ────────────────────────────────
@pytest.fixture
def engines(monkeypatch):
    calls = {"sarvam": 0}

    def offline(data, lang):
        if data == b"silence":
            raise language.AudioRejected("No speech was heard")
        if lang == "en" or data == b"no-model":
            raise language.LanguageUnavailable("No offline speech model")
        return {"text": "मुझे तीन दिन से बुखार है", "language": lang, "engine": OFFLINE, "seconds_audio": 2.0, "seconds_taken": 0.4}

    def online(audio, lang, filename="audio.webm", translate=False):
        calls["sarvam"] += 1
        return {"text": "मुझे तेरह दिन से बुखार है" if lang == "hi" else "I have fever", "language": lang, "engine": sarvam.STT_ENGINE}

    monkeypatch.setattr(language, "transcribe", offline)
    monkeypatch.setattr(language, "translate_patient", lambda text, lang: {"text": f"EN<{text}>", "engine": language.MT_ENGINE, "rewrites": [], "unsure": []})
    monkeypatch.setattr(sarvam, "transcribe", online)
    monkeypatch.setattr(sarvam, "enabled", lambda: True)
    return calls


def _post(client, headers, data=b"audio", lang="hi", second=True):
    form = {"language": lang, **({"second_opinion": "true"} if second else {})}
    return client.post(f"{API}/speech/transcribe", headers=headers, files={"audio": ("speech.webm", data, "audio/webm")}, data=form)


def test_second_engine_hears_the_same_recording_and_both_are_returned(client, nurse, engines):
    r = _post(client, nurse).json()
    assert r["engine"] == OFFLINE and r["translation"]["text"] == "EN<मुझे तीन दिन से बुखार है>"
    s = r["second_opinion"]
    assert s["engine"] == sarvam.STT_ENGINE and s["text"] == "मुझे तेरह दिन से बुखार है" and s["disagree"]
    assert s["differences"] == [f"numbers: 3 ({OFFLINE}) vs 13 ({sarvam.STT_ENGINE})"]
    assert s["translation"] == "EN<मुझे तेरह दिन से बुखार है>"  # the doctor reads both in English


def test_no_audio_goes_online_unless_the_patient_allowed_ai(client, nurse, engines):
    r = _post(client, nurse, second=False).json()
    assert "second_opinion" not in r and engines["sarvam"] == 0


def test_an_unusable_recording_is_refused_before_anything_is_compared(client, nurse, engines):
    assert _post(client, nurse, data=b"silence").status_code == 422


def test_without_the_offline_model_sarvam_alone_transcribes_and_says_so(client, nurse, engines):
    r = _post(client, nurse, data=b"no-model").json()
    assert r["engine"] == sarvam.STT_ENGINE and r["offline_unavailable"] and "second_opinion" not in r
    en = _post(client, nurse, lang="en").json()  # English: no offline model at all
    assert en["text"] == "I have fever" and en["translation"] is None
    assert _post(client, nurse, data=b"no-model", second=False).status_code == 503


@pytest.fixture
def whisper(engines, monkeypatch):
    """IndicWhisper (offline second engine) installed for Hindi; real model never loaded in tests."""
    heard = []

    def hear(data, lang):
        heard.append(lang)
        return {"text": "मुझे तीन दिन से बुखार और खांसी है", "language": lang, "engine": whisper_asr.ENGINE}

    monkeypatch.setattr(whisper_asr, "available", lambda lang: lang == "hi")
    monkeypatch.setattr(whisper_asr, "transcribe", hear)
    return heard


def _check(client, headers, job):
    for _ in range(100):
        r = client.get(f"{API}/speech/second/{job}", headers=headers)
        if r.status_code != 200 or "pending" not in r.json():
            return r
        time.sleep(0.02)
    raise AssertionError("offline check never finished")


def test_with_no_connection_the_offline_second_engine_checks_after_the_reply(client, nurse, doctor, whisper, monkeypatch):
    def down(*a, **kw):
        raise sarvam.SarvamUnavailable("Could not reach Sarvam")

    monkeypatch.setattr(sarvam, "transcribe", down)
    r = _post(client, nurse).json()
    assert r["engine"] == OFFLINE and r["translation"]  # the patient hears the read-back without waiting
    s = r["second_opinion"]
    assert s["engine"] == whisper_asr.ENGINE and s["pending"]
    assert _check(client, doctor, s["pending"]).status_code == 404  # only the one who recorded it
    done = _check(client, nurse, s["pending"]).json()
    assert done["engine"] == whisper_asr.ENGINE and done["disagree"] and f"cough: heard by {whisper_asr.ENGINE} only" in done["differences"]
    assert done["translation"] == "EN<मुझे तीन दिन से बुखार और खांसी है>"
    monkeypatch.setattr(sarvam, "enabled", lambda: False)  # no key at all: the same
    assert _check(client, nurse, _post(client, nurse).json()["second_opinion"]["pending"]).json()["engine"] == whisper_asr.ENGINE
    assert whisper == ["hi", "hi"]


def test_a_failed_offline_check_says_so(client, nurse, whisper, monkeypatch):
    def broken(data, lang):
        raise RuntimeError("out of memory")

    monkeypatch.setattr(sarvam, "enabled", lambda: False)
    monkeypatch.setattr(whisper_asr, "transcribe", broken)
    done = _check(client, nurse, _post(client, nurse).json()["second_opinion"]["pending"]).json()
    assert done["error"].startswith("The second engine failed") and "pending" not in done


def test_without_indicconformer_the_offline_second_engine_transcribes_and_is_waited_for(client, nurse, whisper, monkeypatch):
    monkeypatch.setattr(sarvam, "enabled", lambda: False)
    r = _post(client, nurse, data=b"no-model").json()
    assert r["engine"] == whisper_asr.ENGINE and r["offline_unavailable"] and "second_opinion" not in r


def test_offline_second_engine_is_used_only_when_sarvam_cannot_and_the_patient_allowed_ai(client, nurse, whisper, monkeypatch):
    assert _post(client, nurse).json()["second_opinion"]["engine"] == sarvam.STT_ENGINE and whisper == []
    monkeypatch.setattr(sarvam, "enabled", lambda: False)
    assert "second_opinion" not in _post(client, nurse, second=False).json() and whisper == []
    monkeypatch.setattr(whisper_asr, "available", lambda lang: False)  # neither engine: no second opinion, no error
    assert "second_opinion" not in _post(client, nurse).json()


def test_engines_lists_both_second_engines(client, nurse):
    s = client.get(f"{API}/language/engines", headers=nurse).json()["asr_second"]
    assert s["online"]["engine"] == sarvam.STT_ENGINE and s["offline"]["engine"] == whisper_asr.ENGINE
    assert s["offline"]["installed"] is False  # tests run with no models


# ── the note ───────────────────────────────────────────
def test_note_shows_both_hearings_and_counts_a_symptom_only_the_second_heard(client, nurse):
    said = "मुझे तीन दिन से बुखार है"
    voice = {"text": "I have had fever for three days", "original_text": said, "language": "hi", "source": "voice",
             "confirmed_by_readback": True, "engine": f"{OFFLINE} + {language.MT_ENGINE}",
             "second_hearing": {"engine": sarvam.STT_ENGINE, "text": f"{said} और सीने में दर्द है", "translation": "I have had fever for three days and chest pain"}}
    _, body = new_intake(client, nurse, chief_complaint="fever", vitals={}, symptoms=[voice])
    note = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()["note"]
    d = next(x for x in note["disagreements"] if x["field"] == "Voice transcript")
    assert [v["engine"] for v in d["values"]] == [OFFLINE, sarvam.STT_ENGINE]
    assert "chest pain: heard by Sarvam Saaras v3 (online) only" in d["action"]
    assert any(f["code"] == "DISAGREE" and f["label"].startswith("Voice transcript") for f in note["flags"])
    chest = note["triage"]["findings"]["chest_pain"]
    assert chest["value"] is True and "second speech engine only" in chest["evidence"][0]


def test_engines_that_agree_add_nothing_to_the_note(client, nurse):
    said = "मुझे तीन दिन से बुखार है"
    voice = {"text": "fever for three days", "original_text": said, "language": "hi", "source": "voice", "confirmed_by_readback": True,
             "engine": OFFLINE, "second_hearing": {"engine": sarvam.STT_ENGINE, "text": "मुझे 3 दिन से बुख़ार है।"}}
    _, body = new_intake(client, nurse, chief_complaint="fever", vitals={}, symptoms=[voice])
    note = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()["note"]
    assert not any(x["field"] == "Voice transcript" for x in note["disagreements"])
