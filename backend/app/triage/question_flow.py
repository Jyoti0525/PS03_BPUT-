"""Kiosk context questions from question_flow.yaml, shared with the frontend (frontend/src/lib/question_flow.json)."""

from functools import lru_cache
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("question_flow.yaml")
JSON_PATH = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "question_flow.json"


@lru_cache(maxsize=1)
def load() -> dict:
    with open(PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def answers_table() -> list[tuple[str, str, dict[str, bool]]]:
    """(qid, answer prefix, findings set) for every option that sets a finding."""
    return [(q["qid"], o["match"], dict(o["sets"])) for q in load()["questions"] for o in q["options"] if o.get("sets")]


def problems(known_findings: set[str]) -> list[str]:
    """Everything that breaks the file's contract; an empty list means it is valid."""
    flow, out, seen = load(), [], set()
    tests = set(flow.get("tests") or {})
    out += [f"test {t} reads unknown field {v.get('field')}" for t, v in (flow.get("tests") or {}).items() if v.get("field") not in (flow.get("fields") or {})]

    def check_when(qid: str, cond: dict) -> None:
        for k, v in cond.items():
            if k == "any":
                for c in v:
                    check_when(qid, c)
            elif k not in tests:
                out.append(f"{qid}: unknown test {k}")

    for q in flow["questions"]:
        qid = q.get("qid")
        if qid in seen:
            out.append(f"{qid}: duplicate qid")
        seen.add(qid)
        check_when(qid, q.get("when") or {})
        for o in q.get("options") or []:
            if o.get("match") and not o["label"].startswith(o["match"]):
                out.append(f"{qid}: match {o['match']!r} does not start label {o['label']!r}")
            if o.get("sets") and not o.get("match"):
                out.append(f"{qid}: option {o['label']!r} sets findings but has no match")
            out += [f"{qid}: unknown finding {f}" for f in (o.get("sets") or {}) if f not in known_findings]
            out += [f"{qid}: {f} must be true or false" for f, v in (o.get("sets") or {}).items() if not isinstance(v, bool)]
    return out
