"""Missing-information recall (TODO §5) on deliberately incomplete versions of the 50 synthetic cases.

Each case is first completed: vital signs filled with ordinary values for the age where the case has none, AVPU alert,
the clinician's danger-sign check recorded, an onset and a severity, gestation for maternal cases. Then one item at a
time is removed. Whether the item *matters* is decided without asking the engine what it wants: the item is filled
with a low and a high value, and it matters if the triage colour differs between the two.

* recall: of the items that matter, how many does the engine name as missing (in "missing for green" or in an
  undecided rule's needs) when they are removed;
* also reported: items named although neither value changed the colour (extra questions), and required items
  (vital signs, AVPU, the danger-sign check) named every time regardless.

Usage: python backend/scripts/eval_missing.py [out=docs/evaluation/missing_info.json]
"""

import copy
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.triage.rules import VITAL_LABEL, evaluate_full  # noqa: E402
from eval_llm import intake_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ADULT = {"pulse": 80, "resp_rate": 16, "spo2": 98, "bp_systolic": 120, "bp_diastolic": 80, "temp_f": 98.6}
CHILD = {"pulse": 100, "resp_rate": 22, "spo2": 98, "temp_f": 98.6}
VITAL_RANGE = {"pulse": (40, 150), "resp_rate": (8, 40), "spo2": (85, 99), "bp_systolic": (80, 200), "bp_diastolic": (50, 125), "temp_f": (95.0, 104.0)}


def complete(c: dict) -> dict:
    i = intake_for(c)
    i["vitals"] = {**(ADULT if c["age"] >= 12 else CHILD), **(i.get("vitals") or {}), "avpu": "A"}
    i["exam"] = {"done": True, "signs": [], "by": "Nurse"}
    i["duration"] = i.get("duration") or "3-7 days"
    i["severity"] = i.get("severity") or 3
    if c["category"] == "maternal":
        i["maternal"] = {"gestation_weeks": 28, **(i.get("maternal") or {})}
    return i


def items(i: dict) -> dict:
    """item -> (remove, set_low, set_high, words the engine uses for it)"""
    out = {}
    for k in [k for k in VITAL_RANGE if k in i["vitals"]]:
        lo, hi = VITAL_RANGE[k]
        out[k] = (lambda x, k=k: x["vitals"].pop(k), lambda x, k=k, v=lo: x["vitals"].__setitem__(k, v),
                  lambda x, k=k, v=hi: x["vitals"].__setitem__(k, v), VITAL_LABEL[k])
    out["avpu"] = (lambda x: x["vitals"].pop("avpu"), lambda x: x["vitals"].__setitem__("avpu", "A"),
                   lambda x: x["vitals"].__setitem__("avpu", "U"), "AVPU")
    out["exam"] = (lambda x: x.pop("exam"), lambda x: None, lambda x: None, "danger-sign check")
    out["onset"] = (lambda x: x.update(duration=None), lambda x: x.update(duration="In the last few hours"),
                    lambda x: x.update(duration="More than a month"), "onset")
    out["severity"] = (lambda x: x.update(severity=None), lambda x: x.update(severity=1), lambda x: x.update(severity=10), "severity")
    if i.get("maternal"):
        out["gestation"] = (lambda x: x["maternal"].pop("gestation_weeks"), lambda x: x["maternal"].__setitem__("gestation_weeks", 10),
                            lambda x: x["maternal"].__setitem__("gestation_weeks", 38), "gestational age")
    return out


def named(r: dict, word: str) -> bool:
    asked = list(r["missing_for_green"]) + [n for u in r["unresolved"] for n in u["needs"]]
    asked = ["danger-sign check" if a.startswith("danger-sign") or a == "clinician danger-sign check" else a for a in asked]
    return any(word.lower() in a.lower() for a in asked)


REQUIRED = set(VITAL_RANGE) - {"bp_diastolic"} | {"avpu", "exam"}


def main(out: str = "docs/evaluation/missing_info.json") -> None:
    data = yaml.safe_load((ROOT / "backend/tests/data/llm_eval_cases.yaml").read_text(encoding="utf-8"))
    cases = data["cases"] + data["held_out"]
    t = Counter()
    misses, extra = [], []
    for n, c in enumerate(cases, 1):
        full = complete(c)
        for key, (remove, low, high, word) in items(full).items():
            a, b, gone = copy.deepcopy(full), copy.deepcopy(full), copy.deepcopy(full)
            low(a)
            high(b)
            remove(gone)
            ua, ub = evaluate_full(a, c["age"], c["sex"])["urgency"], evaluate_full(b, c["age"], c["sex"])["urgency"]
            r = evaluate_full(gone, c["age"], c["sex"])
            matters = ua != ub
            said = named(r, word)
            required = key in REQUIRED and not (key == "bp_systolic" and c["age"] < 12)
            t["removals"] += 1
            if matters:
                t["matter"] += 1
                t["matter_named"] += said
                if not said:
                    misses.append({"case": n, "chief": c["chief"], "item": key, "low": ua, "high": ub, "with_it_missing": r["urgency"]})
            else:
                t["not_matter"] += 1
                if said and not required:
                    t["extra_named"] += 1
                    extra.append({"case": n, "item": key})
            if required:
                t["required"] += 1
                t["required_named"] += said
            # Safety: with something that matters missing, the case must not come out GREEN.
            if matters and r["urgency"] == "green":
                t["green_while_missing"] += 1
    res = {
        "cases": len(cases), **t,
        "recall_pct": round(100 * t["matter_named"] / t["matter"], 1) if t["matter"] else None,
        "required_named_pct": round(100 * t["required_named"] / t["required"], 1),
        "misses": misses, "extra_examples": extra[:20],
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("extra_examples",)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
