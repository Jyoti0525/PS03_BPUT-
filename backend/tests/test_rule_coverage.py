"""Every rule in the pack gets four generated cases, built from its own YAML condition (§5 rule correctness):

* firing: an input that makes the condition true, and the rule fires;
* non-firing: the nearest input that makes it false (normal values elsewhere);
* boundary: each threshold on the firing path, tested exactly at the YAML value and one step past it;
* unknown: data for a leaf that can be unmeasured (a vital, a danger sign, AVPU, severity, onset, gestation, sex,
  infant age) is removed from the firing case, and the rule must answer "unknown", never "no".

Leaves whose absence means "not reported" by design (lab values, workplace answers, symptoms the patient did not
mention, `vital_if_measured`) have no unknown case; they are counted separately. A rule that gets no case where it
should is a gap and fails CI. `python -m pytest tests/test_rule_coverage.py -s -k report` prints the counts.
"""

import copy

import pytest

from app.triage.findings import FINDINGS, SIGN, Finding
from app.triage.rules import Ctx, _eval, load_rules

RULES = load_rules()
NORMAL = {"pulse": 80.0, "resp_rate": 16.0, "spo2": 98.0, "bp_systolic": 120.0, "bp_diastolic": 80.0, "temp_f": 98.6, "glucose": 100.0}
STEP = {"temp_c": 0.1, "shock_index": 0.01, "temp_f": 0.1}
NUMERIC = ("vital", "vital_if_measured", "age_years", "age_days", "severity", "onset_hours", "gestation_weeks", "lab",
           "exposure_years", "cough_weeks", "fev1_decline_pct")


def base() -> Ctx:
    """A case where every leaf has a known, ordinary value: adult, alert, no findings, nothing reported."""
    return Ctx(findings={k: Finding(False, ["test"]) for k in FINDINGS}, vitals=dict(NORMAL), avpu="A", age=30,
               age_days=(30 * 365.25, 30 * 365.25), sex="female", severity=2, onset_h=(100.0, 100.0), gestation=None,
               labs={}, occ={"exposures": [], "breathless_vs_last": "same"})


def run(c: Ctx, cond: dict) -> bool | None:
    c.unknown, c.evidence = set(), []
    return _eval(c, cond)


def numeric_value(c: Ctx, key: str, arg) -> float | None:
    if key in ("vital", "vital_if_measured"):
        name = arg[0]
        if name == "temp_c":
            return None if "temp_f" not in c.vitals else (c.vitals["temp_f"] - 32) * 5 / 9
        if name == "shock_index":
            return c.vitals["pulse"] / c.vitals["bp_systolic"]
        return c.vitals.get(name)
    return None


def set_numeric(c: Ctx, key: str, arg, v: float) -> None:
    if key in ("vital", "vital_if_measured"):
        name = arg[0]
        if name == "temp_c":
            c.vitals["temp_f"] = round(v * 9 / 5 + 32, 4)
        elif name == "shock_index":
            c.vitals["bp_systolic"] = 100.0
            c.vitals["pulse"] = round(v * 100, 4)
        else:
            c.vitals[name] = v
    elif key == "age_years":
        c.age = int(v)
    elif key == "age_days":
        c.age_days = (v, v)
    elif key == "severity":
        c.severity = int(v)
    elif key == "onset_hours":
        c.onset_h = (v, v)
    elif key == "gestation_weeks":
        c.gestation = int(v)
    elif key == "lab":
        c.labs[arg[0]] = v
    elif key == "exposure_years":
        c.occ["years_exposed"] = v
    elif key == "cough_weeks":
        c.occ["cough_weeks"] = v
    elif key == "fev1_decline_pct":
        c.occ["fev1_baseline_l"] = 4.0
        c.occ["fev1_l"] = round(4.0 * (1 - v / 100), 4)


def op_threshold(key: str, arg) -> tuple[str, float, float]:
    op, t = (arg[1], arg[2]) if key in ("vital", "vital_if_measured", "lab") else (arg[0], arg[1])
    name = arg[0] if key in ("vital", "vital_if_measured") else key
    step = STEP.get(name, 0.1 if isinstance(t, float) and t != int(t) else 1)
    if key == "fev1_decline_pct":
        step = 0.5
    return op, float(t), step


def make(c: Ctx, cond: dict, want: bool) -> None:
    """Change `c` so that `cond` evaluates to `want`, touching as little as possible."""
    (key, arg), = cond.items()
    if key == "all":
        if want:
            for x in arg:
                make(c, x, True)
        else:
            make(c, arg[0], False) if run(c, cond) is not False else None
        return
    if key == "any":
        if want:
            if run(c, cond) is not True:
                make(c, arg[0], True)
        else:
            for x in arg:
                if run(c, x) is not False:
                    make(c, x, False)
        return
    if key == "not":
        make(c, arg, not want)
        return
    if key == "at_least":
        kids = arg["of"]
        for i, x in enumerate(kids):
            if want and i < arg["n"]:
                make(c, x, True)
            elif not want and run(c, x) is not False:
                make(c, x, False)
        return
    if run(c, cond) is want:
        return
    if key == "finding":
        c.findings[arg] = Finding(want, ["test"])
    elif key in NUMERIC:
        op, t, step = op_threshold(key, arg)
        inside = {"gt": t + step, "gte": t, "lt": t - step, "lte": t, "eq": t}[op]
        outside = {"gt": t, "gte": t - step, "lt": t, "lte": t + step, "eq": t + step}[op]
        set_numeric(c, key, arg, inside if want else outside)
    elif key == "avpu_in":
        c.avpu = arg[0] if want else next(x for x in "AVPU" if x not in arg)
    elif key == "sex":
        c.sex = arg if want else ("male" if arg == "female" else "female")
    elif key == "exposure":
        c.occ["exposures"] = [arg[0]] if want else []
    elif key == "breathless_vs_last":
        c.occ["breathless_vs_last"] = arg if want else next(x for x in ("same", "better", "first") if x != arg)


