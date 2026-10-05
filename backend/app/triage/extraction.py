"""Medical-document extraction: OCR → lines with boxes → lab rows with checks.

Engines, chosen by file type and named truthfully in every output:
* Photos (JPEG/PNG/WebP): RapidOCR — PaddleOCR PP-OCR detection/recognition models run on ONNX
  Runtime (Apache-2.0), offline, CPU. An image-quality gate runs first (blur, darkness, size).
* PDFs with a text layer: the embedded text (pypdfium2), no OCR needed. Scanned PDFs: each page is
  rasterised (pypdfium2) and sent through the same OCR.
* SVG (the synthetic training slips): the SVG's own text elements.

Lab parsing is deterministic: a dictionary of common Indian lab tests with synonyms and OCR
confusions, the value / unit / printed reference range read from the same row, a plausibility
range per test (an impossible number means a misread, not a diagnosis) and a confidence floor.
Anything doubtful is marked `needs_check` for the reviewer; nothing is silently corrected.
"""

import difflib
import io
import re
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

CONF_FLOOR = 0.85  # OCR confidence below this is shown as "needs checking"
STALE_DAYS = 90


@dataclass
class Line:
    text: str
    box: list[float]  # x, y, w, h in page pixels
    conf: float
    page: int = 0

    @property
    def yc(self) -> float:
        return self.box[1] + self.box[3] / 2


@dataclass
class OcrResult:
    engine: str
    lines: list[Line] = field(default_factory=list)
    page_size: tuple[float, float] = (1.0, 1.0)
    quality: dict = field(default_factory=lambda: {"ok": True, "issues": []})
    error: str | None = None


# ---------------------------------------------------------------- engines

_ocr = None
_ocr_lock = threading.Lock()


def _rapidocr():
    global _ocr
    with _ocr_lock:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR  # optional dependency

            _ocr = RapidOCR()
        return _ocr


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except ImportError:
        return False


def image_quality(img) -> dict:
    """Blur (variance of the Laplacian), exposure and size. `img` is a greyscale numpy array."""
    import cv2

    issues = []
    h, w = img.shape[:2]
    if min(h, w) < 500:
        issues.append(f"Low resolution ({w}×{h}) — retake closer")
    mean, contrast = float(img.mean()), float(img.std())
    if mean < 70:
        issues.append("Too dark — retake in better light")
    if contrast < 25:
        issues.append("Low contrast / glare — retake without flash, flat to the camera")
    sharp = float(cv2.Laplacian(img, cv2.CV_64F).var())
    if sharp < 60:
        issues.append("Blurry — hold the phone steady and retake")
    return {"ok": not issues, "issues": issues, "sharpness": round(sharp, 1), "brightness": round(mean, 1), "contrast": round(contrast, 1), "size": [w, h]}


def _ocr_array(arr, page: int = 0) -> list[Line]:
    res, _ = _rapidocr()(arr)
    out = []
    for box, text, conf in res or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        out.append(Line(text.strip(), [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)], float(conf), page))
    return out


def ocr_image(data: bytes) -> OcrResult:
    import cv2
    import numpy as np

    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return OcrResult("none", error="Could not read the image file")
    grey = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    q = image_quality(grey)
    if not ocr_available():
        return OcrResult("none", quality=q, error="OCR engine not installed on this server — review the image directly")
    lines = _ocr_array(arr)
    if lines and sum(x.conf for x in lines) / len(lines) < 0.75:
        q["issues"].append("Text hard to read — low recognition confidence")
        q["ok"] = False
    return OcrResult("RapidOCR (PaddleOCR PP-OCR models, ONNX Runtime, offline)", lines, (arr.shape[1], arr.shape[0]), q)


