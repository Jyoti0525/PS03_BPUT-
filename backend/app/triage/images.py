"""Image understanding without diagnosis (B10) and image redaction before storage (G3).

* `doc_type` — what kind of picture it is: lab report, prescription, medicine strip, discharge summary, maternal
  record card, other document, or a photo that is not a document. Keyword rules on the OCR text, each label
  carries the words that decided it. Photos that are not documents are attached for the clinician with no
  interpretation at all.
* `medicines` — generic medicine names read from a strip or prescription, matched against the PMBJP list of 2110
  generic medicines (PIB, Government of India; see scripts/build_medicine_list.py). Every item is
  "awaiting confirmation": nothing enters the record until a nurse or doctor ticks it.
* `redact` — before an image is stored: faces blurred (YuNet face detector, MIT, falling back to OpenCV's Haar
  cascade) and lines holding a phone, Aadhaar or ABHA number blacked out. PDFs and SVGs are stored as uploaded.
"""

import difflib
import re
import threading
from functools import lru_cache
from pathlib import Path

from ..privacy import scrub

DATA = Path(__file__).with_name("data")
YUNET = DATA / "face_detection_yunet_2023mar.onnx"

DOC_TYPES = {
    "lab_report": "Lab report",
    "prescription": "Prescription",
    "medicine_strip": "Medicine strip or pack",
    "discharge_summary": "Discharge summary",
    "maternal_card": "Mother & child protection card",
    "other_document": "Other document",
    "non_document": "Photo (not a document) — not interpreted",
}
_CUES = {
    "discharge_summary": r"discharge summary|date of discharge|date of admission|course in (the )?hospital|condition at discharge|advice on discharge",
    "maternal_card": r"mother (and|&) child protection|mcp card|\banc\b|antenatal|expected date of delivery|\bedd\b|\blmp\b",
    "medicine_strip": r"\bmfg\b|\bmfd\b|\bmfg\.? ?date|\bexp\b|\bexp\.? ?date|\bexpiry\b|batch|\bb\.? ?no\b|\bmrp\b|schedule h|store (below|in a)|each (film[- ]coated |uncoated )?(tablet|capsule) contains|keep out of reach|\bmanufactured by\b|\bmarketed by\b",
    "prescription": r"\brx\b|℞|\breg\.? ?no\b|registration no|\bdr\.? [a-z]|\bm\.?b\.?b\.?s\b|\b\d-\d-\d\b|\bod\b|\bbd\b|\btds\b|\bsos\b|after food|before food|follow[- ]up|\badv(ice)?\b",
    "lab_report": r"reference (range|interval)|biological ref|normal range|\bresult\b|\bunits?\b|laboratory|pathology|diagnostic(s)? (centre|center|lab)|sample (collected|received)|haemoglobin|hemoglobin|glucose|creatinine",
}


# ---------------------------------------------------------------- medicine names


@lru_cache(maxsize=1)
def _names() -> tuple[dict[str, str], list[str]]:
    """{single word key: display name}, plus the list of keys for fuzzy matching. The first word of each generic
    name is its key ("diclofenac sodium" → "diclofenac"); multi-word names keep the shortest full form."""
    best: dict[str, str] = {}
    for line in (DATA / "medicines_pmbjp.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        key = line.split()[0]
        if len(key) >= 4 and (key not in best or len(line) < len(best[key])):
            best[key] = line
    return best, sorted(best)


# "2m9", "10rng": OCR misreads of "mg" on foil (seen on a real strip photo, 5 Oct).
_STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|m9|rng|mcg|µg|g|ml|iu|%)(?![a-z])", re.I)
_BARE_NUMBER = re.compile(r"^\s*(\d{1,4}(?:\.\d+)?)\s*$")


def _words(text: str) -> list[str]:
    """Words of 5+ letters. Strip print is tightly set and OCR glues words together ("ChlorpheniramineMaleate IP",
    "patacetamolIP"), so a lower-to-upper case change also splits."""
    return re.findall(r"[A-Za-z]{5,}", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text))


