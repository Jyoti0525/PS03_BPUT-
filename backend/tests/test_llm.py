"""B5 + C4: the model's summary is used only when it is faithful to the record and passes the output guard."""

from types import SimpleNamespace

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app import llm

PATIENT = SimpleNamespace(age=40, sex="M")


@pytest.fixture
def case(client, nurse):
    _, body = new_intake(client, nurse, chief_complaint="Fever for 3 days, no chest pain", vitals={"bp_systolic": 150, "bp_diastolic": 90, "temp_f": 101.2})
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    return enc["note"], enc["intake"]


def run(monkeypatch, case, text):
    monkeypatch.setattr(llm, "_complete", lambda facts: text)
    return llm.apply(*case, PATIENT)


def test_faithful_summary_is_used(monkeypatch, case):
    note = run(monkeypatch, case, "A 40-year-old man has had fever for 3 days and denies chest pain. Blood pressure is 150/90 mmHg and temperature 101.2 °F.")
    assert note["renderer"] == "LLM" and note["llm"]["status"] == "PASS"
    assert note["summary"].startswith("A 40-year-old man") and "not a diagnosis" in note["summary"]
    assert note["summary_template"] == case[0]["summary"]  # the template is kept beside it


@pytest.mark.parametrize(
    "text, reason",
    [
        ("A 40-year-old man has had fever for 5 days.", "numbers not in the record: 5"),
        ("A 40-year-old man has had fever for three weeks.", "numbers not in the record: 3"),  # "three" is fine…
        ("A 40-year-old man has fever for 3 days; this is likely dengue.", 'Names a disease or condition: "dengue"'),
        ("A 40-year-old man with fever for 3 days should take paracetamol.", "paracetamol"),
        ("A 40-year-old man has fever for 3 days and chest pain.", "states chest pain, which the record does not"),
        ("A 40-year-old man has fever for 3 days. Weight 70 kg.", "numbers not in the record: 70"),
    ],
)
def test_unfaithful_or_diagnostic_summary_falls_back(monkeypatch, case, text, reason):
    note = run(monkeypatch, case, text)
    if reason.endswith(": 3"):  # "three weeks" — the number is in the record but the unit is not
        assert note["llm"]["status"] == "FAIL_FELL_BACK" and any("week" in p for p in note["llm"]["faithfulness"])
        return
    assert note["renderer"] == "TEMPLATE" and note["llm"]["status"] == "FAIL_FELL_BACK"
    assert note["summary"] == case[0]["summary"]
    assert any(reason in r for r in note["llm"]["faithfulness"] + note["llm"]["guard"]), note["llm"]
    assert note["llm"]["rejected_text"] == text
    assert any(f["code"] == "LLM-FELL-BACK" for f in note["flags"])


def test_no_server_keeps_the_template(monkeypatch, case):
    def down(facts):
        raise llm.LlmUnavailable("not reachable")

    monkeypatch.setattr(llm, "_complete", down)
    note = llm.apply(*case, PATIENT)
    assert note["renderer"] == "TEMPLATE" and note["llm"]["status"] == "UNAVAILABLE" and note["summary"] == case[0]["summary"]


def test_no_ai_consent_never_calls_the_model(monkeypatch, case):
    def called(facts):
        raise AssertionError("model must not run")

    monkeypatch.setattr(llm, "_complete", called)
    note, intake = case
    assert llm.apply(note, {**intake, "ai_assist": False}, PATIENT) is note


def test_fact_sheet_holds_only_recorded_facts(case):
    facts = llm.fact_sheet(*case, PATIENT)
    assert "Fever for 3 days, no chest pain" in facts and "150/90" in facts
    assert "Test Person" not in facts  # no name: the model never sees identity


# ---------------------------------------------------------------- C8: second opinion on urgency


def opinion(monkeypatch, case, answer, summary="A 40-year-old man has had fever for 3 days and denies chest pain."):
    monkeypatch.setattr(llm, "_complete", lambda facts: summary)
    monkeypatch.setattr(llm, "_opinion_text", lambda facts: answer)
    return llm.apply(*case, PATIENT)


def test_opinion_never_changes_urgency_and_a_higher_one_flags_a_second_look(monkeypatch, case):
    rules = case[0]["triage"]["urgency"]
    assert rules != "red"
    note = opinion(monkeypatch, case, "URGENCY: RED\nREASON: Blood pressure 150/90 mmHg with fever for 3 days.")
    op = note["llm_opinion"]
    assert op["status"] == "DISAGREE" and op["direction"] == "higher" and op["model_urgency"] == "red"
    assert op["rules_urgency"] == rules and note["triage"]["urgency"] == rules  # the rules' tier is untouched
    assert op["reason"].startswith("Blood pressure 150/90")
    flag = next(f for f in note["flags"] if f["code"] == "AI-OPINION-HIGHER")
    assert flag["severity"] == "warning" and "only a doctor can change it" in flag["reason"]