def read_pdf(data: bytes) -> OcrResult:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    lines: list[Line] = []
    size = (1.0, 1.0)
    text_layer = True
    for i, page in enumerate(pdf):
        if i >= 5:
            break
        w, h = page.get_size()
        size = (w, h)
        tp = page.get_textpage()
        n = tp.count_rects()
        if n == 0:
            text_layer = False
            break
        for j in range(n):
            l, b, r, t = tp.get_rect(j)
            txt = tp.get_text_bounded(l, b, r, t).strip()
            if txt:
                lines.append(Line(txt, [l, h - t, r - l, t - b], 1.0, i))
    if text_layer and lines:
        return OcrResult("PDF text layer (pypdfium2) — digital report, no OCR", lines, size)
    if not ocr_available():
        return OcrResult("none", error="Scanned PDF and no OCR engine installed — review the file directly")
    import numpy as np

    lines = []
    for i, page in enumerate(pdf):
        if i >= 3:
            break
        img = page.render(scale=2).to_pil().convert("RGB")
        size = img.size
        lines += _ocr_array(np.array(img)[:, :, ::-1], i)
    return OcrResult("RapidOCR on rasterised scanned PDF (PaddleOCR PP-OCR models, ONNX Runtime)", lines, size)


def read_svg(data: bytes) -> OcrResult:
    root = ET.fromstring(data)
    ns = "{http://www.w3.org/2000/svg}"
    w = float(root.get("width", 640))
    h = float(root.get("height", 480))
    lines = []
    for t in root.iter(f"{ns}text"):
        txt = "".join(t.itertext()).strip()
        if txt:
            size = float(t.get("font-size") or 14)
            x, y = float(t.get("x", 0)), float(t.get("y", 0))
            lines.append(Line(txt, [x, y - size, len(txt) * size * 0.6, size * 1.2], 1.0))
    return OcrResult("SVG text layer (synthetic training slip — not OCR)", lines, (w, h))


def read_document(data: bytes, content_type: str) -> OcrResult:
    try:
        if content_type == "image/svg+xml":
            return read_svg(data)
        if content_type == "application/pdf":
            return read_pdf(data)
        if content_type.startswith("image/"):
            return ocr_image(data)
        return OcrResult("none", error=f"{content_type} is not a readable document")
    except Exception as e:  # never let a bad file break intake; the reviewer still has the original
        return OcrResult("none", error=f"Could not read the document ({type(e).__name__})")


# ---------------------------------------------------------------- lab dictionary

@dataclass(frozen=True)
class Test:
    key: str
    name: str
    synonyms: tuple[str, ...]
    unit: str
    plausible: tuple[float, float]
    ref: tuple[float, float] | None  # typical adult range, used only when the slip prints none
    loinc: str | None = None
    kind: str = "number"  # number | bp | dipstick | qualitative


