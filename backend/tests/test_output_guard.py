"""C4: the non-diagnostic output guard blocks every red-team output and lets faithful note sentences through."""

from pathlib import Path

import pytest
import yaml

from conftest import API

from app.output_guard import TEST_SAMPLES, check

DATA = yaml.safe_load((Path(__file__).parent / "data" / "redteam_outputs.yaml").read_text(encoding="utf-8"))


def test_red_team_set_is_at_least_100():
    assert len(DATA["block"]) >= 100


@pytest.mark.parametrize("case", DATA["block"], ids=lambda c: c["text"][:40])
def test_blocks(case):
    v = check(case["text"], case.get("source", ""))
    assert not v.ok, f"not blocked: {case['text']}"


@pytest.mark.parametrize("case", DATA["allow"], ids=lambda c: c["text"][:40])
def test_allows(case):
    v = check(case["text"], case.get("source", ""))
    assert v.ok, v.reasons()


def test_guard_test_samples_are_from_the_red_team_set_and_behave_as_labelled():
    listed = {(c["text"], c.get("source", "")) for c in DATA["block"] + DATA["allow"]}
    for s in TEST_SAMPLES:
        assert (s["text"], s.get("source", "")) in listed, s["text"]
        assert check(s["text"], s.get("source", "")).ok == (s["expect"] == "allow"), s["text"]


def test_supervisor_guard_test_blocks_logs_as_a_test_and_scrubs_identifiers(client, supervisor, doctor):
    r = client.post(f"{API}/guard-test", json={"text": "Ramesh, call 98765 43210 — likely dengue, give paracetamol 500 mg."}, headers=supervisor).json()
    assert r["test"] is True and r["ok"] is False
    assert {h["category"] for h in r["hits"]} == {"condition", "drug_advice"}
    log = client.get(f"{API}/audit", params={"action": "GUARD_BLOCK"}, headers=supervisor).json()
    entry = next(a for a in log if a["resource_type"] == "guard_test")
    assert "not a model output" in entry["detail"] and "98765" not in entry["detail"] and entry["patient_code"] is None
    ok = client.post(f"{API}/guard-test", json={"text": "Fever for four days and headache."}, headers=supervisor).json()
    assert ok["ok"] is True and ok["hits"] == []
    assert client.post(f"{API}/guard-test", json={"text": "likely dengue"}, headers=doctor).status_code == 403
    assert len(client.get(f"{API}/guard-test/samples", headers=supervisor).json()["samples"]) == len(TEST_SAMPLES)