def _strength(lines: list[dict], i: int, word: str) -> str | None:
    """Strength printed after the name on the same line, or in a separate box on the same printed row to its right
    (strips set the strength in a column: "Paracetamol IP ........ 500 mg", which OCR reads as two boxes)."""
    text = lines[i]["text"]
    at = text.lower().find(word.lower())
    if s := _STRENGTH.search(text[at:] if at >= 0 else text):
        return f"{s.group(1)} {'mg' if s.group(2).lower() in ('m9', 'rng') else s.group(2).lower()}"
    box = lines[i].get("bbox")
    if not box:
        return None
    x, y, w, h = box
    row = [ln for j, ln in enumerate(lines) if j != i and ln.get("bbox") and ln["bbox"][0] >= x + w * 0.5
           and abs((ln["bbox"][1] + ln["bbox"][3] / 2) - (y + h / 2)) < max(h, ln["bbox"][3]) * 0.6]
    for ln in sorted(row, key=lambda ln: ln["bbox"][0]):
        if s := _STRENGTH.search(ln["text"]):
            return f"{s.group(1)} {'mg' if s.group(2).lower() in ('m9', 'rng') else s.group(2).lower()}"
        if b := _BARE_NUMBER.match(ln["text"]):
            return f"{b.group(1)} (unit not read)"
    return None


def medicines(lines: list[dict]) -> list[dict]:
    """Medicine names (and strength, when printed next to them) found in OCR lines [{'text','conf','bbox'}]."""
    names, keys = _names()
    cands = []  # (word, key, confidence, strength, line text)
    for i, ln in enumerate(lines):
        for w in _words(ln["text"]):
            wl = w.lower()
            key, score = (wl, 1.0) if wl in names else (None, 0.0)
            if not key:
                close = difflib.get_close_matches(wl, keys, n=1, cutoff=0.86)
                if close:
                    key, score = close[0], difflib.SequenceMatcher(None, wl, close[0]).ratio()
            if key:
                cands.append((wl, key, round(float(ln.get("conf", 1.0)) * score, 2), _strength(lines, i, w), ln["text"]))
    # A torn or folded strip leaves pieces of a name ("heniramine" from "Chlorpheniramine") that fuzzy-match a different
    # medicine (pheniramine). A word that sits inside a longer word read elsewhere on the same picture is that fragment.
    read = {c[0] for c in cands}
    found: dict[str, dict] = {}
    for wl, key, conf, strength, text in cands:
        if any(wl != other and wl in other for other in read):
            continue
        cur = found.get(key)
        if cur and (cur["strength"] or not strength) and cur["confidence"] >= conf:
            continue
        found[key] = {
            "name": names[key],
            "strength": strength or (cur or {}).get("strength"),
            "seen": text[:120],
            "confidence": max(conf, (cur or {}).get("confidence", 0)),
            "status": "awaiting_confirmation",
        }
    return list(found.values())


def doc_type(lines: list[dict], lab_rows: int = 0) -> dict:
    """{'type', 'label', 'why'} from the OCR text. Deterministic; the words that decided it are returned."""
    text = " ".join(x["text"] for x in lines).lower()
    if len(lines) < 3 or len(text) < 25:
        return {"type": "non_document", "label": DOC_TYPES["non_document"], "why": "little or no printed text"}
    hits = {k: sorted({m.group(0) for m in re.finditer(p, text)}) for k, p in _CUES.items()}
    meds = medicines(lines)
    if lab_rows >= 2:
        return {"type": "lab_report", "label": DOC_TYPES["lab_report"], "why": f"{lab_rows} lab values read"}
    for k in ("discharge_summary", "maternal_card"):
        if len(hits[k]) >= 2:
            return {"type": k, "label": DOC_TYPES[k], "why": ", ".join(hits[k][:4])}
    if meds and len(hits["medicine_strip"]) >= 1 and len(hits["prescription"]) < 2:
        return {"type": "medicine_strip", "label": DOC_TYPES["medicine_strip"], "why": ", ".join([m["name"] for m in meds[:2]] + hits["medicine_strip"][:3])}
    if meds and hits["prescription"]:
        return {"type": "prescription", "label": DOC_TYPES["prescription"], "why": ", ".join([m["name"] for m in meds[:2]] + hits["prescription"][:3])}
    if len(hits["lab_report"]) >= 2:
        return {"type": "lab_report", "label": DOC_TYPES["lab_report"], "why": ", ".join(hits["lab_report"][:4])}
    return {"type": "other_document", "label": DOC_TYPES["other_document"], "why": "printed text, no known document pattern"}