TESTS = [
    Test("glucose_fasting", "Fasting blood sugar", ("fasting blood sugar", "fbs", "fasting blood glucose", "fasting plasma glucose", "fpg", "blood sugar fasting", "glucose fasting", "blood sugar f"), "mg/dL", (10, 1500), (70, 100), "1558-6"),
    Test("glucose_pp", "Post-prandial blood sugar", ("post prandial blood sugar", "ppbs", "pp blood sugar", "blood sugar pp", "glucose pp", "post prandial glucose", "2 hr pp"), "mg/dL", (10, 1500), (70, 140)),
    Test("glucose_random", "Random blood sugar", ("random blood sugar", "rbs", "grbs", "random blood glucose", "blood sugar random", "glucose random"), "mg/dL", (10, 1500), (70, 140)),
    Test("hba1c", "HbA1c", ("hba1c", "hbalc", "glycated haemoglobin", "glycated hemoglobin", "glycosylated haemoglobin", "glycosylated hemoglobin", "a1c"), "%", (2, 20), (4.0, 5.6), "4548-4"),
    Test("haemoglobin", "Haemoglobin", ("haemoglobin", "hemoglobin", "hb", "hgb", "hb%"), "g/dL", (2, 25), (12.0, 17.0), "718-7"),
    Test("pcv", "PCV / haematocrit", ("pcv", "packed cell volume", "haematocrit", "hematocrit", "hct"), "%", (5, 75), (36, 50), "4544-3"),
    Test("wbc", "Total WBC count", ("total wbc", "wbc", "tlc", "total leucocyte count", "total leukocyte count", "white blood cells", "wbc count", "total count"), "/µL", (100, 200000), (4000, 11000), "6690-2"),
    Test("platelets", "Platelet count", ("platelet count", "platelets", "plt"), "/µL", (1000, 2000000), (150000, 450000), "777-3"),
    Test("creatinine", "Serum creatinine", ("serum creatinine", "s creatinine", "creatinine"), "mg/dL", (0.1, 25), (0.6, 1.3), "2160-0"),
    Test("urea", "Blood urea", ("blood urea", "serum urea", "urea"), "mg/dL", (2, 400), (15, 45)),
    Test("egfr", "eGFR", ("egfr",), "mL/min/1.73m²", (1, 200), (60, 999)),
    Test("potassium", "Serum potassium", ("serum potassium", "s potassium", "potassium", "k+"), "mmol/L", (1.0, 10.0), (3.5, 5.1), "2823-3"),
    Test("sodium", "Serum sodium", ("serum sodium", "s sodium", "sodium", "na+"), "mmol/L", (100, 190), (135, 145), "2951-2"),
    Test("cholesterol", "Total cholesterol", ("total cholesterol", "cholesterol total", "serum cholesterol", "cholesterol"), "mg/dL", (50, 700), (0, 200), "2093-3"),
    Test("ldl", "LDL cholesterol", ("ldl cholesterol", "ldl"), "mg/dL", (10, 500), (0, 100)),
    Test("hdl", "HDL cholesterol", ("hdl cholesterol", "hdl"), "mg/dL", (5, 150), (40, 999), "2085-9"),
    Test("triglycerides", "Triglycerides", ("triglycerides", "triglyceride", "tg"), "mg/dL", (10, 5000), (0, 150), "2571-8"),
    Test("bilirubin", "Total bilirubin", ("total bilirubin", "bilirubin total", "serum bilirubin", "s bilirubin", "bilirubin"), "mg/dL", (0.05, 40), (0.2, 1.2), "1975-2"),
    Test("alt", "SGPT / ALT", ("sgpt", "alt", "alanine aminotransferase", "sgpt alt"), "U/L", (1, 5000), (7, 56), "1742-6"),
    Test("ast", "SGOT / AST", ("sgot", "ast", "aspartate aminotransferase", "sgot ast"), "U/L", (1, 5000), (10, 40), "1920-8"),
    Test("tsh", "TSH", ("tsh", "thyroid stimulating hormone"), "µIU/mL", (0.001, 150), (0.4, 4.0), "3016-3"),
    Test("bp", "Blood pressure", ("blood pressure", "bp"), "mmHg", (40, 300), None, kind="bp"),
    Test("urine_albumin", "Urine albumin / protein", ("urine albumin", "urine protein", "albumin urine", "proteinuria", "urine alb"), "", (0, 4), None, kind="dipstick"),
    Test("malaria", "Malaria test", ("malaria", "malaria rdt", "malaria antigen", "mp smear", "mp"), "", (0, 1), None, kind="qualitative"),
    Test("dengue_ns1", "Dengue NS1", ("dengue ns1", "ns1 antigen", "ns1"), "", (0, 1), None, kind="qualitative"),
]

UNITS = [r"mg\s*/\s*dl", r"g\s*/\s*dl", r"mmol\s*/\s*l", r"meq\s*/\s*l", r"u\s*/\s*l", r"iu\s*/\s*l", r"µiu\s*/\s*ml", r"uiu\s*/\s*ml", r"miu\s*/\s*l",
         r"ml\s*/\s*min(\s*/\s*1\.73\s*m[2²])?", r"/\s*[uµ]l", r"/\s*cumm", r"cells\s*/\s*[uµ]l", r"lakhs?(\s*/\s*cumm)?", r"x?\s*10\s*\^?\s*[39]\s*/\s*[uµ]?l", r"mmhg", r"%", r"cm", r"fl", r"pg"]
