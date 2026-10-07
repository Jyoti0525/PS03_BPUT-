"""OCR field accuracy on the synthetic lab reports (make_ocr_set.py), per capture type.

For every test printed on a report: was it found, is the value exactly right (as a number, after the parser's own
scaling: "2.10 lakhs" = 210000), the unit, the reference range and the high/low call. The safety figure is the
silent error: a wrong value that the reviewer is *not* told to check. Also: rows invented (a test not on the report),
report date and patient name read, how often the quality gate asked for a retake, and seconds per page.

Also, with the second engine on: correct values flagged anyway (the cost of the check) and how often the two
engines differ on a wrong value (caught) and on a right one (a needless question).

Usage: python backend/scripts/eval_ocr.py [set_dir=models/eval/ocr_synth] [out=docs/evaluation/ocr_synth_rapidocr.json] [types|all] [second]
"""

import difflib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.triage.extraction import _ref, _squash, extract_document  # noqa: E402

TYPES = ("scan", "photo", "poor_photo", "photocopy", "thermal")
CTYPE = {".png": "image/png", ".jpg": "image/jpeg"}


def _unit(u: str) -> str:
    return re.sub(r"\s", "", (u or "").lower().replace("µ", "u").replace("gm/", "g/"))


def _close(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) <= 1e-6 * max(1.0, abs(b))


def score_report(ex: dict, truth: dict) -> dict:
    got = {}
    for r in ex["rows"]:
        got.setdefault(r["test_key"], r)
    rows = []
    for t in truth["rows"]:
        g = got.get(t["test_key"])
        rec = {"test": t["test_key"], "truth": t["value"], "read": g and g.get("value"), "found": bool(g and g.get("value") is not None)}
        if t["value_num"] is None:  # qualitative / dipstick
            rec["value_ok"] = rec["found"] and str(g["value"]).lower().replace(" ", "") == t["value"].lower().replace(" ", "")
            rec["unit_ok"] = rec["ref_ok"] = None
        else:
            rec["value_ok"] = rec["found"] and _close(g.get("value_num"), t["value_num"])
            rec["unit_ok"] = rec["found"] and _unit(g.get("unit")) == _unit(t["unit"])
            want = _ref(t["ref"])
            have = _ref(g["reference"]) if rec["found"] and g.get("reference") and "typical" not in g["reference"] else None
            rec["ref_ok"] = bool(want and have and want[0] == have[0] and want[1] == have[1])
        rec["status_ok"] = rec["found"] and ((g["status"] != "normal") == t["out"])
        rec["flagged"] = bool(g and g.get("needs_check"))
        rec["flagged_without_sums"] = bool(g and g.get("flagged_without_sums", g.get("needs_check")))
        rec["mark"], rec["mark_read"] = t.get("flag") or None, (g or {}).get("flag")
        rec["second"] = g and g.get("second_engine")  # agrees / differs / only / None (not compared)
        rec["silent_error"] = rec["found"] and not rec["value_ok"] and not rec["flagged"]
        rows.append(rec)
    ok = {r["test"]: r["value_ok"] for r in rows}
    failed = (ex.get("consistency") or {}).get("failed", [])
    for r in rows:
        r["in_failed_sum"] = any(r["test"] in f["keys"] for f in failed)
    sums = {"checked": len((ex.get("consistency") or {}).get("checked", [])), "failed": len(failed),
            "false_alarms": sum(1 for f in failed if all(ok.get(k, False) for k in f["keys"]))}
    keys = {t["test_key"] for t in truth["rows"]}
    invented = [r["test_key"] for r in ex["rows"] if r["test_key"] not in keys]
    name = ex["meta"].get("patient_name")
    return {"rows": rows, "invented": invented, "date_ok": ex["meta"].get("date") == truth["date"],
            "name_ok": bool(name) and difflib.SequenceMatcher(None, _squash(name), _squash(truth["patient_name"]).removeprefix("mrs").removeprefix("mr").removeprefix("ms")).ratio() >= 0.85
            or bool(name) and difflib.SequenceMatcher(None, _squash(name), _squash(truth["patient_name"])).ratio() >= 0.85,
            "retake": not ex["quality"].get("ok", True), "engine": ex["engine"], "sums": sums}


