"""B4: every onset carries a certainty label and the patient's own words."""

import pytest

from app.triage.timeline import onset


@pytest.mark.parametrize(
    "chief, tapped, certainty, when, raw",
    [
        ("Fever for 4 days with headache", None, "STATED", "4 days ago", "4 days"),
        ("ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର ହେଉଛି", None, "STATED", "4 days ago", "ଚାରି ଦିନ"),
        ("मुझे तीन दिन से बुखार है", None, "STATED", "3 days ago", "तीन दिन"),
        ("bukhar teen din se", None, "STATED", "3 days ago", "teen din"),
        ("ଜ୍ୱର ୩ ଦିନ ହେଲା", None, "STATED", "3 days ago", "3 ଦିନ"),
        ("Loose stools 6 times since yesterday", None, "STATED", "1 day ago", "since yesterday"),
        ("Pain since this morning", None, "STATED", "Today", "since this morning"),
        ("Fever", "3-7 days", "STATED", "3-7 days ago", "tapped: 3-7 days"),
        ("Cough since Diwali", None, "VAGUE", "Not clear", "since Diwali"),
        ("कई दिन से खांसी", None, "VAGUE", "Not clear", "कई दिन"),
        ("ଅନେକ ଦିନ ହେଲା କାଶ", None, "VAGUE", "Not clear", "ଅନେକ ଦିନ"),
        ("Chest pain", None, "UNKNOWN", "Not stated", None),
        # numbers that are not an onset
        ("Vomiting 3 times a day", None, "UNKNOWN", "Not stated", None),
        ("32 weeks pregnant, headache", None, "UNKNOWN", "Not stated", None),
        ("2 years old child with fever for 2 days", None, "STATED", "2 days ago", "2 days"),
    ],
)
def test_onset(chief, tapped, certainty, when, raw):
    o = onset({"chief_complaint": chief, "duration": tapped})
    assert (o["certainty"], o["when"], o["raw"]) == (certainty, when, raw)


def test_said_and_tapped_disagree_asks_again():
    o = onset({"chief_complaint": "Fever for 3 days", "duration": "1-4 weeks"})
    assert o["certainty"] == "STATED" and "ask again" in o["check"]


def test_vague_onset_is_listed_as_missing_and_labelled_on_the_note(client, nurse):
    from conftest import API, DEVICE
    from test_api import new_intake

    _, body = new_intake(client, nurse, chief_complaint="Cough since Diwali")
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    t = next(x for x in enc["note"]["timeline"] if x["event"].startswith("Onset"))
    assert t["certainty"] == "VAGUE" and t["raw"] == "since Diwali"
    assert any("approximate date" in m for m in enc["note"]["missing_info"])


@pytest.mark.parametrize(
    "chief, window",
    [
        ("ଦୁଇ ଦିନ ହେଲା ଛାତି ଯନ୍ତ୍ରଣା", (36, 60)),
        ("Chest pain since this morning", (0, 24)),
        ("Chest pain for 3 hours", (2.25, 3.75)),
        ("Chest pain since Diwali", None),  # vague: never used, staff are asked
    ],
)
def test_rules_use_a_stated_onset_when_nothing_was_tapped(chief, window):
    from app.triage.rules import onset_hours

    w = onset_hours({"chief_complaint": chief})
    assert (w and tuple(round(x, 2) for x in w)) == window


def test_stated_onset_resolves_the_acute_chest_pain_rule():
    from app.triage.rules import evaluate_full

    today = evaluate_full({"category": "normal", "chief_complaint": "Chest pain since this morning"}, 50, "M")
    assert any(h["rule_id"].startswith("ATP") and "24 h" in h["description"] for h in today["hits"])
    older = evaluate_full({"category": "normal", "chief_complaint": "Chest pain for 2 days"}, 50, "M")
    assert not any("onset" in n for u in older["unresolved"] for n in u["needs"])