UNIT_RE = re.compile("(" + "|".join(UNITS) + ")", re.I)
NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)(?![\d])")
BP_RE = re.compile(r"(\d{2,3})\s*/\s*(\d{2,3})")
RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:[.,]\d+)?)|([<>≤≥]=?)\s*(\d+(?:\.\d+)?)")
DIPSTICK_RE = re.compile(r"(?<![\w+])(nil|negative|trace|[1-4]\s*\+|\+{1,4})(?![\w+])", re.I)
QUAL_RE = re.compile(r"\b(positive|negative|reactive|non[- ]?reactive|detected|not detected|pf|pv)\b", re.I)
DATE_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})")


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9%+]", "", s.lower().replace("µ", "u"))


_SYN = sorted(((_squash(s), t) for t in TESTS for s in t.synonyms), key=lambda x: -len(x[0]))


def match_test(text: str) -> tuple[Test, float] | None:
    """Longest synonym that the line starts with; otherwise a close fuzzy match (OCR slips)."""
    sq = _squash(text)
    if not sq:
        return None
    for syn, t in _SYN:
        if sq.startswith(syn) and (len(syn) >= 3 or sq == syn):
            return t, 1.0
    best = max(((difflib.SequenceMatcher(None, sq[: len(syn) + 2], syn).ratio(), t) for syn, t in _SYN if len(syn) >= 5), key=lambda x: x[0], default=(0, None))
    return (best[1], best[0]) if best[0] >= 0.84 else None


def _after_name(head: str, t: Test) -> str:
    """What follows the test name inside the same OCR cell ("HbA1c 9.8 %" → "9.8 %")."""
    low = head.lower()
    for syn in sorted(t.synonyms, key=len, reverse=True):
        i = low.find(syn)
        if i >= 0:
            return head[i + len(syn):].strip(" :-")
    m = re.search(r"\d", head)
    return head[m.start():] if m else ""


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _ref(text: str) -> tuple[float | None, float | None, str] | None:
    m = RANGE_RE.search(text)
    if not m:
        return None
    if m.group(1):
        return _num(m.group(1)), _num(m.group(2)), m.group(0)
    op, v = m.group(3), _num(m.group(4))
    return (None, v, m.group(0)) if op.startswith(("<", "≤")) else (v, None, m.group(0))


def _scale(t: Test, value: float, unit: str) -> float:
    """Counts printed in thousands or lakhs become per-µL."""
    u = unit.lower().replace(" ", "")
    if t.key in ("platelets", "wbc"):
        if "lakh" in u:
            return value * 100000
        if re.search(r"10\^?3", u) or (value < 1000 and t.key == "platelets") or (value < 100 and t.key == "wbc"):
            return value * 1000
    return value


