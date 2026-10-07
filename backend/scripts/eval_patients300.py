"""Triage on the 300-patient set, split by language, sex and age band (§9 fairness).

The rules engine reads each patient's own words (English, Hindi or Odia, through the offline lexicon; no translation
model) with the recorded vital signs. Two measures:

* agreement with the colour the team set for the vignette, and under-triage (engine colour lower than expected),
  per language, sex and age band;
* consistency: the six patients of a vignette differ only in language, sex and age, so the engine should give them
  one colour. Every vignette where it does not is listed with the reason (the rules that differ).

The incomplete copies must never come out GREEN.

Usage: python backend/scripts/eval_patients300.py [out=docs/evaluation/patients300.json]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.triage.rules import evaluate_full  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RANK = {"green": 0, "yellow": 1, "red": 2}
BANDS = [("under 5", 0, 4), ("5–11", 5, 11), ("12–17", 12, 17), ("18–39", 18, 39), ("40–59", 40, 59), ("60+", 60, 200)]
SEX = {"M": "male", "F": "female"}


def band(age: int) -> str:
    return next(b for b, lo, hi in BANDS if lo <= age <= hi)


def run(p: dict) -> dict:
    i = {"symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [], **p["intake"]}
    return evaluate_full(i, p["age"], SEX[p["sex"]])


def table(rows: list[dict], key) -> dict:
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return {k: {"n": len(v), "agree_pct": round(100 * sum(r["got"] == r["expect"] for r in v) / len(v), 1),
                "under_triage": sum(RANK[r["got"]] < RANK[r["expect"]] for r in v),
                "over_triage": sum(RANK[r["got"]] > RANK[r["expect"]] for r in v)} for k, v in sorted(g.items())}


def main(out: str = "docs/evaluation/patients300.json") -> None:
    data = yaml.safe_load((ROOT / "backend/tests/data/patients300.yaml").read_text(encoding="utf-8"))
    rows = []
    for p in data["patients"]:
        r = run(p)
        rows.append({"id": p["id"], "vignette": p["vignette"], "expect": p["expect"], "got": r["urgency"], "language": p["language"],
                     "sex": p["sex"], "age": p["age"], "band": band(p["age"]), "rules": sorted(h["rule_id"] for h in r["hits"])})
    by_v = defaultdict(list)
    for r in rows:
        by_v[r["vignette"]].append(r)
    inconsistent = []
    for v, rs in by_v.items():
        if len({r["got"] for r in rs}) > 1:
            inconsistent.append({"vignette": v, "expect": rs[0]["expect"],
                                 "patients": [{k: r[k] for k in ("id", "language", "sex", "age", "got", "rules")} for r in rs]})
    gaps = [run(p)["urgency"] for p in data["incomplete"]]
    n = len(rows)
    res = {
        "patients": n, "vignettes": len(by_v),
        "agree_pct": round(100 * sum(r["got"] == r["expect"] for r in rows) / n, 1),
        "under_triage": sum(RANK[r["got"]] < RANK[r["expect"]] for r in rows),
        "over_triage": sum(RANK[r["got"]] > RANK[r["expect"]] for r in rows),
        "by_expected": table(rows, lambda r: r["expect"]),
        "by_language": table(rows, lambda r: r["language"]),
        "by_sex": table(rows, lambda r: r["sex"]),
        "by_age_band": table(rows, lambda r: r["band"]),
        "vignettes_consistent": len(by_v) - len(inconsistent),
        "incomplete": {"n": len(gaps), "green": gaps.count("green"), "colours": {c: gaps.count(c) for c in RANK}},
        "disagreements": [r for r in rows if r["got"] != r["expect"]],
        "inconsistent": inconsistent,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("disagreements", "inconsistent")}, ensure_ascii=False, indent=1))
    for x in inconsistent:
        print(x["vignette"], x["expect"], [(p["language"], p["sex"], p["age"], p["got"]) for p in x["patients"]])


if __name__ == "__main__":
    main(*sys.argv[1:])
