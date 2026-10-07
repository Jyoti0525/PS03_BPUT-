"""Handwritten prescriptions: how much of the doctor's writing each OCR engine reads, and how many of the prescribed
medicines the app then names (B1, B10).

Data: "100 handwritten medical records" (chaithanyakota, Hugging Face, CC BY-ND 4.0): photographed Indian outpatient
prescriptions, each with the medicines written on it ("CEPODEM XP 325MG TAB, DOLO TAB 650MG, ..."). Used for
measurement only; the images are not copied into the repo or changed.

Engines: RapidOCR and docTR (OnnxTR), offline; Sarvam Vision, online (needs SARVAM_API_KEY; about ₹0.50 a page).
Each engine's reading is cached in <set_dir>/read_<engine>.json, so a rerun costs nothing.

Per prescribed medicine (its brand's first word, "cepodem"):
* read: the word is in the engine's text, allowing small slips (similarity 0.8 or more);
* named: the app's medicine list for that page (images.medicines) contains it.
Per medicine the app names: right (on the prescription) or wrong. Tuned on rx000–rx049 ("dev"), reported on
rx050–rx099 ("test") as well, which were not looked at while tuning.

Usage: python backend/scripts/eval_handwriting.py [set_dir=models/eval/rx_hand] [engines=rapidocr,doctr,sarvam]
"""

import difflib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # settings read ".env" from the working directory; run from the repo root

from app.triage import images  # noqa: E402

FORMS = re.compile(r"^(tab|tabs|tablet|cap|caps|syp|syr|syrup|susp|inj|neb|mdi|inhaler|pwd|powder|drops?|oint|cream|gel|gargle|"
                   r"respules?|rotacaps?|sachet|lotion|soln|solution|plus|forte|kid|ds|sr|cr|er|xr|mr|od|dt)$", re.I)


def wanted(item: str) -> str | None:
    """The brand's first word: "CEPODEM XP 325MG TAB" → "cepodem"."""
    for w in re.split(r"[\s\-]+", item.strip()):
        if w and not re.search(r"\d", w) and not FORMS.match(w):
            return w.lower() if len(w) >= 3 else None
    return None


def read_rapidocr(path: Path) -> list[dict]:
    import cv2

    from app.triage.extraction import _ocr_array

    a = cv2.imread(str(path), cv2.IMREAD_COLOR)
    h, w = a.shape[:2]
    return [{"text": x.text, "conf": x.conf, "bbox": [x.box[0] / w, x.box[1] / h, x.box[2] / w, x.box[3] / h]} for x in _ocr_array(a)]


def read_doctr(path: Path) -> list[dict]:
    import cv2

    from app.triage.extraction import _ocr2_array

    a = cv2.imread(str(path), cv2.IMREAD_COLOR)
    h, w = a.shape[:2]
    return [{"text": x.text, "conf": x.conf, "bbox": [x.box[0] / w, x.box[1] / h, x.box[2] / w, x.box[3] / h]} for x in _ocr2_array(a)]


def read_sarvam(path: Path) -> list[dict]:
    from app import sarvam

    return sarvam.read_page(path.read_bytes(), path.name)


READERS = {"rapidocr": read_rapidocr, "doctr": read_doctr, "sarvam": read_sarvam}


def _found(word: str, tokens: list[str], cutoff: float = 0.8) -> bool:
    return any(difflib.SequenceMatcher(None, word, t).ratio() >= cutoff for t in tokens)


def contents(item: str) -> str:
    """What a prescribed brand contains, from the brand list ("ALLEGRA 30MG SYRUP" → "fexofenadine (30mg/5ml)")."""
    brands = images._brands()[0]
    words = [w.lower() for w in re.split(r"[\s\-]+", item.strip()) if w and not re.search(r"\d", w) and not FORMS.match(w)]
    for key in ([" ".join(words[:2])] if len(words) > 1 else []) + words[:1]:
        if key in brands:
            return brands[key][1].lower()
    return ""


