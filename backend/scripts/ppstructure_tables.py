"""PP-StructureV3 table reader, run in its own Python (PaddlePaddle and PaddleOCR are not in the app's environment).

The app calls it as a subprocess (app/triage/tables.py) with an image path; it prints JSON: one list of rows per table
found, each row a list of cell texts, in reading order. Models are PaddleOCR's (Apache-2.0), downloaded on first use.

Set up once (from the repo root):
    python -m venv models/venv-paddle
    models/venv-paddle/Scripts/python -m pip install paddlepaddle==3.1.1 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
    models/venv-paddle/Scripts/python -m pip install "paddleocr[doc-parser]"
then set JEEVIA_TABLE_PYTHON=models/venv-paddle/Scripts/python.exe in backend/.env.

Usage: <paddle python> backend/scripts/ppstructure_tables.py <image> [<image> ...]   (one JSON line per image)
"""

import json
import os
import sys
from html.parser import HTMLParser

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


class _Cells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def main(paths: list[str]) -> None:
    from paddleocr import PPStructureV3

    pipe = PPStructureV3(use_doc_orientation_classify=False, use_doc_unwarping=False, use_seal_recognition=False,
                         use_formula_recognition=False, use_chart_recognition=False, use_region_detection=False)
    for p in paths:
        tables = []
        for res in pipe.predict(p):
            for t in (res.json.get("res") or res.json).get("table_res_list") or []:
                cells = _Cells()
                cells.feed(t.get("pred_html") or "")
                tables.append(cells.rows)
        print(json.dumps({"image": p, "tables": tables}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