def _rows(lines: list[Line]) -> list[list[Line]]:
    if not lines:
        return []
    hs = sorted(x.box[3] for x in lines)
    tol = max(4.0, hs[len(hs) // 2] * 0.6)
    rows: list[list[Line]] = []
    for ln in sorted(lines, key=lambda x: (x.page, x.yc)):
        if rows and rows[-1][0].page == ln.page and abs(ln.yc - sum(x.yc for x in rows[-1]) / len(rows[-1])) <= tol:
            rows[-1].append(ln)
        else:
            rows.append([ln])
    return [sorted(r, key=lambda x: x.box[0]) for r in rows]


def parse_labs(res: OcrResult, sex: str | None = None, pregnant: bool = False) -> list[dict]:
    out = []
    W, H = res.page_size
    for row in _rows(res.lines):
        head = row[0].text
        m = match_test(head)
        if not m:
            continue
        t, score = m
        # Text after the test name: the rest of the first cell plus every cell to its right.
        tail_cells = [x.text for x in row[1:]]
        first_rest = _after_name(head, t)
        ref_cell = next((c for c in reversed(tail_cells) if RANGE_RE.search(c)), None) if len(tail_cells) > 1 else None
        value_text = " ".join([first_rest] + [c for c in tail_cells if c is not ref_cell]).strip()
        conf = min(x.conf for x in row)
        x0 = min(x.box[0] for x in row)
        y0 = min(x.box[1] for x in row)
        x1 = max(x.box[0] + x.box[2] for x in row)
        y1 = max(x.box[1] + x.box[3] for x in row)
        item = {
            "test_key": t.key, "test": t.name, "printed_name": head, "loinc": t.loinc,
            "value": None, "unit": t.unit, "reference": None, "status": "normal", "needs_check": False, "checks": [],
            "ocr_confidence": round(conf, 3), "bbox": [x0 / W, y0 / H, (x1 - x0) / W, (y1 - y0) / H], "page": row[0].page,
            "crop_text": " ".join(x.text for x in row),
        }
        if score < 1.0:
            item["checks"].append(f'Test name read as "{head}" — matched to {t.name} ({score:.0%} similar)')
            item["needs_check"] = True
        if conf < CONF_FLOOR:
            item["checks"].append("Hard to read — check the value against the crop")
            item["needs_check"] = True

        if t.kind == "bp":
            bm = BP_RE.search(value_text)
            if not bm:
                continue
            s, d = int(bm.group(1)), int(bm.group(2))
            item["value"] = f"{s}/{d}"
            item["values"] = {"systolic": s, "diastolic": d}
            item["reference"] = "< 140/90"
            item["status"] = "abnormal" if s >= 140 or d >= 90 else "normal"
            if not (60 <= s <= 260 and 30 <= d <= 160 and s > d):
                item["needs_check"] = True
                item["checks"].append("Implausible blood pressure — possible misread")
        elif t.kind == "dipstick":
            dm = DIPSTICK_RE.search(value_text)
            if not dm:
                continue
            v = dm.group(1).replace(" ", "").lower()
            plus = v.count("+") if v.startswith("+") else (int(v[0]) if v[0].isdigit() else 0)
            item["value"] = v
            item["value_num"] = plus
            item["reference"] = "Nil"
            item["status"] = "abnormal" if plus >= 1 else "borderline" if v == "trace" else "normal"
        elif t.kind == "qualitative":
            qm = QUAL_RE.search(value_text)
            if not qm:
                continue
            v = qm.group(1).lower()
            item["value"] = v
            item["reference"] = "Negative"
            item["status"] = "normal" if v in ("negative", "non reactive", "non-reactive", "nonreactive", "not detected") else "abnormal"
        else:
            nm = NUM_RE.search(value_text)
            if not nm:
                continue
            um = UNIT_RE.search(value_text[nm.end(): nm.end() + 25]) or UNIT_RE.search(value_text)
            unit = um.group(1) if um else ""
            raw = _num(nm.group(1))
            val = _scale(t, raw, unit)
            item["value"] = nm.group(1)
            item["value_num"] = val
            item["unit"] = unit.strip() or t.unit
            rng = _ref(ref_cell or value_text[nm.end():]) if (ref_cell or RANGE_RE.search(value_text[nm.end():])) else None
            if rng:
                lo, hi, printed = rng
                item["reference"] = ref_cell.strip() if ref_cell else printed
                if t.key in ("platelets", "wbc"):
                    lo = _scale(t, lo, ref_cell or "") if lo is not None else None
                    hi = _scale(t, hi, ref_cell or "") if hi is not None else None
            else:
                lo, hi = _default_ref(t, sex, pregnant)
                if lo is not None or hi is not None:
                    item["reference"] = f"{lo:g}–{hi:g} (typical adult range; lab ranges vary)" if lo and hi and hi < 999 else f"> {lo:g} (typical)" if lo else f"< {hi:g} (typical)"
                    item["checks"].append("No reference range printed — compared with a typical adult range")
            if not (t.plausible[0] <= val <= t.plausible[1]):
                item["needs_check"] = True
                item["status"] = "borderline"
                item["checks"].append(f"{raw:g} is outside the possible range for {t.name} — likely a misread")
            elif lo is not None and val < lo or hi is not None and val > hi:
                out_by = (lo - val) / lo if lo is not None and val < lo and lo else (val - hi) / hi if hi else 0
                item["status"] = "abnormal" if out_by > 0.1 else "borderline"
        out.append(item)
    return out


def _default_ref(t: Test, sex: str | None, pregnant: bool) -> tuple[float | None, float | None]:
    if t.key == "haemoglobin":  # WHO anaemia cut-offs for the lower bound
        return (11.0 if pregnant else 13.0 if sex == "M" else 12.0), 17.5
    if t.ref is None:
        return None, None
    lo, hi = t.ref
    return (lo or None), (hi if hi < 999 else None)


# ---------------------------------------------------------------- whole-document checks

def report_meta(res: OcrResult) -> dict:
    meta: dict = {}
    for ln in res.lines:
        low = ln.text.lower()
        if "date" in low or not meta.get("date"):
            m = DATE_RE.search(ln.text)
            if m:
                d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                y = y + 2000 if y < 100 else y
                try:
                    meta["date"] = date(y, mth, d).isoformat()
                except ValueError:
                    pass
        pm = re.search(r"(?:patient|name|pt\.?)\s*(?:name)?\s*[:\-]\s*([A-Za-z][A-Za-z .]{1,40}?)(?=\s{2,}|\s*(?:age|sex|date|uhid|$))", ln.text, re.I)
        if pm and "patient_name" not in meta:
            meta["patient_name"] = pm.group(1).strip()
    return meta


def document_checks(meta: dict, patient_name: str | None, today: date | None = None) -> list[str]:
    today = today or datetime.now(timezone.utc).date()
    warns = []
    if meta.get("date"):
        age = (today - date.fromisoformat(meta["date"])).days
        if age > STALE_DAYS:
            warns.append(f"Report is {age} days old (dated {meta['date']}) — values may not reflect today")
        elif age < -1:
            warns.append(f"Report date {meta['date']} is in the future — check the date")
    else:
        warns.append("No report date found — confirm when the test was done")
    if meta.get("patient_name") and patient_name:
        a, b = _squash(meta["patient_name"]), _squash(patient_name)
        if a and b and difflib.SequenceMatcher(None, a, b).ratio() < 0.7 and a not in b and b not in a:
            warns.append(f'Name on report ("{meta["patient_name"]}") does not match the patient record — confirm it is the right person\'s report')
    return warns


def extract_document(data: bytes, content_type: str, *, patient_name: str | None = None, sex: str | None = None, pregnant: bool = False) -> dict:
    res = read_document(data, content_type)
    rows = parse_labs(res, sex, pregnant) if res.lines else []
    meta = report_meta(res)
    warnings = list(res.quality.get("issues", []))
    if res.error:
        warnings.append(res.error)
    W, H = res.page_size
    text = [{"text": x.text, "conf": round(x.conf, 3), "bbox": [x.box[0] / W, x.box[1] / H, x.box[2] / W, x.box[3] / H], "page": x.page} for x in res.lines[:400]]
    from .images import doc_type, medicines

    kind = doc_type(text, len(rows)) if res.lines else {"type": "non_document", "label": "Not read", "why": res.error or "no text found"}
    if res.lines and kind["type"] != "medicine_strip":  # a strip has mfg/expiry dates and no patient name
        warnings += document_checks(meta, patient_name)
    if res.lines and not rows and kind["type"] not in ("medicine_strip", "prescription"):
        warnings.append("No recognised lab values — the reviewer should read the document directly")
    meds = medicines(text) if kind["type"] in ("prescription", "medicine_strip") else []
    if kind["type"] in ("prescription", "medicine_strip") and rows:
        rows = []  # numbers on a strip or prescription are strengths, not lab values
    return {
        "engine": res.engine,
        "doc_type": kind,
        "medicines": meds,
        "quality": res.quality,
        "rows": rows,
        "meta": meta,
        "warnings": warnings,
        "text": text,
        "at": datetime.now(timezone.utc).isoformat(),
    }


def lab_values(extractions: list[dict]) -> dict[str, float]:
    """Numeric values the rules engine may use (e.g. potassium for the ATP outside-evaluation rule).
    Impossible values (misreads) are excluded. Low-confidence but possible values are kept: rules
    only ever raise urgency, so a doubtful high potassium over-triages rather than being missed."""
    out: dict[str, float] = {}
    for ex in extractions:
        for r in ex.get("rows", []):
            test = next((t for t in TESTS if t.key == r["test_key"]), None)
            v = r.get("value_num")
            if v is not None and test and test.plausible[0] <= v <= test.plausible[1]:
                out[r["test_key"]] = v
    return out