def test_lower_or_equal_opinion_is_shown_but_adds_no_flag(monkeypatch, case):
    rules = case[0]["triage"]["urgency"]
    lower = "GREEN" if rules != "green" else None
    if lower:
        note = opinion(monkeypatch, case, f"URGENCY: {lower}\nREASON: Fever for 3 days.")
        assert note["llm_opinion"]["direction"] == "lower"
        assert not any(f["code"] == "AI-OPINION-HIGHER" for f in note["flags"])
    note = opinion(monkeypatch, case, f"**URGENCY:** {rules.upper()}\n**REASON:** Fever for 3 days.")
    assert note["llm_opinion"]["status"] == "AGREE" and note["llm_opinion"]["direction"] is None


@pytest.mark.parametrize(
    "answer, withheld",
    [
        ("URGENCY: RED\nREASON: Fever for 3 days suggests dengue.", "dengue"),
        ("URGENCY: RED\nREASON: Give paracetamol for the fever.", "paracetamol"),
        ("URGENCY: RED\nREASON: Fever for 9 days.", "numbers not in the record: 9"),
    ],
)
def test_opinion_reason_that_fails_the_checks_is_withheld(monkeypatch, case, answer, withheld):
    note = opinion(monkeypatch, case, answer)
    op = note["llm_opinion"]
    assert op["model_urgency"] == "red" and "reason" not in op
    assert any(withheld in w for w in op["reason_withheld"])
    flag = next(f for f in note["flags"] if f["code"] == "AI-OPINION-HIGHER")
    assert "dengue" not in flag["reason"] and "paracetamol" not in flag["reason"]


def test_unreadable_or_unavailable_opinion_is_never_guessed(monkeypatch, case):
    note = opinion(monkeypatch, case, "This patient is somewhere between red and green.")
    assert note["llm_opinion"]["status"] == "UNREADABLE" and "model_urgency" not in note["llm_opinion"]

    def down(facts):
        raise llm.LlmUnavailable("not reachable")

    monkeypatch.setattr(llm, "_complete", down)
    monkeypatch.setattr(llm, "_opinion_text", lambda facts: pytest.fail("no second call when the server is down"))
    note = llm.apply(*case, PATIENT)
    assert note["llm_opinion"]["status"] == "UNAVAILABLE"


def test_no_ai_consent_gets_no_opinion(monkeypatch, case):
    monkeypatch.setattr(llm, "_opinion_text", lambda facts: pytest.fail("model must not run"))
    note, intake = case
    assert "llm_opinion" not in llm.apply(note, {**intake, "ai_assist": False}, PATIENT)


def test_opinion_switch_off(monkeypatch, case):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_urgency_opinion", False)
    note = opinion(monkeypatch, case, "URGENCY: RED\nREASON: x")
    assert "llm_opinion" not in note and not any(f["code"] == "AI-OPINION-HIGHER" for f in note["flags"])


def test_disagreement_view_lists_cases_for_supervisor_and_doctor_only(client, nurse, doctor, supervisor, monkeypatch):
    from app.db import SessionLocal
    from app.models import Encounter

    _, body = new_intake(client, nurse, chief_complaint="Fever for 3 days, no chest pain", vitals={"bp_systolic": 150, "bp_diastolic": 90, "temp_f": 101.2})
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    monkeypatch.setattr(llm, "_complete", lambda facts: "A 40-year-old man has had fever for 3 days.")
    monkeypatch.setattr(llm, "_opinion_text", lambda facts: "URGENCY: RED\nREASON: Fever for 3 days.")
    with SessionLocal() as db:
        e = db.get(Encounter, enc["id"])
        e.note = llm.apply(e.note, e.intake, e.patient)
        db.commit()
        rules = e.urgency

    r = client.get(f"{API}/ai-opinions", headers=supervisor)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["counts"]["DISAGREE"] >= 1 and v["higher"] >= 1
    row = next(c for c in v["cases"] if c["encounter_id"] == enc["id"])
    assert row["model_urgency"] == "red" and row["rules_urgency"] == rules and row["final_urgency"] == rules
    assert v["matrix"][rules]["red"] >= 1
    assert client.get(f"{API}/ai-opinions", headers=doctor).status_code == 200
    assert client.get(f"{API}/ai-opinions", headers=nurse).status_code == 403