def score(lines: list[dict], truth: list[str]) -> dict:
    """A name the app gives is right when it is a prescribed brand, or a generic one of them contains (typed
    prescriptions print "FEXOFENADINE (30 MG)" under "Syrup Allegra")."""
    tokens = [t.lower() for ln in lines for t in re.findall(r"[A-Za-z]{3,}", ln["text"])]
    meds = images.medicines(lines)
    named = [m["name"].split()[0].lower() for m in meds]
    want = [w for w in (wanted(x) for x in truth) if w]
    inside = " ".join(contents(x) for x in truth)
    return {"want": want, "read": [w for w in want if _found(w, tokens)], "named_right": [w for w in want if _found(w, named, 0.85)],
            "named": [m["name"] for m in meds], "named_wrong": [n for n in named if not _found(n, want, 0.85) and not _found(n, re.findall(r"[a-z]{4,}", inside), 0.85)]}


def summarise(rows: list[dict]) -> dict:
    want = sum(len(r["want"]) for r in rows)
    named = sum(len(r["named"]) for r in rows)
    return {"pages": len(rows), "medicines": want,
            "read_pct": round(100 * sum(len(r["read"]) for r in rows) / want, 1) if want else None,
            "named_pct": round(100 * sum(len(r["named_right"]) for r in rows) / want, 1) if want else None,
            "names_given": named, "names_wrong": sum(len(r["named_wrong"]) for r in rows),
            "precision_pct": round(100 * (named - sum(len(r["named_wrong"]) for r in rows)) / named, 1) if named else None}


def main(set_dir: Path, engines: list[str]) -> dict:
    truth = {k: [x for x in v.split(",") if x.strip()] for k, v in json.loads((set_dir / "truth.json").read_text(encoding="utf-8")).items() if v}  # 15 pages list no medicines: left out
    result = {}
    for eng in engines:
        cache_f = set_dir / f"read_{eng}.json"
        cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
        for rid in sorted(truth):
            if rid in cache:
                continue
            path = next(set_dir.glob(f"{rid}.*"))
            t = time.perf_counter()
            try:
                cache[rid] = {"lines": READERS[eng](path), "s": round(time.perf_counter() - t, 2)}
            except Exception as e:  # noqa: BLE001 — record and move on; a failed page counts as nothing read
                cache[rid] = {"lines": [], "s": None, "error": f"{type(e).__name__}: {e}"[:200]}
            cache_f.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            print(eng, rid, len(cache[rid]["lines"]), cache[rid]["s"], flush=True)
        if eng == "sarvam":  # readings cached before block_lines existed: tables and Markdown into plain lines (idempotent)
            from app import sarvam

            for v in cache.values():
                v["lines"] = [x for ln in v["lines"] for x in sarvam.block_lines(ln["text"], ln["conf"], ln["bbox"])]
        per = {rid: score(cache[rid]["lines"], truth[rid]) for rid in sorted(truth)}
        dev = [per[r] for r in per if int(r[2:]) < 50]
        test = [per[r] for r in per if int(r[2:]) >= 50]
        secs = [cache[r]["s"] for r in cache if cache[r].get("s")]
        result[eng] = {"dev": summarise(dev), "test": summarise(test), "all": summarise(list(per.values())),
                       "seconds_per_page": round(sum(secs) / len(secs), 1) if secs else None,
                       "failed_pages": sum(1 for r in cache.values() if r.get("error")), "per_page": per}
        print(eng, json.dumps({k: v for k, v in result[eng].items() if k != "per_page"}))
    return result


if __name__ == "__main__":
    out = main(Path(sys.argv[1] if len(sys.argv) > 1 else "models/eval/rx_hand"),
               (sys.argv[2] if len(sys.argv) > 2 else "rapidocr,doctr,sarvam").split(","))
    Path("docs/evaluation/handwriting_rx100.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
