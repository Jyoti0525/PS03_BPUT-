"""E6 reminder calls: logistics and bounded questions only; a danger sign ends the call and pages a person; the more
serious the case, the less AI on the call; nothing about health on a phone that is not the patient's own."""

import re
import uuid
from datetime import date, timedelta

import pytest
from conftest import API, DEVICE, login

from app import calls

NORMAL = {"bp_systolic": 120, "bp_diastolic": 80, "pulse": 80, "spo2": 98, "temp_f": 98.4, "resp_rate": 16, "avpu": "A"}
ADVICE = ("rest", "take ", "tablet", "paracetamol", "drink", "don't worry", "do not worry", "nothing serious", "normal", "go to")


@pytest.fixture(scope="module")
def hw(client):
    return login(client, "9000000006")


@pytest.fixture(scope="module")
def mo(client):
    return login(client, "9000000007")


def followup(client, nurse, hw, *, name, category="maternal", phone="98110", owner="self", vitals=NORMAL, weeks=30, condition="Type 2 diabetes", lang="en", exam=True):
    past = (date.today() - timedelta(days=3)).isoformat()
    phone = f"{phone}{uuid.uuid4().int % 100000:05d}" if phone else None
    pat = client.post(f"{API}/patients", json={"name": name, "age": 30, "sex": "F", "language": lang, "phone": phone}, headers=nurse).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=nurse).json()
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": category, "language": "en", "chief_complaint": "Routine check-up",
            "vitals": vitals, "consent_id": con["id"], "client_ref": f"c_{uuid.uuid4().hex}"}
    if category == "maternal":
        body["maternal"] = {"gestation_weeks": weeks, "next_checkup": past, "phone_belongs_to": owner, "assigned_worker_id": "usr_hw1"}
    else:
        body["chronic"] = {"condition": condition, "current_medicines": "Metformin", "next_checkup": past, "assigned_worker_id": "usr_hw1"}
    r = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE})
    assert r.status_code == 200, r.text
    if exam:  # the danger-sign check; without it the visit stays UNDETERMINED and only a person may call
        assert client.post(f"{API}/encounters/{r.json()['id']}/observations", json={"exam_done": True}, headers=nurse).status_code == 200
    return next(x for x in client.get(f"{API}/followups", headers=hw).json() if x["patient_id"] == pat["id"])


def say(client, hw, call, *answers):
    for a in answers:
        body = a if isinstance(a, dict) else {"text": a}
        call = client.post(f"{API}/calls/{call['id']}/answer", json=body, headers=hw).json()
    return call


def agent_lines(call) -> str:
    return " ".join(t["text_en"] for t in call["turns"] if t["who"] == "agent").lower()


# ── reading answers (rules, not a model) ──────────────
@pytest.mark.parametrize("said,heard", [
    ("Yes", "yes"), ("haan ji", "yes"), ("हाँ", "yes"), ("ହଁ", "yes"), ("ଆଜ୍ଞା", "yes"),
    ("No", "no"), ("nahi", "no"), ("नहीं", "no"), ("ନାହିଁ", "no"), ("No, but I will try", "no"),
    ("पता नहीं", "unsure"), ("I don't know", "unsure"), ("ଜାଣିନି", "unsure"),
    ("blue", None), ("", None),
    # a hedge is never a yes or a no: "moving less" must not pass "is the baby moving as usual?"
    ("ହଲୁଛି", "yes"), ("କମ୍ ହଲୁଛି", "unsure"), ("बच्चा कम हिल रहा है", "unsure"), ("a little less", "unsure"), ("sometimes", "unsure"),
    # the eight languages added for Sarvam's voice
    ("আজ্ঞে হ্যাঁ", "yes"), ("না", "no"), ("ஆமாம்", "yes"), ("இல்லை", "no"), ("தெரியாது", "unsure"), ("అవును", "yes"), ("లేదు", "no"),
    ("હા", "yes"), ("ખબર નથી", "unsure"), ("ಹೌದು", "yes"), ("ಗೊತ್ತಿಲ್ಲ", "unsure"), ("അതെ", "yes"), ("ഇല്ല", "no"), ("होय", "yes"),
    ("माहीत नाही", "unsure"), ("ਹਾਂ ਜੀ", "yes"), ("ਬਿਲਕੁਲ ਨਹੀਂ", "no"), ("কম নড়ছে", "unsure"),
])
def test_short_answers(said, heard):
    assert calls.read_short_answer(said) == heard


