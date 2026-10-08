"""Live check of the photo description (app/triage/vlm.py describe) against a running Qwen3-VL llama-server.

    bash backend/scripts/start_vlm.sh &   # port 8032
    python backend/scripts/eval_vlm_photo.py <photo_folder> [out=docs/evaluation/vlm_photo.json]

Use synthetic or public photos only. For each photo it records the text kept (or that the guard blocked it) and the
time taken. Nothing is sent anywhere except the local server.
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("JEEVIA_VLM_URL", "http://127.0.0.1:8032")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.triage import vlm  # noqa: E402


def main(folder: str, out: str = str(Path(__file__).resolve().parents[2] / "docs/evaluation/vlm_photo.json")) -> None:
    rows = []
    for p in sorted(Path(folder).glob("*.jpg")) + sorted(Path(folder).glob("*.png")):
        t = time.perf_counter()
        got = vlm.describe(p.read_bytes(), "image/png" if p.suffix == ".png" else "image/jpeg")
        dt = round(time.perf_counter() - t, 1)
        row = {"photo": p.name, "seconds": dt, "text": got and got.get("text"), "blocked": (got or {}).get("blocked") or [], "empty": got is None}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    secs = sorted(r["seconds"] for r in rows)
    summary = {"photos": len(rows), "kept": sum(bool(r["text"]) for r in rows), "blocked": sum(bool(r["blocked"]) for r in rows),
               "median_seconds": secs[len(secs) // 2] if secs else None}
    Path(out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main(*sys.argv[1:])
