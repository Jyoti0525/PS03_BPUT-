"""Deterministic triage rules engine (three-valued).

Rule sets are YAML files in `rules/`, one per protocol, each rule carrying its published source.
Every condition evaluates to True, False or None (unknown — e.g. a vital that was never
measured). The engine never treats unknown as normal:

* RED or YELLOW is assigned only by rules that are definitely true.
* A case can be GREEN only when no rule fired, no rule was left undecided by missing data, the
  core vital signs for the patient's age were measured and a clinician recorded the danger-sign
  check. Otherwise it is held at a *provisional* YELLOW that lists exactly what is missing.

Protocols are routed by age and pregnancy and all applicable sets run together; the highest
urgency wins. No model is involved; the same input always gives the same output, and each fired
rule carries the evidence that triggered it, its source document and whether it may be lowered.
"""

import hashlib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .findings import FINDINGS, Finding, extract, resolve

RULES_DIR = Path(__file__).parent / "rules"
RANK = {"green": 0, "yellow": 1, "red": 2}
ROLES = ("health_worker", "nurse", "doctor")


@dataclass(frozen=True)
class Rule:
    id: str
    protocol: str
    description: str
    urgency: str
    when: dict
    source: str
    non_downgradable: bool
    review_by: str


@dataclass(frozen=True)
class Protocol:
    key: str
    name: str
    applies: dict
    rules: tuple[Rule, ...]


