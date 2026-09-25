"""Deterministic triage rules engine.

Loads YAML rule sets (ATP adult, maternal, IMCI paediatric) and evaluates intake data against
them. The final urgency is the maximum urgency across every rule that fires. No model is
involved; the same input always yields the same output, and every fired rule is returned so
the reviewer can see exactly why.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).parent / "rules"
RANK = {"green": 0, "yellow": 1, "red": 2}


@dataclass(frozen=True)
class Rule:
    id: str
    protocol: str
    description: str
    urgency: str
    when: dict


@dataclass
class Ctx:
    text: str
    age: int
    category: str
    vitals: dict
    severity: int | None
    duration: str | None


@lru_cache
def load_rules() -> tuple[Rule, ...]:
    out: list[Rule] = []
    for f in sorted(RULES_DIR.glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        for r in doc["rules"]:
            if r["urgency"] not in RANK:
                raise ValueError(f"{r['id']}: bad urgency {r['urgency']}")
            out.append(Rule(r["id"], doc["protocol"], r["description"], r["urgency"], r["when"]))
    ids = [r.id for r in out]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule ids")
    return tuple(out)


def _vital(c: Ctx, field: str) -> float | None:
    v = c.vitals.get(field)
    return float(v) if v is not None else None


def _cond(c: Ctx, cond: dict[str, Any]) -> bool:
    ok = True
    for key, arg in cond.items():
        if key == "all":
            ok = all(_cond(c, x) for x in arg)
        elif key == "any":
            ok = any(_cond(c, x) for x in arg)
        elif key == "text_any":
            ok = any(w.lower() in c.text for w in arg)
        elif key == "age_gte":
            ok = c.age >= arg
        elif key == "age_lt":
            ok = c.age < arg
        elif key == "category":
            ok = c.category == arg
        elif key == "severity_gte":
            ok = (c.severity or 0) >= arg
        elif key == "duration_long":
            ok = bool(c.duration and re.search(r"(3|4|5|6|7).*day|week|month", c.duration)) == bool(arg)
        elif key in ("vital_lt", "vital_gte", "vital_between"):
            v = _vital(c, arg["field"])
            if v is None:
                ok = False
            elif key == "vital_lt":
                ok = v < arg["value"]
            elif key == "vital_gte":
                ok = v >= arg["value"]
            else:
                ok = arg["min"] <= v <= arg["max"]
        else:
            raise ValueError(f"Unknown rule condition: {key}")
        if not ok:
            return False
    return ok


def intake_text(intake: dict) -> str:
    parts = [intake.get("chief_complaint", "")]
    parts += [s.get("text", "") for s in intake.get("symptoms", [])]
    parts += intake.get("selected_symptoms", [])
    parts += [a.get("answer", "") for a in intake.get("answers", [])]
    return " ".join(parts).lower()


def evaluate(intake: dict, age: int) -> tuple[str, list[dict]]:
    ctx = Ctx(
        text=intake_text(intake),
        age=age,
        category=intake.get("category", "normal"),
        vitals={k: v for k, v in (intake.get("vitals") or {}).items() if v is not None},
        severity=intake.get("severity"),
        duration=intake.get("duration"),
    )
    hits = [
        {"rule_id": r.id, "protocol": r.protocol, "description": r.description, "urgency": r.urgency}
        for r in load_rules()
        if _cond(ctx, r.when)
    ]
    if not hits:
        hits.append(
            {
                "rule_id": "ATP-ROUT-00",
                "protocol": "IMCI" if age < 5 else "ATP",
                "description": "No red or yellow criteria met — routine queue",
                "urgency": "green",
            }
        )
    urgency = max((h["urgency"] for h in hits), key=RANK.__getitem__)
    return urgency, hits
