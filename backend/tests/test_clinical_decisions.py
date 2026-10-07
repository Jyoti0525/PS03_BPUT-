"""The two clinical decisions closed on 7 Oct: severe hypertension (local rule) and IITT meningism (kept as published)."""
import pytest

from app.triage.rules import evaluate_full
from test_wednesday import NORMAL, said


def _with_bp(text, s, d):
    return {**said(text), "vitals": {**NORMAL, "bp_systolic": s, "bp_diastolic": d}}


def test_bp_166_102_with_headache_is_yellow_for_a_doctor():
    r = evaluate_full(_with_bp("headache", 166, 102), 50, "M")
    assert r["urgency"] == "yellow"
    hit = next(h for h in r["hits"] if h["rule_id"] == "LOCAL-SEVERE-HTN")
    assert hit["review_by"] == "doctor"


@pytest.mark.parametrize("s,d", [(184, 96), (150, 112)])
def test_bp_at_or_above_180_or_110_is_yellow_without_symptoms(s, d):
    assert evaluate_full(_with_bp("routine check", s, d), 50, "F")["urgency"] in ("yellow", "red")


def test_moderately_raised_bp_without_symptoms_is_not_raised_by_the_local_rule():
    r = evaluate_full(_with_bp("routine check", 164, 98), 50, "F")
    assert not any(h["rule_id"] == "LOCAL-SEVERE-HTN" for h in r["hits"])


def test_meningism_kept_as_in_the_who_tool():
    # IITT age >= 12 Red: any two of altered mental status, stiff neck, fever or hypothermia, headache.
    r = evaluate_full(said("fever and headache"), 25, "M")
    assert r["urgency"] == "red" and any(h["rule_id"] == "IITT-A-MENINGISM" for h in r["hits"])
