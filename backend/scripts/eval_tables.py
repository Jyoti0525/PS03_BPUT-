"""PP-StructureV3 table reader (app/triage/tables.py) on the held-out synthetic lab reports.

For each report: every true row is looked up in the table reader's rows (exact value), and every value the OCR engines
got wrong (docs/evaluation/ocr_heldout_two_engines.json) is checked against the table reading: if the table reader
read something else, the app would have marked that row for checking. Needs JEEVIA_TABLE_PYTHON (models/venv-paddle).

Usage: python backend/scripts/eval_tables.py [per_type=8] [out=docs/evaluation/tables_heldout.json]
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.triage import tables  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "models" / "eval" / "ocr_heldout"
TYPES = ("scan", "photo", "poor_photo", "photocopy", "thermal")


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def main(per_type: int = 8, out: str = "docs/evaluation/tables_heldout.json") -> None:
    truth = json.loads((EVAL / "truth.json").read_text(encoding="utf-8"))
    ocr = json.loads((ROOT / "docs/evaluation/ocr_heldout_two_engines.json").read_text(encoding="utf-8"))["detail"]
    ids = sorted(truth)[:per_type]
    img = {(t, i): str(next((EVAL / t).glob(f"{i}.*"))) for t in TYPES for i in ids}
    paths = list(img.values())
    py = str(ROOT / "models" / "venv-paddle" / "Scripts" / "python.exe")
    t0 = time.time()
    run = subprocess.run([py, str(tables.SCRIPT), *paths], capture_output=True, text=True, encoding="utf-8", check=True)
    seconds = time.time() - t0
    found = {json.loads(l)["image"]: json.loads(l)["tables"] for l in run.stdout.splitlines() if l.startswith("{")}
    by_type, detail = {}, []
    for t in TYPES:
        s = by_type[t] = {"reports": 0, "no_table": 0, "rows": 0, "exact": 0, "missed": 0, "wrong": 0, "ocr_errors": 0, "ocr_errors_flagged": 0}
        ocr_by_id = {r["id"]: r for r in ocr.get(t, [])}
        for i in ids:
            tb = found.get(img[t, i])
            s["reports"] += 1
            if not tb:
                s["no_table"] += 1
            got = {r["test_key"]: r for r in tables.rows_from_tables(tb or [])}
            for row in truth[i]["rows"]:
                s["rows"] += 1
                g = got.get(row["test_key"])
                if g is None or g.get("value") is None:
                    s["missed"] += 1
                elif _num(g["value"]) == _num(row["value"]):
                    s["exact"] += 1
                else:
                    s["wrong"] += 1
                    detail.append({"type": t, "id": i, "test": row["test_key"], "truth": row["value"], "table": g["value"]})
            for e in ocr_by_id.get(i, {}).get("errors", []):
                if not e.get("found") or e.get("value_ok"):
                    continue
                s["ocr_errors"] += 1
                g = got.get(e["test"])
                if g is not None and _num(g.get("value")) != _num(e["read"]):
                    s["ocr_errors_flagged"] += 1
    total = {k: sum(v[k] for v in by_type.values()) for k in next(iter(by_type.values()))}
    res = {"engine": tables.ENGINE, "reports_per_type": per_type, "seconds_total": round(seconds, 1),
           "seconds_per_page": round(seconds / len(paths), 1), "by_type": by_type, "total": total, "wrong_values": detail}
    Path(out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "wrong_values"}, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]) if a else 8, *a[1:2])