def test_danger_signs_are_read_in_three_languages_with_negation():
    assert [f["finding"] for f in calls.danger_signs("maternal", "मुझे सिरदर्द है")] == ["headache"]
    assert [f["finding"] for f in calls.danger_signs("maternal", "ମୁଣ୍ଡବିନ୍ଧା ହେଉଛି")] == ["headache"]
    assert calls.danger_signs("maternal", "no headache, no bleeding") == []
    assert {f["finding"] for f in calls.danger_signs("chronic", "chest pain since morning")} == {"chest_pain"}
    assert calls.danger_signs("chronic", "a little headache") == []  # headache alone is a pregnancy sign, not a chronic one


def _slots(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def test_every_line_has_every_language_with_the_same_slots():
    cfg = calls.config()
    assert len(calls.LANGS) == 11
    for key, line in cfg["lines"].items():
        assert set(line) == set(calls.LANGS), key
        assert all(_slots(line[lang]) == _slots(line["en"]) for lang in calls.LANGS), key  # {name} etc. never lost
    for kind, words in cfg["answers"].items():
        assert set(words) == set(calls.LANGS), kind
    for k, words in cfg["conditions"].items():
        assert set(calls.LANGS) <= set(words), k
    for prog, qs in cfg["scripts"].items():
        for q in qs:
            if q["kind"] != "identity":
                assert all(q.get(lang) for lang in calls.LANGS), (prog, q["key"])
                assert all(_slots(q[lang]) == _slots(q["en"]) for lang in calls.LANGS), (prog, q["key"])
            for f in q.get("findings", []):
                assert f in calls.red_flags(prog), (prog, f)  # a question's danger sign is also caught when said freely


# ── the call ──────────────────────────────────────────
def test_headache_on_a_maternal_call_ends_it_and_pages_a_person(client, nurse, hw, mo):
    f = followup(client, nurse, hw, name="Call Test One")
    assert f["who_calls"]["who"] == "agent" and f["programme"] == "maternal"
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    assert call["status"] == "active" and call["expects"] == "yes_no" and "automated call" in agent_lines(call)
    call = say(client, hw, call, "yes", "yes", "no")
    assert call["turns"][-1]["key"] == "headache"
    call = say(client, hw, call, "yes")
    assert call["status"] == "ended" and call["outcome"] == "danger_sign"
    assert {x["finding"] for x in call["red_flags"]} == {"headache", "visual_disturbance"}
    assert call["turns"][-1]["key"] == "end_danger" and "call you back" in call["turns"][-1]["text_en"]
    assert not any(w in agent_lines(call) for w in ADVICE)  # logistics only, never advice
    a = next(a for a in client.get(f"{API}/alerts", headers=mo).json() if a["kind"] == "call_escalation" and a["key"] == f["id"])
    assert a["to_role"] == "medical_officer" and a["assigned_to"] == "usr_hw1" and a["status"] == "open"
    assert any(x["key"] == f["id"] for x in client.get(f"{API}/alerts", headers=hw).json() if x["kind"] == "call_escalation")  # her ASHA too
    rows = client.get(f"{API}/followups", headers=hw).json()
    flagged = [x["status"] == "flagged" for x in rows]
    assert flagged == sorted(flagged, reverse=True)  # flagged ones at the top of the list
    assert next(x for x in rows if x["id"] == f["id"])["status"] == "flagged"
    # The person who calls back must say what was done
    assert client.post(f"{API}/alerts/{a['id']}/acknowledge", json={"note": ""}, headers=mo).status_code == 422
    r = client.post(f"{API}/alerts/{a['id']}/acknowledge", json={"note": "Phoned her back; coming in today"}, headers=mo)
    assert r.status_code == 200
    f = next(x for x in client.get(f"{API}/followups", headers=hw).json() if x["id"] == f["id"])
    assert f["status"] == "contacted"
    assert client.post(f"{API}/calls/{call['id']}/answer", json={"text": "yes"}, headers=hw).status_code == 409


def test_a_danger_sign_said_freely_ends_the_call(client, nurse, hw):
    f = followup(client, nurse, hw, name="Call Test Two")
    call = client.post(f"{API}/followups/{f['id']}/calls", json={"language": "hi"}, headers=hw).json()
    assert "नमस्ते" in call["turns"][0]["text"]
    call = say(client, hw, call, "हाँ", {"text": "No, I cannot come, there is bleeding", "original_text": "नहीं आ सकती, खून आ रहा है"})
    assert call["outcome"] == "danger_sign" and any(x["finding"] == "bleeding" for x in call["red_flags"])


def test_baby_not_moving_is_a_danger_sign_and_not_asked_before_24_weeks(client, nurse, hw):
    f = followup(client, nurse, hw, name="Call Test Three", weeks=30)
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    call = say(client, hw, call, "yes", "yes", "no", "no", "no")
    assert call["turns"][-1]["key"] == "movement"
    call = say(client, hw, call, "no")
    assert call["outcome"] == "danger_sign" and call["red_flags"][0]["finding"] == "reduced_fetal_movement"
    early = followup(client, nurse, hw, name="Call Test Four", weeks=14)
    call = client.post(f"{API}/followups/{early['id']}/calls", json={}, headers=hw).json()
    call = say(client, hw, call, "yes", "yes", "no", "no", "no")
    assert call["turns"][-1]["key"] == "other"  # no movement question at 14 weeks


def test_moving_less_is_never_read_as_yes(client, nurse, hw):
    f = followup(client, nurse, hw, name="Call Test Hedge", weeks=30, lang="or")
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    assert call["language"] == "or"
    call = say(client, hw, call, "ହଁ", "ହଁ", "ନା", "ନା", "ନା")
    assert call["turns"][-1]["key"] == "movement"
    call = say(client, hw, call, "କମ୍ ହଲୁଛି")  # "moving less"
    assert call["outcome"] == "unclear" and call["status"] == "ended"


def test_a_call_in_tamil_reads_plain_answers_and_never_ignores_an_unread_one(client, nurse, hw, monkeypatch):
    monkeypatch.setattr(calls, "_english", lambda said, lang: None)  # no translation model: nothing free is read
    f = followup(client, nurse, hw, name="Call Test Tamil", category="chronic", lang="ta")
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    assert call["language"] == "ta" and "வணக்கம்" in call["turns"][0]["text"] and call["turns"][0]["text_en"].startswith("Namaste")
    call = say(client, hw, call, "ஆமாம்", "ஆமாம்", "ஆமாம்", "இல்லை", "இல்லை", "இல்லை")
    assert call["turns"][-1]["key"] == "anything"
    call = say(client, hw, call, "நேற்றிலிருந்து நெஞ்சு வலிக்குது")  # chest pain since yesterday, and nothing can read it
    assert call["outcome"] == "unclear" and call["turns"][-2].get("unread")
    # With a translation, the English is read for danger signs as for any other language
    monkeypatch.setattr(calls, "_english", lambda said, lang: "Chest pain since yesterday")
    g = followup(client, nurse, hw, name="Call Test Tamil Two", category="chronic", lang="ta")
    call = client.post(f"{API}/followups/{g['id']}/calls", json={}, headers=hw).json()
    call = say(client, hw, call, "ஆமாம்", "நேற்றிலிருந்து நெஞ்சு வலிக்குது")
    assert call["outcome"] == "danger_sign" and call["red_flags"][0]["finding"] == "chest_pain"


def test_not_sure_on_a_danger_question_hands_over_to_a_person(client, nurse, hw, mo):
    f = followup(client, nurse, hw, name="Call Test Five")
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    call = say(client, hw, call, "yes", "yes", "not sure")
    assert call["outcome"] == "unclear" and call["turns"][-1]["key"] == "end_unclear"
    assert any(a["key"] == f["id"] and a["detail"]["reason"] == "unclear" for a in client.get(f"{API}/alerts", headers=mo).json() if a["kind"] == "call_escalation")
    # Gibberish gets one "please say yes or no", then the same hand-over
    g = followup(client, nurse, hw, name="Call Test Six")
    call = client.post(f"{API}/followups/{g['id']}/calls", json={}, headers=hw).json()
    call = say(client, hw, call, "yes", "yes", "blue")
    assert call["status"] == "active" and call["turns"][-1]["key"] == "reprompt"
    call = say(client, hw, call, "purple")
    assert call["outcome"] == "unclear"


def test_all_no_is_weak_evidence_and_keeps_the_follow_up_open(client, nurse, hw):
    f = followup(client, nurse, hw, name="Call Test Seven", category="chronic")
    assert f["programme"] == "chronic" and f["condition"] == "Type 2 diabetes" and f["who_calls"]["who"] == "agent"
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    assert call["audience"] == "patient"
    call = say(client, hw, call, "yes", "yes")
    assert call["turns"][-1]["key"] == "medicines" and "diabetes" in agent_lines(call)
    call = say(client, hw, call, "no", "no", "no", "no", "Nothing else")
    assert call["outcome"] == "completed" and call["red_flags"] is None
    assert call["notes"]["flags"] == ["Not taking medicines every day"] and call["notes"]["can_come"] is True
    f = next(x for x in client.get(f"{API}/followups", headers=hw).json() if x["id"] == f["id"])
    assert f["status"] == "contacted" and "weak evidence" in f["attempts"][-1]["note"] and "Not taking medicines" in f["attempts"][-1]["note"]


def test_someone_else_answers_hears_nothing_about_health(client, nurse, hw):
    f = followup(client, nurse, hw, name="Call Test Eight")
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    call = say(client, hw, call, "No, this is her mother-in-law")
    assert call["audience"] == "other" and call["turns"][-1]["key"] == "neutral_other"
    call = say(client, hw, call, "OK")
    assert call["outcome"] == "message_left"
    after_intro = " ".join(t["text_en"] for t in call["turns"][1:] if t["who"] == "agent").lower()
    assert not any(w in after_intro for w in ("pregnan", "check-up", "bleeding", "baby"))


def test_a_serious_or_unassessed_last_visit_means_a_person_calls(client, nurse, hw):
    u = followup(client, nurse, hw, name="Call Test Unassessed", exam=False)
    assert u["who_calls"]["who"] == "human" and "UNDETERMINED" in u["who_calls"]["why"]
    f = followup(client, nurse, hw, name="Call Test Nine", category="chronic", condition="Hypertension",
                 vitals={**NORMAL, "bp_systolic": 190, "bp_diastolic": 114})  # ATP RED
    assert f["who_calls"]["who"] == "human"
    r = client.post(f"{API}/followups/{f['id']}/calls", json={"operator": "agent"}, headers=hw)
    assert r.status_code == 409 and "a person calls" in r.json()["detail"]
    call = client.post(f"{API}/followups/{f['id']}/calls", json={"operator": "human"}, headers=hw).json()
    assert call["operator"] == "human" and call["turns"][0]["key"] == "intro"
    call = say(client, hw, call, "yes", "yes", "yes", {"text": "Yes, chest pain"})
    assert call["outcome"] == "danger_sign"


def test_no_answer_and_who_may_see_a_call(client, nurse, hw, doctor, employer):
    f = followup(client, nurse, hw, name="Call Test Ten")
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    call = client.post(f"{API}/calls/{call['id']}/end", json={"outcome": "no_answer"}, headers=hw).json()
    assert call["outcome"] == "no_answer" and call["status"] == "ended"
    assert client.get(f"{API}/calls/{call['id']}", headers=doctor).status_code == 200
    assert len(client.get(f"{API}/followups/{f['id']}/calls", headers=hw).json()) == 1
    assert client.get(f"{API}/calls/{call['id']}", headers=employer).status_code == 403


def test_sarvam_speaks_only_the_agents_fixed_lines(client, nurse, hw, monkeypatch):
    from app import sarvam

    f = followup(client, nurse, hw, name="Call Test Voice", lang="hi")
    call = client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).json()
    assert call["voice"] == "device"  # no key: the browser's own voice
    assert client.get(f"{API}/calls/{call['id']}/turns/0/audio", headers=hw).status_code == 503
    spoken = []
    monkeypatch.setattr(sarvam, "enabled", lambda: True)
    monkeypatch.setattr(sarvam, "speak", lambda text, lang, **kw: spoken.append((text, lang)) or b"ID3fake")
    call = say(client, hw, call, "हाँ")
    assert call["voice"] == "sarvam"
    r = client.get(f"{API}/calls/{call['id']}/turns/2/audio", headers=hw)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake"
    assert spoken[-1] == (call["turns"][2]["text"], "hi") and all(t == x["text"] for t, _ in spoken for x in call["turns"][2:3])
    assert client.get(f"{API}/calls/{call['id']}/turns/1/audio", headers=hw).status_code == 404  # the patient's turn
    assert client.get(f"{API}/calls/{call['id']}/turns/9/audio", headers=hw).status_code == 404
