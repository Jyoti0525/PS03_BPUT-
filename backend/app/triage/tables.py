"""Lab report rows from PP-StructureV3's table reader (PaddleOCR 3, Apache-2.0), as a third reading of a report.

The OCR engines give text lines and the app puts each row together from where the lines sit on the page; a tilted or
curled photo can join the wrong value to a test. PP-StructureV3 finds the table and its cells instead. Its rows go
through the same parse_labs, and each test is compared with the OCR reading: a different value marks the row for
checking with both readings, as the second engine does (B9). It never replaces a value.

PaddlePaddle does not share the app's Python packages, so it runs in its own environment as a subprocess
(scripts/ppstructure_tables.py). Off unless JEEVIA_TABLE_PYTHON names that environment's python.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from app.config import get_settings
from app.triage.extraction import Line, OcrResult, _same, parse_labs

ENGINE = "PP-StructureV3 table"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ppstructure_tables.py"


def enabled() -> bool:
    p = get_settings().table_python
    return bool(p) and Path(p).exists()


def read_tables(image: bytes, suffix: str = ".jpg") -> list[list[list[str]]] | None:
    """Every table on the page as rows of cell texts; None when off or the reader failed."""
    if not enabled():
        return None
    with tempfile.TemporaryDirectory(prefix="jeevia-table-") as d:
        path = Path(d) / f"page{suffix}"
        path.write_bytes(image)
        try:
            out = subprocess.run([get_settings().table_python, str(SCRIPT), str(path)], capture_output=True, text=True, encoding="utf-8",
                                 timeout=get_settings().table_timeout_s, check=True)  # nosec B603: fixed script, our own file
        except (subprocess.SubprocessError, OSError):
            return None
    for line in reversed(out.stdout.splitlines()):
        if line.startswith("{"):
            return json.loads(line).get("tables") or []
    return None


def rows_from_tables(tables: list[list[list[str]]], sex: str | None = None, pregnant: bool = False) -> list[dict]:
    """parse_labs over the table rows: one line per row, cells in order, so a row can never borrow another's value."""
    lines = [Line("   ".join(c for c in row if c), [0.0, 40.0 * i, 1000.0, 30.0], 0.99)
             for i, row in enumerate(r for t in tables for r in t)]
    return parse_labs(OcrResult(ENGINE, lines, (1000.0, 40.0 * max(1, len(lines)))), sex, pregnant) if lines else []


def check(rows: list[dict], table_rows: list[dict]) -> dict:
    """Mark rows where the table reader read a different value; returns the tally for the note."""
    by = {r["test_key"]: r for r in table_rows if r.get("value") is not None}
    agree, differ = 0, []
    for r in rows:
        b = by.pop(r["test_key"], None)
        if b is None:
            continue
        if _same(r, b):
            agree += 1
            r["table_reader"] = "agrees"
        else:
            r["needs_check"], r["table_reader"] = True, "differs"
            r["checks"].append(f'The table reader read {b["value"]} — check the crop')
            differ.append({"test": r["test"], "test_key": r["test_key"], "first": r["value"], "table": b["value"]})
    return {"engine": ENGINE, "agree": agree, "disagreements": differ, "table_only": [b["test"] for b in by.values()]}
