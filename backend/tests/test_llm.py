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