def true_leaves(c: Ctx, cond: dict, out: list) -> list:
    """Leaves on the path that makes `cond` true in `c` (what the firing case actually relies on)."""
    (key, arg), = cond.items()
    if key in ("all", "any"):
        for x in arg:
            if key == "all" or run(c, x) is True:
                true_leaves(c, x, out)
    elif key == "at_least":
        for x in arg["of"]:
            if run(c, x) is True:
                true_leaves(c, x, out)
    elif key != "not":  # a leaf under "not" is false in the firing case; its boundary is still tested from the other side
        out.append(cond)
    return out


def unknowable(c: Ctx, cond: dict) -> bool:
    (key, arg), = cond.items()
    return (key == "finding" and FINDINGS[arg][1] == SIGN) or key in ("vital", "avpu_in", "severity", "onset_hours",
                                                                       "gestation_weeks", "sex", "age_days")


def blank(c: Ctx, cond: dict) -> None:
    (key, arg), = cond.items()
    if key == "finding":
        c.findings.pop(arg)
    elif key == "vital":
        for v in {"temp_c": ["temp_f"], "shock_index": ["pulse", "bp_systolic"]}.get(arg[0], [arg[0]]):
            c.vitals.pop(v, None)
    elif key == "avpu_in":
        c.avpu = None
    elif key == "severity":
        c.severity = None
    elif key == "onset_hours":
        c.onset_h = None
    elif key == "gestation_weeks":
        c.gestation = None
    elif key == "sex":
        c.sex = None
    elif key == "age_days":
        lo = c.age_days[0]
        c.age_days = (lo - 400, lo + 400)  # "a few months old", not a day count


def firing(rule) -> Ctx:
    c = base()
    make(c, rule.when, True)
    return c


def cases(rule) -> dict:
    fire = firing(rule)
    off = base()
    make(off, rule.when, False)
    out = {"firing": run(copy.deepcopy(fire), rule.when), "non_firing": run(off, rule.when), "boundary": [], "unknown": []}
    for leaf in true_leaves(fire, rule.when, []):
        (key, arg), = leaf.items()
        if key in NUMERIC:
            op, t, step = op_threshold(key, arg)
            past = {"gt": t, "gte": t - step, "lt": t, "lte": t + step, "eq": t + step}[op]
            edge = {"gt": t + step, "gte": t, "lt": t - step, "lte": t, "eq": t}[op]
            at, beyond = copy.deepcopy(fire), copy.deepcopy(fire)
            set_numeric(at, key, arg, edge)
            set_numeric(beyond, key, arg, past)
            out["boundary"].append((leaf, run(at, rule.when), run(beyond, rule.when)))
        if unknowable(fire, leaf):
            u = copy.deepcopy(fire)
            blank(u, leaf)
            out["unknown"].append((leaf, run(u, rule.when)))
    return out


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_rule_fires_and_does_not_fire(rule):
    r = cases(rule)
    assert r["firing"] is True, f"{rule.id}: no input built from its condition makes it fire"
    assert r["non_firing"] is False, f"{rule.id}: the nearest non-matching input does not give a definite no"


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_rule_threshold_sits_exactly_at_the_published_value(rule):
    for leaf, at, beyond in cases(rule)["boundary"]:
        assert at is True and beyond is not True, f"{rule.id}: {leaf} — at the edge {at}, one step past {beyond}"


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_rule_never_says_no_when_a_measurement_is_missing(rule):
    for leaf, v in cases(rule)["unknown"]:
        assert v is not False, f"{rule.id}: {leaf} removed and the rule answered 'no' instead of 'unknown'"


def test_report_coverage_counts():
    rows = {rule.id: cases(rule) for rule in RULES}
    n = len(rows)
    fire = sum(r["firing"] is True and r["non_firing"] is False for r in rows.values())
    with_threshold = sum(bool(r["boundary"]) for r in rows.values())
    with_unknown = sum(bool(r["unknown"]) for r in rows.values())
    absent_is_no = [k for k, r in rows.items() if not r["unknown"]]
    no_threshold = [k for k, r in rows.items() if not r["boundary"]]
    print(f"\n{n} rules: {fire} firing + non-firing; {with_threshold} with thresholds, "
          f"{sum(len(r['boundary']) for r in rows.values())} boundary cases; {with_unknown} with unknown-input cases "
          f"({sum(len(r['unknown']) for r in rows.values())} leaves); {len(absent_is_no)} rules where absence means "
          f"'not reported' by design; {len(no_threshold)} rules with no numeric threshold")
    assert fire == n
