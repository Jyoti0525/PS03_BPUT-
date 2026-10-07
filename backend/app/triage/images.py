"""Image understanding without diagnosis (B10) and image redaction before storage (G3).

* `doc_type` — what kind of picture it is: lab report, prescription, medicine strip, discharge summary, maternal
  record card, other document, or a photo that is not a document. Keyword rules on the OCR text, each label
  carries the words that decided it. Photos that are not documents are attached for the clinician with no
  interpretation at all.
* `medicines` — medicine names read from a strip or prescription: generic names matched against the PMBJP list of
  2110 generic medicines (PIB, Government of India; see scripts/build_medicine_list.py), and on drug-order lines brand
  names ("Tab Dolo 650") matched against 186,000 Indian brands with what each contains (A-Z Medicine Dataset of
  India, CC BY-SA 4.0; see scripts/build_brand_list.py). Every item is "awaiting confirmation": nothing enters the
  record until a nurse or doctor ticks it.
* `redact` — before an image is stored: faces blurred (YuNet face detector, MIT, falling back to OpenCV's Haar
  cascade) and lines holding a phone, Aadhaar or ABHA number blacked out. PDFs and SVGs are stored as uploaded.
"""

import collections
import difflib
import gzip
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


@lru_cache(maxsize=1)
def _brands() -> tuple[dict[str, tuple[str, str]], dict[tuple[str, int], list[str]], collections.Counter]:
    """{brand: (product name, contains)}; one-word brands bucketed by first letter and length for fuzzy lookup; and
    how many products carry each brand's first word (Azithral: 8, Azithree: 1), to choose between equally close names."""
    out: dict[str, tuple[str, str]] = {}
    with gzip.open(DATA / "medicine_brands.tsv.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                key, shown, contains = line.rstrip("\n").split("\t")
                out[key] = (shown, contains)
    buckets: dict[tuple[str, int], list[str]] = collections.defaultdict(list)
    for key in out:
        if " " not in key and len(key) >= 5:
            buckets[(key[0], len(key))].append(key)
    family = collections.Counter(key.split()[0] for key in out)
    return out, buckets, family


# A drug order: a dosage form, a strength, a dose pattern or a duration. Brand names are matched only on such lines,
# because ordinary words are brands too ("Rest", "Follow").
_RX_LINE = re.compile(r"\b(tab|tabs|tablet|cap|caps|capsule|syp|syr|syrup|susp|suspension|inj|drops?|oint|cream|gel|neb|inhaler|mdi|"
                      r"respules?|gargle|lotion|sachet|pwd|powder)\b|\d+\s*(mg|ml|mcg)\b|\b\d\s*-\s*\d\s*-\s*\d\b|"
                      r"\b(od|bd|tds|tid|hs|sos|qid)\b|\bx\s*\d+\s*(d|days?)\b", re.I)
# Where the medicine's name sits on an order line: first ("Dolo 650 1-0-1"), or right after its form ("2. Syrup
# Ambrolite S", "Tab. Montair FX"). Elsewhere on the line are the dose and duration words, many of which are brands
# too (Days, Once, Twicef) — the first evaluation on handwritten prescriptions named them.
_FORMS = {"tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules", "syp", "syr", "syrup", "susp", "suspension",
          "inj", "injection", "drop", "drops", "oint", "ointment", "cream", "gel", "neb", "inhaler", "mdi", "respule", "respules",
          "gargle", "lotion", "sachet", "pwd", "powder", "spray", "solution", "soln", "rotacap", "rotacaps", "lozenge", "lozenges"}
_NOT_NAMES = {"once", "twice", "thrice", "daily", "day", "days", "week", "weeks", "month", "months", "times", "take", "apply",
              "mixed", "mix", "with", "for", "the", "and", "plus", "then", "after", "before", "morning", "night", "noon",
              "continue", "local", "each", "half", "one", "two", "three", "every", "hourly", "hours", "till", "until", "empty",
              "stomach", "food", "meal", "meals", "water", "milk", "dose", "stat", "sos", "rx", "adv", "advice", "review"}
# Generic-list entries that are everyday words ("Throat lozenges", "Water for injection", "Papaya leaf extract"):
# these count only in a medicine's place on an order line, never in "Throat normal" or "Eat papaya".
_COMMON = {"absolute", "activated", "alpha", "amino", "anise", "antioxidant", "antiseptic", "applicator", "atomizer", "beta",
           "bilberry", "cereal", "coal", "complex", "conjugated", "copper", "cranberry", "dental", "devil", "diabetes", "diluent",
           "dried", "essential", "evening", "face", "facewash", "fennel", "foaming", "fungal", "gama", "goat", "hand", "human",
           "inhalent", "intimate", "iron", "light", "liquid", "measuring", "micronized", "milk", "minerals", "mono",
           "monocarton", "mouth", "multi", "natural", "omega", "ophthalmic", "opthalmic", "pack", "papaya", "para", "pine",
           "protein", "rabies", "recombinant", "rehydration", "renal", "ringer", "rosehip", "saline", "screw", "sesame",
           "silver", "soluble", "solvent", "surgical", "tetanus", "throat", "toothpaste", "transfer", "water"}


# "Tab" as handwriting readers return it ("Jab Dolo 650", "Lab Azee", "Tag Montair", "7ab Recool").
_FORM_SLIPS = {"jab", "lab", "tag", "fab", "tah", "tb", "ab", "sy", "sig"}


def _name_slots(text: str) -> tuple[list[str], set[int]]:
    """The line's words, and the indexes of those that can be a medicine's name on an order line: the first word; the
    second after a short prefix ("DB Montek", "Sub Ziten"); the word after a form ("Syrup Ambrolite"), after a bracket
    ("Paracetamol (Crocin DS)") or after a number marker inside the line ("… 17) Dibem")."""
    found = list(re.finditer(r"[A-Za-z]{2,}", text))
    words = [m.group(0) for m in found]
    low = [w.lower() for w in words]
    slots = {0} if words else set()
    if len(words) > 1 and len(words[0]) <= 3:
        slots.add(1)
    for i, m in enumerate(found[1:], 1):
        before = text[: m.start()].rstrip()
        if low[i - 1] in _FORMS or low[i - 1] in _FORM_SLIPS or before.endswith("(") or re.search(r"\d+[).]$", before):
            slots.add(i)
    return words, {i for i in slots if low[i] not in _NOT_NAMES and low[i] not in _FORMS and low[i] not in _FORM_SLIPS}


def _confirmed(text: str, last_word: str) -> bool:
    """A brand not preceded by its form is taken only with more sign of a drug order: its strength straight after it
    ("Dolo 650"), a dose pattern, or a form elsewhere on the line. Without this, everyday words in a name's place were
    named as brands on the development pages ("Sunday", "Change", "Stream", "Rest")."""
    at = text.lower().find(last_word.lower())
    if at >= 0 and re.match(r"[\s:\-]*\(?\s*\d", text[at + len(last_word):]):
        return True
    return bool(re.search(r"\b\d\s*-\s*\d\s*-\s*\d\b", text)) or any(w.lower() in _FORMS for w in re.findall(r"[A-Za-z]{2,}", text))


def _slot(text: str, word: str) -> bool:
    """`word` sits where a medicine's name goes on this order line."""
    words, slots = _name_slots(text)
    return any(words[i].lower() == word.lower() for i in slots)


def _brand_strength(text: str, last_word: str, contains: str) -> str | None:
    """Brands carry their strength as a bare number after the name ("Dolo 650", "Azithral 500"). Its unit comes from
    the brand's own products when one of them has that strength ("Paracetamol (650mg)"); otherwise it is left unsaid."""
    at = text.lower().find(last_word.lower())
    rest = text[at + len(last_word):] if at >= 0 else ""
    m = re.match(r"[\s.:-]*(\d{1,4}(?:\.\d+)?)", rest)
    if not m or (len(m.group(1)) == 1 and re.match(r"\s*-\s*\d\s*-\s*\d", rest[m.end():])):
        return None  # "Dolo 1-0-1": that is the dose pattern
    n = m.group(1)
    unit = re.search(rf"\({re.escape(n)}\s*(mg|mcg|g|iu)\)", contains, re.I)
    return f"{n} {unit.group(1).lower()}" if unit else f"{n} (unit not read)"


def _brand(words: list[str], i: int) -> tuple[str, float, int] | None:
    """The brand starting at words[i]: two words ("Montair FX") before one; exact before close (OCR and handwriting
    slips, one-word brands of 5+ letters only; between equally close brands, the one with more products).
    Returns (brand key, similarity, words used)."""
    brands, buckets, family = _brands()
    w = words[i].lower()
    if i + 1 < len(words) and f"{w} {words[i + 1].lower()}" in brands:
        return f"{w} {words[i + 1].lower()}", 1.0, 2
    if len(w) >= 4 and w in brands:
        return w, 1.0, 1
    if len(w) >= 5:
        pool = [k for n in (len(w) - 1, len(w), len(w) + 1) for k in buckets.get((w[0], n), [])]
        close = difflib.get_close_matches(w, pool, n=5, cutoff=0.84)
        if close:
            best = max(close, key=lambda k: (round(difflib.SequenceMatcher(None, w, k).ratio(), 2), family[k]))
            return best, difflib.SequenceMatcher(None, w, best).ratio(), 1
    return None


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
            if key and key in _COMMON and not (_RX_LINE.search(ln["text"]) and _slot(ln["text"], w)):
                continue
            if key:
                cands.append((wl, key, round(float(ln.get("conf", 1.0)) * score, 2), _strength(lines, i, w), ln["text"], None))
    # Brands, on drug-order lines only, in a name's place, and never a word already read as a generic name
    # ("Paracetamol Tablets IP" is the generic, though a brand is called Paracetamol too).
    generic_words = {c[0] for c in cands}
    brands = _brands()[0]
    for i, ln in enumerate(lines):
        if not _RX_LINE.search(ln["text"]):
            continue
        words, slots = _name_slots(ln["text"])
        for j in sorted(slots):
            hit = None if words[j].lower() in generic_words or words[j].lower() in names else _brand(words, j)
            if not hit:
                continue
            key, score, used = hit
            if not (j and (words[j - 1].lower() in _FORMS or words[j - 1].lower() in _FORM_SLIPS)) and not _confirmed(ln["text"], words[j + used - 1]):
                continue
            shown, contains = brands[key]
            name = " ".join(x.upper() if len(x) <= 3 else x.capitalize() for x in key.split())
            strength = _strength(lines, i, words[j]) or _brand_strength(ln["text"], words[j + used - 1], contains)
            cands.append((key, f"brand:{key}", round(float(ln.get("conf", 1.0)) * score, 2), strength, ln["text"],
                          {"brand": name, "contains": contains, "product": shown}))
    # A torn or folded strip leaves pieces of a name ("heniramine" from "Chlorpheniramine") that fuzzy-match a different
    # medicine (pheniramine). A word that sits inside a longer word read elsewhere on the same picture is that fragment.
    read = {c[0] for c in cands}
    found: dict[str, dict] = {}
    for wl, key, conf, strength, text, brand in cands:
        if not brand and any(wl != other and wl in other for other in read):
            continue
        cur = found.get(key)
        if cur and (cur["strength"] or not strength) and cur["confidence"] >= conf:
            continue
        found[key] = {
            "name": brand["brand"] if brand else names[key],
            "strength": strength or (cur or {}).get("strength"),
            "seen": text[:120],
            "confidence": max(conf, (cur or {}).get("confidence", 0)),
            "status": "awaiting_confirmation",
            **({"kind": "brand", "contains": brand["contains"]} if brand else {"kind": "generic"}),
        }
    # Typed prescriptions print each brand's contents under it ("Syrup Allegra" / "FEXOFENADINE (30 MG)"): one medicine,
    # shown once, as the brand with what it contains.
    inside = " ".join(m["contains"] for m in found.values() if m["kind"] == "brand").lower()
    return [m for m in found.values() if m["kind"] == "brand" or m["name"].split()[0].lower() not in inside]


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
