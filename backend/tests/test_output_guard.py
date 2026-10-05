"""C4: the non-diagnostic output guard blocks every red-team output and lets faithful note sentences through."""

from pathlib import Path

import pytest
import yaml

from app.output_guard import check

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
