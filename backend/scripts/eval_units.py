"""Unit errors (TODO §5 validation catch rate), measured without OCR on the synthetic B2 reports (eval_sums.py covers
digit swaps and decimal shifts).

Every printed row with a unit is broken one way at a time and the report is parsed again (parse_labs + consistency):
* wrong unit: the unit read as another test's unit (g/dL for mg/dL, U/L for %, ...);
* unit lost: nothing read in the unit column;
* SI value, conventional unit: the lab printed mmol/L (value and range) but the unit was read as mg/dL;
* conventional value, SI unit: the reverse.
A break is *caught* if the row is now marked for checking (needs_check) and was not before. It is *silent* if the
value the rules see moved by more than 5 % and the row is not marked. A row whose unit was lost but whose value is
unchanged (the unit assumed is the right one) is *harmless*: a note says the unit was assumed.

Usage: python backend/scripts/eval_units.py [n_reports=500] [seed=5151] [out=docs/evaluation/unit_errors.json]
"""

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.triage import extraction as E  # noqa: E402
from make_ocr_set import report_b2  # noqa: E402

UNITS = ["mg/dL", "g/dL", "mmol/L", "U/L", "%", "fL", "pg", "µIU/mL", "µmol/L", "mg/L", "10^3/µL", "mill/cumm"]
SI = {k: (kind, f) for k, d in E.CONVERT.items() for kind, f in d.items() if k != "hba1c"}
SI_NAME = {"mmol/l": "mmol/L", "umol/l": "µmol/L", "g/l": "g/L"}


def table(rows: list[dict]) -> E.OcrResult:
    lines = []
    for i, r in enumerate(rows):
        y = 300 + 40 * i
        lines += [E.Line(r["printed"], [60, y, 300, 24], 0.97), E.Line(r["value"], [520, y, 90, 24], 0.97)]
        if r["unit"]:
            lines.append(E.Line(r["unit"], [700, y, 90, 24], 0.97))
        if r["ref"]:
            lines.append(E.Line(r["ref"], [900, y, 160, 24], 0.97))
    return E.OcrResult("test", lines, (1200, 1700))


def parse(rows: list[dict]) -> list[dict]:
    parsed = E.parse_labs(table(rows))
    E.consistency(parsed)
    return parsed


def fmt(v: float) -> str:
    return f"{v:.1f}" if v < 100 else f"{v:.0f}"


def si_ref(ref: str, f) -> str:
    """A printed range in the SI unit: each number divided back by the conversion."""
    nums = re.findall(r"\d+(?:\.\d+)?", ref)
    return " - ".join(fmt(float(x) / f(1.0)) for x in nums) if nums else ref


def breaks(row: dict, rng: random.Random) -> list[tuple[str, dict]]:
    out = []
    kind = E._unit_kind(row["unit"])
    others = [u for u in UNITS if E._unit_kind(u) != kind]
    out.append(("wrong unit", {**row, "unit": rng.choice(others)}))
    out.append(("unit lost", {**row, "unit": ""}))
    if row["test_key"] in SI and kind not in SI_NAME:
        si_kind, f = SI[row["test_key"]]
        k = f(1.0)
        out.append(("SI value, conventional unit", {**row, "value": fmt(row["value_num"] / k), "ref": si_ref(row["ref"], f)}))
    if row["test_key"] in SI and kind in SI_NAME:
        out.append(("conventional value, SI unit", {**row, "value": fmt(row["value_num"]), "ref": ""}))
    return out


def main(n: int = 500, seed: int = 5151, out: str = "docs/evaluation/unit_errors.json") -> None:
    rng = random.Random(seed)
    tally: dict[str, Counter] = defaultdict(Counter)
    false_alarm = Counter()
    for i in range(n):
        rows = [r for _, sec in report_b2(rng, i)["sections"] for r in sec]
        clean = {r["test_key"]: r for r in parse(rows)}
        false_alarm["rows"] += len(clean)
        false_alarm["marked"] += sum(r["needs_check"] for r in clean.values())
        for j, row in enumerate(rows):
            if not row["unit"] or row["value_num"] is None or row["test_key"] not in clean or clean[row["test_key"]]["needs_check"]:
                continue
            truth = clean[row["test_key"]]["value_num"]
            for name, broken in breaks(row, rng):
                got = {r["test_key"]: r for r in parse(rows[:j] + [broken] + rows[j + 1:])}.get(row["test_key"])
                t = tally[name]
                t["n"] += 1
                moved = got is None or got["value_num"] is None or abs(got["value_num"] - truth) > 0.05 * max(abs(truth), 1e-9)
                if got is None:
                    t["row dropped"] += 1
                elif got["needs_check"]:
                    t["caught"] += 1
                elif moved:
                    t["silent"] += 1
                else:
                    t["harmless"] += 1
    res = {
        "reports": n, "seed": seed,
        "clean_rows": false_alarm["rows"], "clean_rows_marked": false_alarm["marked"],
        "by_break": {k: {**v, "caught_pct": round(100 * v["caught"] / v["n"], 1), "silent_pct": round(100 * v["silent"] / v["n"], 1)} for k, v in tally.items()},
    }
    allc = sum(tally.values(), Counter())
    res["all"] = {**allc, "caught_pct": round(100 * allc["caught"] / allc["n"], 1), "silent_pct": round(100 * allc["silent"] / allc["n"], 1)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]) if a else 500, int(a[1]) if len(a) > 1 else 5151, a[2] if len(a) > 2 else "docs/evaluation/unit_errors.json")