def summarise(reports: list[dict]) -> dict:
    rows = [r for rep in reports for r in rep["rows"]]
    num = [r for r in rows if r["unit_ok"] is not None]
    found = [r for r in rows if r["found"]]
    wrong = [r for r in found if not r["value_ok"]]

    def pct(xs, n):
        return round(100 * len(xs) / n, 1) if n else None

    return {
        "reports": len(reports), "tests": len(rows),
        "found_pct": pct(found, len(rows)),
        "value_exact_pct": pct([r for r in rows if r["value_ok"]], len(rows)),
        "unit_pct": pct([r for r in num if r["unit_ok"]], len(num)),
        "range_pct": pct([r for r in num if r["ref_ok"]], len(num)),
        "high_low_pct": pct([r for r in rows if r["status_ok"]], len(rows)),
        "wrong_values": len(wrong),
        "wrong_flagged_pct": pct([r for r in wrong if r["flagged"]], len(wrong)),
        "silent_errors": len([r for r in rows if r["silent_error"]]),
        "correct_flagged_pct": pct([r for r in rows if r["value_ok"] and r["flagged"]], len([r for r in rows if r["value_ok"]])),
        "engines_differ_on_wrong": len([r for r in wrong if r.get("second") == "differs"]),
        "engines_differ_on_correct": len([r for r in rows if r["value_ok"] and r.get("second") == "differs"]),
        "silent_error_pct": pct([r for r in rows if r["silent_error"]], len(rows)),
        # B2: what the report's own sums and the lab's H/L marks add
        "correct_flagged_without_sums_pct": pct([r for r in rows if r["value_ok"] and r["flagged_without_sums"]], len([r for r in rows if r["value_ok"]])),
        "silent_errors_without_sums": len([r for r in wrong if not r["flagged_without_sums"]]),
        "wrong_in_failed_sum": len([r for r in wrong if r["in_failed_sum"]]),
        "sum_relations_checked": sum(rep["sums"]["checked"] for rep in reports),
        "sum_relations_failed": sum(rep["sums"]["failed"] for rep in reports),
        "sum_false_alarms": sum(rep["sums"]["false_alarms"] for rep in reports),
        "marks_printed": len([r for r in rows if r["mark"]]),
        "marks_read_pct": pct([r for r in rows if r["mark"] and r["mark_read"] == r["mark"]], len([r for r in rows if r["mark"]])),
        "marks_misread": len([r for r in rows if r["mark_read"] and r["mark_read"] != r["mark"]]),
        "invented_rows": sum(len(rep["invented"]) for rep in reports),
        "date_pct": pct([1 for rep in reports if rep["date_ok"]], len(reports)),
        "name_pct": pct([1 for rep in reports if rep["name_ok"]], len(reports)),
        "retake_asked_pct": pct([1 for rep in reports if rep["retake"]], len(reports)),
        "seconds_per_page": round(sum(rep["seconds"] for rep in reports) / len(reports), 2) if reports else None,
    }


def main(set_dir: Path, out: Path, types=TYPES, second: bool = False) -> dict:
    truth = json.loads((set_dir / "truth.json").read_text(encoding="utf-8"))
    by_type, detail = {}, {}
    for t in types:
        reps = []
        for f in sorted((set_dir / t).iterdir()):
            rid = f.stem
            start = time.perf_counter()
            ex = extract_document(f.read_bytes(), CTYPE[f.suffix], patient_name=truth[rid]["patient_name"], second=second)
            rep = score_report(ex, truth[rid])
            rep["seconds"] = time.perf_counter() - start
            rep["id"] = rid
            reps.append(rep)
            print(f"{t:10s} {rid} values {sum(r['value_ok'] for r in rep['rows'])}/{len(rep['rows'])} {rep['seconds']:.1f}s", flush=True)
        by_type[t] = summarise(reps)
        detail[t] = [{"id": r["id"], "errors": [x for x in r["rows"] if not x["value_ok"] or x["unit_ok"] is False or x["ref_ok"] is False], "invented": r["invented"], "sums": r["sums"],
                      "date_ok": r["date_ok"], "name_ok": r["name_ok"], "retake": r["retake"]} for r in reps]
    result = {"engine": rep["engine"], "second_engine": second, "by_type": by_type, "detail": detail}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(by_type, indent=1))
    return result


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "models/eval/ocr_synth"),
         Path(sys.argv[2] if len(sys.argv) > 2 else "docs/evaluation/ocr_synth_rapidocr.json"),
         tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] != "all" else TYPES,
         len(sys.argv) > 4 and sys.argv[4] == "second")
