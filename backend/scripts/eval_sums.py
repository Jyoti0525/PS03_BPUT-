"""B2 arithmetic checks, measured without OCR: how often does one misread digit break a sum the report must satisfy?

Synthetic reports from make_ocr_set.report_b2 (a seed never used for an image set). For every printed value that takes
part in at least one relation (WBC differential = 100 %, absolute = % × WBC, globulin = total protein − albumin,
MCHC = Hb ÷ PCV, VLDL = TG ÷ 5, …), each kind of OCR slip is applied in turn, one value at a time:
* a digit read as a look-alike (1↔7, 3↔8, 5↔6, 6↔8, 0↔8, 4↔9, 2↔7, 1↔4), at the first, a middle or the last digit;
* a digit dropped; the decimal point lost.
Results are also split by how far the slip moved the value: a slip in the last digit of "12,300" moves it by under
1 %, inside the rounding every sum must allow, and cannot be caught by arithmetic.
A slip counts as caught by the sums if a relation that held before now fails, and as caught by the per-test bounds if
the new value is outside what the body can have (the check that existed before B2). The correct reports themselves
must fail no relation (false alarms).

Usage: python backend/scripts/eval_sums.py [n_reports=2000] [seed=4242] [out=docs/evaluation/b2_sums_simulation.json]
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.triage.extraction import TEST, consistency  # noqa: E402
from make_ocr_set import report_b2  # noqa: E402

LOOKALIKE = {"1": "74", "7": "12", "3": "8", "8": "3609", "5": "6", "6": "58", "0": "8", "4": "91", "9": "4", "2": "7"}


def slips(value: str, rng: random.Random) -> list[tuple[str, str]]:
    """(kind, slipped text) for one printed value; at most one of each kind."""
    digits = [i for i, ch in enumerate(value) if ch.isdigit()]
    out = []
    for where, pos in (("first digit", digits[0]), ("middle digit", digits[len(digits) // 2] if len(digits) > 2 else None), ("last digit", digits[-1])):
        if pos is None:
            continue
        ch = value[pos]
        out.append((f"look-alike, {where}", value[:pos] + rng.choice(LOOKALIKE[ch]) + value[pos + 1:]))
    if len(digits) > 1:
        pos = rng.choice(digits)
        out.append(("digit dropped", value[:pos] + value[pos + 1:]))
    if "." in value:
        out.append(("decimal point lost", value.replace(".", "", 1)))
    return out


def _rows(truth_rows: list[dict]) -> list[dict]:
    return [{"test_key": r["test_key"], "value": r["value"], "value_num": r["value_num"], "printed_name": r["printed"], "checks": [], "needs_check": False}
            for r in truth_rows if r["value_num"] is not None]


def main(n: int, seed: int, out: Path) -> dict:
    rng, slip_rng = random.Random(seed), random.Random(seed + 1)  # the reports do not depend on the slips drawn
    relations = false_alarms = 0
    tried = defaultdict(int)
    by_sums = defaultdict(int)
    by_bounds = defaultdict(int)
    by_either = defaultdict(int)
    per_test = defaultdict(lambda: [0, 0])
    by_size = defaultdict(lambda: [0, 0, 0])  # how far the slip moved the value: slips, caught by bounds, caught by either
    for i in range(n):
        rep = report_b2(rng, i)
        truth = [r for _, s in rep["sections"] for r in s]
        base = consistency(_rows(truth))
        relations += len(base["checked"])
        false_alarms += len(base["failed"])
        involved = _involved(truth)
        for j, r in enumerate(truth):
            if r["value_num"] is None or r["test_key"] not in involved:
                continue
            for kind, text in slips(r["value"], slip_rng):
                try:
                    raw = float(text.replace(",", ""))
                except ValueError:
                    continue
                old_raw = float(r["value"].replace(",", ""))
                if raw == old_raw:
                    continue
                new_num = r["value_num"] / old_raw * raw if old_raw else raw  # same scaling as printed (lakhs, 10³, SI)
                rows = _rows(truth)
                k = next(x for x in rows if x["test_key"] == r["test_key"])
                k["value"], k["value_num"] = text, new_num
                t = TEST[r["test_key"]]
                bounds = not (t.plausible[0] <= new_num <= t.plausible[1])
                sums = bool(consistency(rows)["failed"])
                tried[kind] += 1
                by_sums[kind] += sums
                by_bounds[kind] += bounds
                by_either[kind] += sums or bounds
                per_test[t.name][0] += 1
                per_test[t.name][1] += sums or bounds
                change = abs(new_num - r["value_num"]) / abs(r["value_num"]) if r["value_num"] else 1.0
                size = "moved >= 10 %" if change >= 0.1 else "moved 5-10 %" if change >= 0.05 else "moved < 5 %"
                by_size[size][0] += 1
                by_size[size][1] += bounds
                by_size[size][2] += sums or bounds

    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    total = sum(tried.values())
    result = {
        "reports": n, "seed": seed, "relations_checked": relations, "false_alarms_on_correct_reports": false_alarms,
        "slips": total,
        "caught_by_bounds_alone_pct": pct(sum(by_bounds.values()), total),
        "caught_by_sums_pct": pct(sum(by_sums.values()), total),
        "caught_by_either_pct": pct(sum(by_either.values()), total),
        "by_kind": {k: {"slips": tried[k], "bounds_pct": pct(by_bounds[k], tried[k]), "sums_pct": pct(by_sums[k], tried[k]),
                        "either_pct": pct(by_either[k], tried[k])} for k in sorted(tried)},
        "by_size": {k: {"slips": a, "bounds_pct": pct(b, a), "either_pct": pct(c, a)} for k, (a, b, c) in sorted(by_size.items())},
        "by_test": {k: {"slips": a, "caught_pct": pct(b, a)} for k, (a, b) in sorted(per_test.items())},
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "by_test"}, ensure_ascii=False, indent=1))
    return result


def _involved(truth: list[dict]) -> set[str]:
    """Tests that take part in a relation on this report: those whose slip could break a sum."""
    rows = _rows(truth)
    keys = set()
    for r in rows:  # a value is involved if a large change to it breaks some relation
        trial = _rows(truth)
        x = next(y for y in trial if y["test_key"] == r["test_key"])
        x["value_num"] = x["value_num"] * 1.25 + 1
        x["value"] = str(x["value_num"])
        if consistency(trial)["failed"]:
            keys.add(r["test_key"])
    return keys


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2000, int(sys.argv[2]) if len(sys.argv) > 2 else 4242,
         Path(sys.argv[3]) if len(sys.argv) > 3 else Path("docs/evaluation/b2_sums_simulation.json"))
