"""The kiosk question flow is one versioned file (question_flow.yaml) read by both the kiosk and the rules engine."""

import json

from app.triage import findings, question_flow


def test_flow_is_valid():
    assert question_flow.problems(set(findings.FINDINGS)) == []


def test_frontend_json_matches_yaml():
    built = json.loads(question_flow.JSON_PATH.read_text(encoding="utf-8"))
    assert built == question_flow.load(), "run: python backend/scripts/build_question_flow.py"


def test_unknown_finding_fails(monkeypatch):
    flow = json.loads(json.dumps(question_flow.load()))
    flow["questions"][1]["options"][0]["sets"]["not_a_finding"] = True
    flow["questions"][2]["when"]["shoe_size"] = 9
    monkeypatch.setattr(question_flow, "load", lambda: flow)
    bad = question_flow.problems(set(findings.FINDINGS))
    assert any("unknown finding not_a_finding" in b for b in bad) and any("unknown test shoe_size" in b for b in bad)


def test_answers_reach_the_rules():
    got = findings.extract({"answers": [{"qid": "mechanism", "answer": "Fall from a height (tree, roof, ladder)"}]})
    assert got["fall_from_height"].value is True
    got = findings.extract({"answers": [{"qid": "chest_radiation", "answer": "Yes"}]})  # short form still read
    assert got["chest_pain_radiating"].value is True