# ---------------------------------------------------------------- redaction

_face_lock = threading.Lock()


def _faces(img) -> list[tuple[int, int, int, int]]:
    import cv2

    h, w = img.shape[:2]
    with _face_lock:
        if YUNET.exists() and hasattr(cv2, "FaceDetectorYN"):
            det = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.7, 0.3, 50)
            _, faces = det.detect(img)
            return [tuple(int(v) for v in f[:4]) for f in (faces if faces is not None else [])]
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return [tuple(int(v) for v in f) for f in cascade.detectMultiScale(grey, 1.1, 5, minSize=(40, 40))]


def face_engine() -> str:
    return "YuNet face detector (OpenCV Zoo, MIT)" if YUNET.exists() else "OpenCV Haar cascade"


def redact(data: bytes, content_type: str, text_lines: list[dict] | None = None) -> tuple[bytes, dict]:
    """Blur faces and black out ID-number lines in a photo before it is stored. `text_lines` are OCR lines with
    normalised boxes [x, y, w, h] (0–1). Returns (bytes to store, report)."""
    if not content_type.startswith("image/") or content_type == "image/svg+xml":
        return data, {"faces": 0, "id_numbers": 0, "skipped": "not a photo"}
    try:
        import cv2
        import numpy as np
    except ImportError:
        return data, {"faces": 0, "id_numbers": 0, "skipped": "image redaction not installed"}
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return data, {"faces": 0, "id_numbers": 0, "skipped": "could not read the image"}
    h, w = img.shape[:2]
    faces = _faces(img)
    for x, y, fw, fh in faces:
        pad_w, pad_h = int(fw * 0.15), int(fh * 0.2)
        x0, y0, x1, y1 = max(0, x - pad_w), max(0, y - pad_h), min(w, x + fw + pad_w), min(h, y + fh + pad_h)
        roi = img[y0:y1, x0:x1]
        if roi.size:
            small = cv2.resize(roi, (max(1, (x1 - x0) // 16), max(1, (y1 - y0) // 16)), interpolation=cv2.INTER_LINEAR)
            img[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)  # pixelate: not reversible
    ids = 0
    for ln in text_lines or []:
        if scrub(ln.get("text"), numbers_only=True)[1]:
            bx, by, bw, bh = ln["bbox"]
            cv2.rectangle(img, (int(bx * w) - 4, int(by * h) - 4), (int((bx + bw) * w) + 4, int((by + bh) * h) + 4), (0, 0, 0), -1)
            ids += 1
    # Always re-encoded, even with nothing to hide: this also drops EXIF metadata such as the GPS position.
    ext = {"image/png": ".png", "image/webp": ".webp"}.get(content_type, ".jpg")
    ok, buf = cv2.imencode(ext, img, [cv2.IMWRITE_JPEG_QUALITY, 90] if ext == ".jpg" else [])
    if not ok:
        return data, {"faces": 0, "id_numbers": 0, "skipped": "re-encoding failed — stored without redaction"}
    return buf.tobytes(), {"faces": len(faces), "id_numbers": ids, "engine": face_engine()}
