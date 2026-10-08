"""Second document-type label (Qwen3-VL-4B, app/triage/vlm.py) against the truth and against the text-based label.

Pictures: synthetic lab reports (6 of each capture type from the held-out OCR set), synthetic medicine strips
(eval_strips.py) and public handwritten prescriptions (rx_hand, CC BY-ND, read only). For each: the true type, the
label from the OCR text (images.doc_type), the image model's label, and the seconds it took. Needs the image model's
server (scripts/start_vlm.sh) and JEEVIA_VLM_URL.

Usage: python backend/scripts/eval_vlm_doctype.py [out=docs/evaluation/vlm_doctype.json]
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("JEEVIA_VLM_URL", "http://127.0.0.1:8032")
from app.config import get_settings  # noqa: E402
from app.triage import vlm  # noqa: E402
from app.triage.extraction import extract_document  # noqa: E402

EVAL = Path(__file__).resolve().parents[2] / "models" / "eval"


def pictures() -> list[tuple[Path, str]]:
    out = []
    for kind in ("scan", "photo", "poor_photo", "photocopy", "thermal"):
        out += [(p, "lab_report") for p in sorted((EVAL / "ocr_heldout" / kind).glob("*.jpg"))[:6]]
    out += [(p, "medicine_strip") for p in sorted((EVAL / "strips").glob("*.jpg"))[::3][:15]]
    out += [(p, "prescription") for p in sorted(x for x in (EVAL / "rx_hand").rglob("*") if x.suffix.lower() in (".jpg", ".jpeg", ".png"))[:15]]
    return out


def main(out: str = "docs/evaluation/vlm_doctype.json") -> None:
    get_settings.cache_clear()
    rows = []
    for path, truth in pictures():
        data = path.read_bytes()
        ctype = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        os.environ["JEEVIA_VLM_URL"] = ""  # the text label alone first
        get_settings.cache_clear()
        text_label = extract_document(data, ctype)["doc_type"]["type"]
        os.environ["JEEVIA_VLM_URL"] = "http://127.0.0.1:8032"
        get_settings.cache_clear()
        t = time.perf_counter()
        got = vlm.label(data, ctype)
        rows.append({"file": f"{path.parent.name}/{path.name}", "truth": truth, "text_label": text_label, "image_label": got and got["type"],
                     "seconds": round(time.perf_counter() - t, 1)})
        print(rows[-1], flush=True)
    by = {}
    for r in rows:
        b = by.setdefault(r["truth"], {"n": 0, "text_right": 0, "image_right": 0, "image_none": 0, "differ": 0, "differ_text_wrong": 0})
        b["n"] += 1
        b["text_right"] += r["text_label"] == r["truth"]
        b["image_right"] += r["image_label"] == r["truth"]
        b["image_none"] += r["image_label"] is None
        if r["image_label"] and r["image_label"] != r["text_label"]:
            b["differ"] += 1
            b["differ_text_wrong"] += r["text_label"] != r["truth"]
    secs = sorted(r["seconds"] for r in rows)
    res = {"model": get_settings().vlm_model_name, "by_type": by, "median_seconds": secs[len(secs) // 2] if secs else None, "pictures": rows}
    Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "pictures"}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