@lru_cache
def load_pack() -> tuple[dict, tuple[Protocol, ...], str]:
    """(sources, protocols, version). Validates every rule at load so a typo fails at start-up."""
    sources = yaml.safe_load((RULES_DIR / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    protocols, digest, seen = [], hashlib.sha256(), set()
    for f in sorted(RULES_DIR.glob("*.yaml")):
        raw = f.read_text(encoding="utf-8")
        digest.update(raw.encode())
        if f.name == "sources.yaml":
            continue
        doc = yaml.safe_load(raw)
        rules = []
        for r in doc["rules"]:
            if r["urgency"] not in RANK or r["urgency"] == "green":
                raise ValueError(f"{r['id']}: rules raise urgency only (red/yellow), got {r['urgency']}")
            src = r.get("source", doc.get("source"))
            if src not in sources:
                raise ValueError(f"{r['id']}: unknown source {src!r}")
            review = r.get("review_by", "doctor" if r["urgency"] == "red" else "nurse")
            if review not in ROLES:
                raise ValueError(f"{r['id']}: bad review_by {review}")
            if r["id"] in seen:
                raise ValueError(f"Duplicate rule id {r['id']}")
            seen.add(r["id"])
            _check(r["id"], r["when"])
            rules.append(Rule(r["id"], doc["protocol"], r["description"], r["urgency"], r["when"], src,
                              bool(r.get("non_downgradable", r["urgency"] == "red")), review))
        protocols.append(Protocol(doc["protocol"], doc["name"], doc.get("applies", {}), tuple(rules)))
    return sources, tuple(protocols), digest.hexdigest()[:10]


def load_rules() -> tuple[Rule, ...]:
    return tuple(r for p in load_pack()[1] for r in p.rules)


# ---------------------------------------------------------------- context and three-valued leaves

VITALS = ("bp_systolic", "bp_diastolic", "pulse", "spo2", "temp_f", "resp_rate", "glucose")
DERIVED = ("temp_c", "shock_index")
OPS = {"lt": lambda a, b: a < b, "lte": lambda a, b: a <= b, "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b, "eq": lambda a, b: a == b}
VITAL_LABEL = {"bp_systolic": "systolic BP", "bp_diastolic": "diastolic BP", "pulse": "pulse", "spo2": "SpO₂", "temp_f": "temperature", "temp_c": "temperature",
               "resp_rate": "respiratory rate", "glucose": "blood glucose", "shock_index": "shock index (pulse ÷ systolic BP)", "avpu": "AVPU level of consciousness"}
UNIT = {"bp_systolic": "mmHg", "bp_diastolic": "mmHg", "pulse": "/min", "spo2": "%", "temp_c": "°C", "temp_f": "°F", "resp_rate": "/min", "glucose": "mg/dL", "shock_index": ""}

# Onset windows (hours) for the kiosk's duration options; ranges are deliberately wide so that
# "1–2 days" cannot rule out a 20-hour onset.
DURATION_HOURS = [
    (r"last few hours|^within (the )?last \d+ hours?", (0, 12)),
    (r"^today|since (this )?morning|few hours|^aaj", (0, 24)),
    (r"yesterday|^1\s*-\s*2 days?", (12, 48)),
    (r"^3\s*-\s*7 days?", (72, 168)),
    (r"^1\s*-\s*4 weeks?|more than a week", (168, 720)),
    (r"more than a month|months?|years?", (720, 10**6)),
]


@dataclass
class Ctx:
    findings: dict[str, Finding]
    vitals: dict[str, float]
    avpu: str | None
    age: int
    age_days: tuple[float, float]
    sex: str | None
    severity: int | None
    onset_h: tuple[float, float] | None
    gestation: int | None
    labs: dict[str, float]
    unknown: set[str] = field(default_factory=set)
    evidence: list[str] = field(default_factory=list)


def onset_hours(intake: dict) -> tuple[float, float] | None:
    # The follow-up answer is more specific than the tile ("In the last few hours" after "today").
    texts = [a.get("answer", "") for a in intake.get("answers", []) if a.get("qid") == "dur"] + [intake.get("duration") or ""]
    for t in texts:
        t = re.sub(r"[–—]", "-", t.strip().lower())
        if not t:
            continue
        for pat, rng in DURATION_HOURS:  # the kiosk's own options first
            if re.search(pat, t):
                return rng
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?)\s*)?(hour|hr|h\b|day|week|month)", t)
        if m:
            lo, hi, unit = float(m.group(1)), float(m.group(2) or m.group(1)), m.group(3)
            per = {"hour": 1, "hr": 1, "h": 1, "day": 24, "week": 168, "month": 720}[unit]
            return (max(0, (lo - 0.5) * per), (hi + 0.5) * per) if per > 1 else (lo, hi)
    # Nothing tapped: use an onset the patient stated in their own words ("ଦୁଇ ଦିନ ହେଲା", "since this morning"), with a
    # wide window. A vague one ("since Diwali") is never used, so its rules stay unresolved and staff are asked.
    from .timeline import onset

    o = onset(intake)
    if o["certainty"] == "STATED" and o["days"] is not None:
        h = o["days"] * 24
        if h < 1e-9:
            return (0, 24)  # "today", "this morning"
        margin = h * 0.25 if h < 24 else max(12, h * 0.25)
        return (max(0, h - margin), h + margin)
    return None


def _age_days(intake: dict, age: int) -> tuple[float, float]:
    if intake.get("age_days") is not None:
        d = float(intake["age_days"])
        return d, d
    if intake.get("age_months") is not None:
        m = float(intake["age_months"])
        return m * 30.4, (m + 1) * 30.4 - 1
    return age * 365.25, (age + 1) * 365.25 - 1


def _compare(lo: float, hi: float, op: str, value: float) -> bool | None:
    """Range comparison: True if every value in [lo, hi] satisfies it, False if none does."""
    a, b = OPS[op](lo, value), OPS[op](hi, value)
    return a if a == b else None


def _vital(c: Ctx, name: str) -> float | None:
    if name == "temp_c":
        f = c.vitals.get("temp_f")
        return round((f - 32) * 5 / 9, 2) if f is not None else None
    if name == "shock_index":
        p, s = c.vitals.get("pulse"), c.vitals.get("bp_systolic")
        return round(p / s, 2) if p is not None and s else None
    return c.vitals.get(name)


def _and(vals: list[bool | None]) -> bool | None:
    return False if any(v is False for v in vals) else True if all(v is True for v in vals) else None


def _or(vals: list[bool | None]) -> bool | None:
    return True if any(v is True for v in vals) else False if all(v is False for v in vals) else None


def _check(rid: str, cond: Any) -> None:
    if not isinstance(cond, dict) or len(cond) != 1:
        raise ValueError(f"{rid}: each condition must have exactly one key, got {cond!r}")
    (key, arg), = cond.items()
    if key in ("all", "any"):
        for x in arg:
            _check(rid, x)
    elif key == "not":
        _check(rid, arg)
    elif key == "at_least":
        for x in arg["of"]:
            _check(rid, x)
    elif key == "finding":
        if arg not in FINDINGS:
            raise ValueError(f"{rid}: unknown finding {arg}")
    elif key in ("vital", "vital_if_measured"):
        name, op, _ = arg
        if name not in VITALS + DERIVED or op not in OPS:
            raise ValueError(f"{rid}: bad vital condition {arg}")
    elif key in ("age_years", "age_days", "severity", "onset_hours", "gestation_weeks"):
        if arg[0] not in OPS:
            raise ValueError(f"{rid}: bad operator in {key}")
    elif key == "lab":
        if arg[1] not in OPS:
            raise ValueError(f"{rid}: bad operator in lab")
    elif key not in ("avpu_in", "sex"):
        raise ValueError(f"{rid}: unknown condition {key}")


def _eval(c: Ctx, cond: dict) -> bool | None:
    (key, arg), = cond.items()
    if key == "all":
        return _and([_eval(c, x) for x in arg])
    if key == "any":
        return _or([_eval(c, x) for x in arg])
    if key == "not":
        v = _eval(c, arg)
        return None if v is None else not v
    if key == "at_least":
        vals = [_eval(c, x) for x in arg["of"]]
        yes, maybe = vals.count(True), vals.count(None)
        return True if yes >= arg["n"] else False if yes + maybe < arg["n"] else None
    if key == "finding":
        f = resolve(c.findings, arg)
        if f.value is None:
            c.unknown.add(f"danger-sign check: {FINDINGS[arg][0].lower()}")
        elif f.value:
            c.evidence.append(f"{FINDINGS[arg][0]} — {f.evidence[0]}")
        return f.value
    if key in ("vital", "vital_if_measured"):
        # `vital_if_measured` is for tests that are not part of routine triage (glucose): a missing
        # value means "not tested", not "unknown", so it cannot hold a case at provisional.
        name, op, value = arg
        v = _vital(c, name)
        if v is None:
            if key == "vital_if_measured":
                return False
            c.unknown.add(VITAL_LABEL[name])
            return None
        ok = OPS[op](v, value)
        if ok:
            lab = VITAL_LABEL[name]
            c.evidence.append(f"{lab[0].upper()}{lab[1:]} {v:g}{(' ' + UNIT[name]) if UNIT[name] else ''}")
        return ok
    if key == "avpu_in":
        if c.avpu is None:
            c.unknown.add(VITAL_LABEL["avpu"])
            return None
        ok = c.avpu in arg
        if ok:
            c.evidence.append(f"AVPU: {c.avpu}")
        return ok
    if key == "age_years":
        return OPS[arg[0]](c.age, arg[1])
    if key == "age_days":
        v = _compare(*c.age_days, arg[0], arg[1])
        if v is None:
            c.unknown.add("exact age in days or months (infant)")
        return v
    if key == "sex":
        return None if c.sex is None else c.sex == arg
    if key == "severity":
        if c.severity is None:
            c.unknown.add("pain / symptom severity")
            return None
        ok = OPS[arg[0]](c.severity, arg[1])
        if ok:
            c.evidence.append(f"Self-rated severity {c.severity}/10")
        return ok
    if key == "onset_hours":
        if c.onset_h is None:
            c.unknown.add("time of onset")
            return None
        v = _compare(*c.onset_h, arg[0], arg[1])
        if v is None:
            c.unknown.add(f"exact time of onset (within {arg[1]} h?)")
        elif v:
            c.evidence.append(f"Onset within {arg[1]} h")
        return v
    if key == "gestation_weeks":
        if c.gestation is None:
            c.unknown.add("gestational age")
            return None
        return OPS[arg[0]](c.gestation, arg[1])
    if key == "lab":
        # Lab rules act only on values read from an uploaded report; absence is not "unknown".
        name, op, value = arg
        v = c.labs.get(name)
        if v is None:
            return False
        ok = OPS[op](v, value)
        if ok:
            c.evidence.append(f"Report: {name} {v:g}")
        return ok
    raise ValueError(f"Unknown rule condition: {key}")


def _applies(p: Protocol, c: Ctx) -> bool:
    a = p.applies
    if "age_min" in a and c.age < a["age_min"]:
        return False
    if "age_max_exclusive" in a and c.age >= a["age_max_exclusive"]:
        return False
    if a.get("pregnant") and resolve(c.findings, "pregnant").value is not True:
        return False
    return True


# ---------------------------------------------------------------- public API

REQUIRED_ADULT = ("pulse", "resp_rate", "spo2", "bp_systolic", "temp_f")
REQUIRED_CHILD = ("pulse", "resp_rate", "spo2", "temp_f")


def evaluate_full(intake: dict, age: int, sex: str | None = None) -> dict:
    sources, protocols, version = load_pack()
    vit = {k: float(v) for k, v in (intake.get("vitals") or {}).items() if v is not None and k in VITALS}
    avpu = ((intake.get("vitals") or {}).get("avpu") or "").upper()[:1] or None
    category = intake.get("category", "normal")
    c = Ctx(
        findings=extract(intake, category),
        vitals=vit,
        avpu=avpu if avpu in ("A", "V", "P", "U") else None,
        age=age,
        age_days=_age_days(intake, age),
        sex=sex,
        severity=intake.get("severity"),
        onset_h=onset_hours(intake),
        gestation=(intake.get("maternal") or {}).get("gestation_weeks"),
        labs={k.lower(): float(v) for k, v in (intake.get("lab_values") or {}).items() if v is not None},
    )

    applied, hits, unresolved = [], [], []
    for p in protocols:
        if not _applies(p, c):
            continue
        applied.append({"key": p.key, "name": p.name})
        for r in p.rules:
            c.unknown, c.evidence = set(), []
            v = _eval(c, r.when)
            base = {"rule_id": r.id, "protocol": r.protocol, "description": r.description, "urgency": r.urgency,
                    "source": sources[r.source]["short"], "source_key": r.source, "non_downgradable": r.non_downgradable, "review_by": r.review_by}
            if v is True:
                hits.append({**base, "evidence": list(dict.fromkeys(c.evidence))})
            elif v is None:
                unresolved.append({**base, "needs": sorted(c.unknown)})

    required = REQUIRED_ADULT if age >= 12 else REQUIRED_CHILD
    missing = [VITAL_LABEL[k] for k in required if k not in vit]
    if c.avpu is None:
        missing.append(VITAL_LABEL["avpu"])
    if not (intake.get("exam") or {}).get("done"):
        missing.append("clinician danger-sign check")

    top = max((h["urgency"] for h in hits), key=RANK.__getitem__, default="green")
    provisional = top != "red" and bool(missing or unresolved)
    could_be_red = sorted({u["rule_id"] for u in unresolved if u["urgency"] == "red"})
    if provisional and top == "green":
        top = "yellow"
    if provisional:
        needs = sorted({"clinician danger-sign check" if n.startswith("danger-sign") else n for u in unresolved for n in u["needs"]} | set(missing))
        hits.append({
            "rule_id": "SAFE-PROVISIONAL", "protocol": "SAFETY", "urgency": "yellow",
            "description": "Provisional — cannot be routine until measured: " + ", ".join(needs),
            "source": sources["safety"]["short"], "source_key": "safety", "non_downgradable": True, "review_by": "nurse",
            "evidence": [f"{len(could_be_red)} RED rule(s) could not be ruled out: {', '.join(could_be_red)}"] if could_be_red else [],
        })
    elif not hits:
        hits.append({
            "rule_id": "TRIAGE-GREEN", "protocol": "SAFETY", "urgency": "green",
            "description": "No red or yellow criteria; vital signs measured and within limits; danger-sign check recorded",
            "source": sources["safety"]["short"], "source_key": "safety", "non_downgradable": False, "review_by": "nurse", "evidence": [],
        })

    return {
        "urgency": top,
        "provisional": provisional,
        "hits": hits,
        "unresolved": unresolved,
        "missing_for_green": missing,
        "protocols": applied,
        "findings": {k: {"label": FINDINGS[k][0], "value": f.value, "evidence": f.evidence} for k, f in c.findings.items()},
        "rulepack_version": version,
    }


def evaluate(intake: dict, age: int, sex: str | None = None) -> tuple[str, list[dict]]:
    r = evaluate_full(intake, age, sex)
    return r["urgency"], r["hits"]
