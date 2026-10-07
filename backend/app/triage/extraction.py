"""Medical-document extraction: OCR → lines with boxes → lab rows with checks.

Engines, chosen by file type and named truthfully in every output:
* Photos (JPEG/PNG/WebP): RapidOCR — PaddleOCR PP-OCR detection/recognition models run on ONNX
  Runtime (Apache-2.0), offline, CPU. An image-quality gate runs first (blur, darkness, size).
* PDFs with a text layer: the embedded text (pypdfium2), no OCR needed. Scanned PDFs: each page is
  rasterised (pypdfium2) and sent through the same OCR.
* SVG (the synthetic training slips): the SVG's own text elements.
* Second engine (B9), for photographed and scanned reports: docTR's DBNet + CRNN models through OnnxTR, also ONNX
  Runtime, offline. It reads the same image at the same time; each engine's text goes through the same parser and
  `cross_check` compares them test by test. A different value or range is shown to the reviewer with both readings.

Lab parsing is deterministic: a dictionary of common Indian lab tests with synonyms and OCR
confusions, the value / unit / printed reference range read from the same row, a plausibility
range per test (an impossible number means a misread, not a diagnosis) and a confidence floor.
Anything doubtful is marked `needs_check` for the reviewer; nothing is silently corrected.

B2 number checks: the lab's own High/Low mark against the value and range, a unit that belongs to the test (SI units
converted for the rules, shown as printed), a printed range that fits the test, and the report's numbers against each
other (`consistency`: WBC differential = 100 %, absolute = % × WBC, globulin = protein − albumin, MCHC = Hb ÷ PCV, …).
"""

import difflib
import io
import re
import threading
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from ..config import get_settings

CONF_FLOOR = 0.85  # OCR confidence below this is shown as "needs checking"
STALE_DAYS = 90


@dataclass
class Line:
    text: str
    box: list[float]  # x, y, w, h in page pixels
    conf: float
    page: int = 0
    slope: float = 0.0  # tan of the text line's tilt (top edge of the OCR box); 0 for text layers

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
    second: "OcrResult | None" = None  # the second engine's reading of the same image (B9)


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
    if not get_settings().ocr_enabled:  # H3: the stub profile reads no documents
        return False
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except ImportError:
        return False


SECOND_DET, SECOND_RECO = "db_mobilenet_v3_large", "crnn_mobilenet_v3_large"
SECOND_ENGINE = "docTR DBNet + CRNN models (OnnxTR, ONNX Runtime, offline)"
_ocr2 = None
_ocr2_lock = threading.Lock()


def second_available() -> bool:
    try:
        import onnxtr  # noqa: F401

        return True
    except ImportError:
        return False


def _onnxtr():
    global _ocr2
    with _ocr2_lock:
        if _ocr2 is None:
            from onnxtr.models import ocr_predictor  # optional dependency

            _ocr2 = ocr_predictor(det_arch=SECOND_DET, reco_arch=SECOND_RECO, assume_straight_pages=False, detect_orientation=False, straighten_pages=False)
        return _ocr2


def _ocr2_array(arr, page: int = 0) -> list[Line]:
    """docTR's lines in RapidOCR's form (pixel box, lowest word confidence, tilt from the first to the last word)."""
    import cv2
    import numpy as np

    h, w = arr.shape[:2]
    doc = _onnxtr()([cv2.cvtColor(arr, cv2.COLOR_BGR2RGB) if arr.ndim == 3 else cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)])
    out = []
    for block in doc.pages[0].blocks:
        for ln in block.lines:
            if not ln.words:
                continue
            pts = np.asarray(ln.geometry, dtype=float).reshape(-1, 2) * [w, h]
            centre = [np.asarray(wd.geometry, dtype=float).reshape(-1, 2).mean(0) * [w, h] for wd in (ln.words[0], ln.words[-1])]
            dx = centre[1][0] - centre[0][0]
            slope = float((centre[1][1] - centre[0][1]) / dx) if dx > 2 * abs(centre[1][1] - centre[0][1]) and dx > 0 else 0.0
            x0, y0 = pts.min(0)
            x1, y1 = pts.max(0)
            out.append(Line(_clean(" ".join(wd.value for wd in ln.words)), [float(x0), float(y0), float(x1 - x0), float(y1 - y0)],
                            float(min(wd.confidence for wd in ln.words)), page, slope))
    return out


def _both(arr, page: int, second: bool) -> tuple[list[Line], list[Line] | None]:
    """The first engine's lines and, when asked and installed, the second's: both read the image at once."""
    if not (second and second_available()):
        return _ocr_array(arr, page), None
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(1) as pool:
        other = pool.submit(_ocr2_array, arr, page)
        lines = _ocr_array(arr, page)
        try:
            return lines, other.result()
        except Exception:  # the second engine failing never stops the first engine's reading
            return lines, None


# Retake thresholds, set on the synthetic report photos (docs/EVALUATION.md, OCR): every clean scan, photocopy,
# phone photo and thermal slip passed; most blurred, dim photos (the ones OCR misread) were asked to retake.
SHARP_MIN = 32  # variance of the Laplacian after a 3×3 median filter, measured at QUALITY_SIDE
CONTRAST_MIN = 60  # ink vs paper: mean of the light minus the dark Otsu class
QUALITY_SIDE = 1600


def image_quality(img) -> dict:
    """Blur, exposure, contrast and size. `img` is a greyscale numpy array.

    Measured at one scale (longer side QUALITY_SIDE), so a 12-megapixel phone photo and a small scan are judged
    alike. Blur is the Laplacian variance after a median filter: sensor noise otherwise reads as sharpness, which let
    blurred phone photos through. Contrast is ink against paper (Otsu classes), not the spread over the whole page: a
    clean white page has little spread and was asked to retake."""
    import cv2

    issues = []
    h, w = img.shape[:2]
    if min(h, w) < 500:
        issues.append(f"Low resolution ({w}×{h}) — retake closer")
    s = min(1.0, QUALITY_SIDE / max(h, w))
    small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    mean = float(small.mean())
    thr, _ = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark, light = small[small <= thr], small[small > thr]
    contrast = float(light.mean() - dark.mean()) if dark.size and light.size else 0.0
    if mean < 70:
        issues.append("Too dark — retake in better light")
    if contrast < CONTRAST_MIN:
        issues.append("Low contrast / glare — retake without flash, flat to the camera")
    sharp = float(cv2.Laplacian(cv2.medianBlur(small, 3), cv2.CV_64F).var())
    if sharp < SHARP_MIN:
        issues.append("Blurry — hold the phone steady and retake")
    return {"ok": not issues, "issues": issues, "sharpness": round(sharp, 1), "brightness": round(mean, 1), "contrast": round(contrast, 1), "size": [w, h]}


def _ocr_array(arr, page: int = 0) -> list[Line]:
    res, _ = _rapidocr()(arr)
    out = []
    for box, text, conf in res or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        (x0, y0), (x1, y1) = box[0], box[1]
        slope = (y1 - y0) / (x1 - x0) if x1 - x0 > 2 * abs(y1 - y0) and x1 > x0 else 0.0
        out.append(Line(_clean(text), [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)], float(conf), page, slope))
    return out


def _clean(text: str) -> str:
    """OCR text in plain forms: the PaddleOCR models were trained mostly on Chinese print and write full-width
    brackets and colons ("（<200）"), which the range and name patterns would not see. NFKC also turns µ into the Greek
    μ; it is put back so units still read as µ."""
    return unicodedata.normalize("NFKC", text).replace("μ", "µ").strip()


def ocr_image(data: bytes, second: bool = False) -> OcrResult:
    import cv2
    import numpy as np

    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return OcrResult("none", error="Could not read the image file")
    grey = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    q = image_quality(grey)
    if not ocr_available():
        return OcrResult("none", quality=q, error="OCR engine not installed on this server — review the image directly")
    lines, lines2 = _both(arr, 0, second)
    if not lines and not lines2:
        # Large print blurred past reading still scores as sharp enough: the reader finding nothing is the real sign.
        q["issues"].append("No text could be read — hold the phone steady, closer, and retake")
        q["ok"] = False
    elif lines and sum(x.conf for x in lines) / len(lines) < 0.75:
        q["issues"].append("Text hard to read — low recognition confidence")
        q["ok"] = False
    size = (arr.shape[1], arr.shape[0])
    return OcrResult("RapidOCR (PaddleOCR PP-OCR models, ONNX Runtime, offline)", lines, size, q,
                     second=OcrResult(SECOND_ENGINE, lines2, size) if lines2 is not None else None)


def read_pdf(data: bytes, second: bool = False) -> OcrResult:
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

    lines, lines2 = [], []
    for i, page in enumerate(pdf):
        if i >= 3:
            break
        img = page.render(scale=2).to_pil().convert("RGB")
        size = img.size
        a, b = _both(np.ascontiguousarray(np.array(img)[:, :, ::-1]), i, second)
        lines += a
        lines2 = lines2 + b if b is not None and lines2 is not None else None
    return OcrResult("RapidOCR on rasterised scanned PDF (PaddleOCR PP-OCR models, ONNX Runtime)", lines, size,
                     second=OcrResult(SECOND_ENGINE, lines2, size) if lines2 is not None and second else None)


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


def read_document(data: bytes, content_type: str, second: bool = False) -> OcrResult:
    try:
        if content_type == "image/svg+xml":
            return read_svg(data)
        if content_type == "application/pdf":
            return read_pdf(data, second)
        if content_type.startswith("image/"):
            return ocr_image(data, second)
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
    # B2: tests that other printed values must add up to. Several also stop a misread: before they were listed,
    # "VLDL" was taken for LDL, "Cholesterol/HDL Ratio" for total cholesterol, "Blood Urea Nitrogen" for urea (2.14× off),
    # "Serum Bilirubin (Direct)" for total bilirubin and "RBC Count" for the WBC count.
    Test("bun", "Blood urea nitrogen", ("blood urea nitrogen", "serum urea nitrogen", "urea nitrogen", "bun"), "mg/dL", (1, 200), (7, 20), "3094-0"),
    Test("rbc", "RBC count", ("total rbc count", "rbc count", "red blood cell count", "red cell count", "red blood cells", "total rbc", "rbc"), "million/µL", (0.5, 10), (4.0, 6.0), "789-8"),
    Test("mcv", "MCV", ("mean corpuscular volume", "mean cell volume", "mcv"), "fL", (40, 160), (80, 100), "787-2"),
    Test("mch", "MCH", ("mean corpuscular haemoglobin", "mean corpuscular hemoglobin", "mean cell haemoglobin", "mean cell hemoglobin", "mch"), "pg", (10, 60), (27, 32), "785-6"),
    Test("mchc", "MCHC", ("mean corpuscular haemoglobin concentration", "mean corpuscular hemoglobin concentration", "mean cell haemoglobin concentration",
                          "mean cell hemoglobin concentration", "mchc"), "g/dL", (15, 50), (32, 36), "786-4"),
    Test("neutrophils", "Neutrophils", ("neutrophils", "neutrophil", "polymorphs", "polymorphonuclear", "segmented neutrophils", "neut", "pmn"), "%", (0, 100), (40, 75), "770-8"),
    Test("lymphocytes", "Lymphocytes", ("lymphocytes", "lymphocyte", "lymphs", "lymph"), "%", (0, 100), (20, 45), "736-9"),
    Test("monocytes", "Monocytes", ("monocytes", "monocyte", "mono"), "%", (0, 100), (2, 10), "5905-5"),
    Test("eosinophils", "Eosinophils", ("eosinophils", "eosinophil", "eos"), "%", (0, 100), (1, 6), "713-8"),
    Test("basophils", "Basophils", ("basophils", "basophil", "baso"), "%", (0, 100), (0, 2), "706-2"),
    *(Test(f"abs_{c}", f"Absolute {c[:-1]} count", tuple(s.format(c[:-1]) for s in (
        "absolute {} count", "absolute {}s", "absolute {}", "abs {} count", "abs {}s", "abs {}", "{}s absolute", "{} absolute", "{}s abs", "{} abs", "{}s abs count"))
        + (("aec",) if c == "eosinophils" else ()),
        "/µL", (0, 150000), ref, loinc)
      for c, ref, loinc in (("neutrophils", (2000, 7000), "751-8"), ("lymphocytes", (1000, 3000), "731-0"), ("monocytes", (200, 1000), "742-7"),
                            ("eosinophils", (20, 500), "711-2"), ("basophils", (0, 100), "704-7"))),
    Test("total_protein", "Total protein", ("serum total protein", "total proteins", "total protein", "protein total", "proteins total", "serum protein", "s total protein", "s protein"),
         "g/dL", (1, 15), (6.0, 8.3), "2885-2"),
    Test("albumin", "Serum albumin", ("serum albumin", "s albumin", "albumin serum", "albumin"), "g/dL", (0.5, 8), (3.5, 5.2), "1751-7"),
    Test("globulin", "Globulin", ("serum globulin", "s globulin", "globulin"), "g/dL", (0.5, 10), (2.0, 3.5), "10834-0"),
    Test("ag_ratio", "A/G ratio", ("albumin globulin ratio", "albumin/globulin ratio", "a/g ratio", "a:g ratio", "ag ratio", "a g ratio"), "", (0.1, 5), (1.0, 2.2), "1759-0"),
    Test("bilirubin_direct", "Direct bilirubin", ("serum bilirubin direct", "s bilirubin direct", "bilirubin direct", "direct bilirubin", "conjugated bilirubin",
                                                  "bilirubin conjugated", "bilirubin d"), "mg/dL", (0, 30), (0, 0.3), "1968-7"),
    Test("bilirubin_indirect", "Indirect bilirubin", ("serum bilirubin indirect", "s bilirubin indirect", "bilirubin indirect", "indirect bilirubin",
                                                      "unconjugated bilirubin", "bilirubin unconjugated"), "mg/dL", (0, 30), (0.1, 1.0), "1971-1"),
    Test("vldl", "VLDL cholesterol", ("very low density lipoprotein", "vldl cholesterol", "vldl"), "mg/dL", (1, 400), (2, 30), "13458-5"),
    Test("non_hdl", "Non-HDL cholesterol", ("non hdl cholesterol", "non hdl"), "mg/dL", (20, 600), (0, 130), "43396-1"),
    Test("tc_hdl_ratio", "Total cholesterol / HDL ratio", ("total cholesterol/hdl ratio", "cholesterol/hdl ratio", "chol/hdl ratio", "tc/hdl ratio", "total cholesterol/hdl",
                                                          "cholesterol/hdl", "chol/hdl", "tc/hdl"), "", (0.5, 20), (0, 5.0), "9830-1"),
    Test("ldl_hdl_ratio", "LDL / HDL ratio", ("ldl/hdl ratio", "ldl/hdl"), "", (0.2, 15), (0, 3.5), "11054-4"),
]
TEST = {t.key: t for t in TESTS}
DIFF = ("neutrophils", "lymphocytes", "monocytes", "eosinophils", "basophils")
COUNTS = ("wbc", "platelets", *(f"abs_{c}" for c in DIFF))

_POW = r"[\^~*]"  # OCR reads the caret of "x10^3/µL" as "~"; some labs print "10*3" or "10³"
UNITS = [r"mg\s*/\s*dl", r"mg\s*%", r"gm?\s*/\s*dl", r"gm?\s*%", r"mmo[l1]\s*/\s*mol", r"mmo[l1]\s*/\s*l", r"meq\s*/\s*l", r"[uµμ]mo[l1]\s*/\s*l", r"mg\s*/\s*l(?![a-z])",
         r"gm?\s*/\s*l(?![a-z])", r"u\s*/\s*l", r"iu\s*/\s*l", r"µiu\s*/\s*ml", r"uiu\s*/\s*ml", r"miu\s*/\s*l",
         r"ml\s*/\s*min(\s*/\s*1\.73\s*m[2²])?", r"mill?(ion)?s?\s*/\s*(cumm|[uµ]l|mm3)", rf"x?\s*10\s*{_POW}?\s*[6⁶]\s*/\s*[uµμ]l", rf"x?\s*10\s*{_POW}?\s*(12|¹²)\s*/\s*l",
         r"/\s*[uµ]l", r"cells\s*/\s*cumm", r"/\s*cumm", r"cells\s*/\s*[uµ]l", r"lakhs?(\s*/\s*cumm)?", rf"x?\s*10\s*{_POW}?\s*[39³⁹]\s*/\s*[uµμ]?l", r"mmhg", r"%", r"cm", r"fl", r"pg"]
UNIT_RE = re.compile("(" + "|".join(UNITS) + ")", re.I)
NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)(?![\d])")
BP_RE = re.compile(r"(\d{2,3})\s*/\s*(\d{2,3})")
_RNUM = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?"  # 1,50,000 (lakh commas) as well as 4,000 and 3.5
RANGE_RE = re.compile(rf"({_RNUM})\s*(?:-|–|—|to)\s*({_RNUM})|([<>≤≥]=?)\s*({_RNUM})")
DIPSTICK_RE = re.compile(r"(?<![\w+])(nil|negative|trace|[1-4]\s*\+|\+{1,4})(?![\w+])", re.I)
QUAL_RE = re.compile(r"\b(positive|negative|reactive|non[- ]?reactive|detected|not detected|pf|pv)\b", re.I)
DATE_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})")


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9%+]", "", s.lower().replace("µ", "u"))


_SYN = sorted(((_squash(s), t) for t in TESTS for s in t.synonyms), key=lambda x: -len(x[0]))


_LOOKALIKE = str.maketrans("1i0", "llo")  # OCR reads NS1 as "Nsl" or "Nsi", O as 0
_DIGIT_LOOKALIKE = str.maketrans("iIl|oO", "111100")  # and 175 as "i75"


def match_test(text: str) -> tuple[Test, float] | None:
    """Longest synonym that the line starts with; otherwise a close fuzzy match (OCR slips)."""
    sq = _squash(text)
    if not sq:
        return None
    for syn, t in _SYN:
        if sq.startswith(syn) and (len(syn) >= 3 or sq == syn):
            return t, 1.0
        # A short name ("Hb") alone in its cell, or straight before its number as handwritten notes put it ("Hb 9.4")
        if len(syn) < 3 and re.match(rf"\s*{re.escape(syn)}\s*[:=\-]?\s*\d", text, re.I):
            return t, 1.0
    alike = sq.translate(_LOOKALIKE)
    for syn, t in _SYN:
        if len(syn) >= 4 and alike.startswith(syn.translate(_LOOKALIKE)):
            return t, 1.0
    # A small printer cuts long names ("Thyroid Stimulating Ho7.17"): the letters before the value, if at least ten
    # and the start of only one test's names, are that test.
    head = re.match(r"[a-z%+]*", alike).group(0)
    if len(head) >= 10:
        hits = {t.key: t for syn, t in _SYN if syn.translate(_LOOKALIKE).startswith(head)}
        if len(hits) == 1:
            return next(iter(hits.values())), 1.0
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


def _unorm(unit: str) -> str:
    """"x10~3/µL", "10*3/uL", "10³/µL" → "10^3/ul"."""
    u = re.sub(r"\s", "", unit.lower()).replace("µ", "u").replace("μ", "u").replace("gm", "g")
    u = re.sub(r"10[~*]", "10^", u).replace("mo1/", "mol/")  # a thermal slip's "µmo1/L"
    return u.replace("³", "^3").replace("⁶", "^6").replace("⁹", "^9").replace("¹²", "^12")


def _mend_unit(unit: str) -> str:
    """The unit as the lab printed it, with the OCR slips that only have one reading undone: "X10~3/�L" → "x10^3/µL",
    "mmo1/L" → "mmol/L"."""
    u = re.sub(r"^[Xx×]\s*(?=10)", "x", unit)
    u = re.sub(r"10\s*[~*]\s*(?=\d)", "10^", u).replace("�", "µ")
    return re.sub(r"(?<=[mµu]mo)1(?=/)", "l", u)


def _scale(t: Test, value: float, unit: str) -> float:
    """Counts printed in thousands or lakhs become per-µL."""
    u = _unorm(unit)
    if t.key in ("platelets", "wbc"):
        if "lakh" in u:
            return value * 100000
        if re.search(r"10\^?3", u) or (value < 1000 and t.key == "platelets") or (value < 100 and t.key == "wbc"):
            return value * 1000
    if t.key.startswith("abs_") and (re.search(r"10\^?[39]", u) or (not u and value < 50 and value != int(value))):
        return value * 1000  # "4.52" ×10³/µL; "40" cells/cumm stays 40
    return value


# ---------------------------------------------------------------- B2: units, flags, ranges

_UNIT_KIND = [("mg/dl", r"mg/dl|mg%"), ("g/dl", r"g/dl|g%"), ("mmol/mol", r"mmol/mol"), ("mmol/l", r"mmol/l|meq/l"), ("umol/l", r"umol/l"),
              ("mg/l", r"mg/l"), ("g/l", r"g/l"), ("u/l", r"i?u/l"), ("uiu/ml", r"uiu/ml|miu/l"), ("ml/min", r"ml/min.*"),
              ("million", r"mill.*|.*10\^?(6|12)/.*"), ("count", r".*(/ul|/cumm|lakhs?.*|10\^?[39]/u?l)"), ("%", "%"), ("fl", "fl"), ("pg", "pg")]


def _unit_kind(unit: str) -> str | None:
    u = _unorm(unit).replace("x", "")
    return next((k for k, pat in _UNIT_KIND if re.fullmatch(pat, u)), None)


_MGDL = ("glucose_fasting", "glucose_pp", "glucose_random", "creatinine", "urea", "bun", "cholesterol", "ldl", "hdl", "triglycerides", "vldl", "non_hdl",
         "bilirubin", "bilirubin_direct", "bilirubin_indirect")
UNIT_OK: dict[str, set[str]] = {
    **{k: {"mg/dl"} for k in _MGDL}, **{k: {"count"} for k in COUNTS}, **{k: {"%"} for k in DIFF},
    "hba1c": {"%"}, "haemoglobin": {"g/dl", "%"}, "mchc": {"g/dl", "%"}, "total_protein": {"g/dl"}, "albumin": {"g/dl"}, "globulin": {"g/dl"},
    "pcv": {"%"}, "rbc": {"million", "count"}, "mcv": {"fl"}, "mch": {"pg"}, "potassium": {"mmol/l"}, "sodium": {"mmol/l"},
    "alt": {"u/l"}, "ast": {"u/l"}, "tsh": {"uiu/ml"}, "egfr": {"ml/min"}, "ag_ratio": set(), "tc_hdl_ratio": set(), "ldl_hdl_ratio": set(),
}


def _times(f: float):
    return lambda v: v * f


# SI units some labs print, to the unit the rules use. A glucose of 17 mmol/L read as 17 mg/dL would look like
# hypoglycaemia; converted, it is 306 mg/dL.
CONVERT = {
    **dict.fromkeys(("glucose_fasting", "glucose_pp", "glucose_random"), {"mmol/l": _times(18.016)}),
    **dict.fromkeys(("cholesterol", "ldl", "hdl", "vldl", "non_hdl"), {"mmol/l": _times(38.67)}),
    "triglycerides": {"mmol/l": _times(88.57)}, "creatinine": {"umol/l": _times(1 / 88.42)},
    "urea": {"mmol/l": _times(6.006)}, "bun": {"mmol/l": _times(2.801)},
    **dict.fromkeys(("bilirubin", "bilirubin_direct", "bilirubin_indirect"), {"umol/l": _times(1 / 17.1)}),
    **dict.fromkeys(("haemoglobin", "total_protein", "albumin", "globulin", "mchc"), {"g/l": _times(0.1)}),
    "hba1c": {"mmol/mol": lambda v: v / 10.929 + 2.15},  # IFCC to NGSP
}

# The lab's own high/low mark beside a result: "310 H", "(L)", "HIGH", "↑". Units are removed before looking, so the
# L of "mmol/L" is not read as Low.
FLAG_RE = re.compile(r"(?<![A-Za-zµ/^\d.])[\[(*]?\s*(HIGH|LOW|High|Low|high|low|HH|LL|H|L|↑|↓)\s*[\])*]?(?![A-Za-z])|(?<=\d)(H|L)(?![A-Za-z])")


def _flag(after_value: str) -> str | None:
    s = UNIT_RE.sub(" ", after_value)
    rm = RANGE_RE.search(s)
    m = FLAG_RE.search(s[: rm.start()] if rm else s)
    if not m:
        return None
    f = m.group(1) or m.group(2)
    return "H" if f[0] in "Hh↑" else "L"


RANK = {"normal": 0, "borderline": 1, "abnormal": 2}


def _call(val: float, lo: float | None, hi: float | None) -> str:
    if lo is not None and val < lo or hi is not None and val > hi:
        out_by = (lo - val) / lo if lo is not None and val < lo and lo else (val - hi) / hi if hi else 0
        return "abnormal" if out_by > 0.1 else "borderline"
    return "normal"


def _range_fits(t: Test, lo: float | None, hi: float | None) -> bool:
    """A printed range more than four times off the test's usual range is a range in another unit (glucose 3.9 – 5.5
    is mmol/L) or a misread one ("< 2000" for "< 200"); either way the high/low call against it cannot be trusted."""
    if not t.ref:
        return True
    tl, th = t.ref
    th = th if th < 999 else None

    def off(a, b):
        return bool(a and b and a > 0 and b > 0 and max(a / b, b / a) > 4)

    return not (off(hi, th) or off(lo, tl))


def _local_slopes(lines: list[Line]) -> list[float]:
    """The tilt around each line (a phone photo is rarely straight, and perspective makes the top and bottom of the
    page tilt differently): the median slope of the long text lines near it, vertically."""
    long_ = [x for x in lines if x.box[2] > 3 * x.box[3]]
    span = 4 * (sorted(max(4.0, x.box[3] - abs(x.slope) * x.box[2]) for x in lines)[len(lines) // 2] if lines else 1)
    out = []
    for ln in lines:
        s = sorted(x.slope for x in long_ if x.page == ln.page and abs(x.yc - ln.yc) <= span) or sorted(x.slope for x in long_ if x.page == ln.page)
        out.append(s[len(s) // 2] if s else 0.0)
    return out


def _rows(lines: list[Line]) -> list[list[Line]]:
    """Table rows: lines at the same height once the page's tilt is taken out. On a tilted photo the value cell sits
    lower (or higher) than its test name by slope × distance, enough to pair a name with the next row's value."""
    if not lines:
        return []
    # the text's own height: an upright box around a tilted line is taller by slope × width
    hs = sorted(max(4.0, x.box[3] - abs(x.slope) * x.box[2]) for x in lines)
    tol = max(4.0, hs[len(hs) // 2] * 0.6)
    slope = dict(zip(map(id, lines), _local_slopes(lines)))

    def y(ln: Line) -> float:
        return ln.yc - slope[id(ln)] * (ln.box[0] + ln.box[2] / 2)

    rows: list[list[Line]] = []
    for ln in sorted(lines, key=lambda x: (x.page, y(x))):
        if rows and rows[-1][0].page == ln.page and abs(y(ln) - sum(y(x) for x in rows[-1]) / len(rows[-1])) <= tol:
            rows[-1].append(ln)
        else:
            rows.append([ln])
    rows = [sorted(r, key=lambda x: x.box[0]) for r in rows]
    return _attach_ranges(rows, y, tol / 0.6)


def _range_only(text: str) -> bool:
    core = _mend_range(text).strip("()[] ")
    m = RANGE_RE.search(core)
    return bool(m) and len(m.group(0)) >= 0.7 * len(core)


def _attach_ranges(rows: list[list[Line]], y, h: float) -> list[list[Line]]:
    """A line holding only a reference range belongs to the test at or above it, never below: small printers put
    "(70 - 110)" under the value, exactly between its own test and the next, where height alone cannot tell."""
    tests = [r for r in rows if match_test(r[0].text)]
    moved: list[tuple[Line, list[Line]]] = []
    for r in rows:
        for ln in r[1:] if r in tests else r:
            if not _range_only(ln.text) or (r in tests and abs(y(ln) - y(r[0])) <= 0.5 * h):
                continue
            above = [t for t in tests if t[0].page == ln.page and y(t[0]) <= y(ln) + 0.35 * h and y(ln) - y(t[0]) <= 2.5 * h]
            if above:
                moved.append((ln, max(above, key=lambda t: y(t[0]))))
    for ln, to in moved:
        for r in rows:
            if ln in r:
                r.remove(ln)
        to.append(ln)
    return [sorted(r, key=lambda x: x.box[0]) for r in rows if r]


_LAKH = r"\d{1,2},\d{2},\d{3}"


def _mend_range(text: str) -> str:
    """A range whose dash OCR lost or read as a dot, where only one reading exists: two lakh-comma numbers run
    together ("1,50,0004,50,000"), or two decimals joined by a dot ("0.4.4.0"). "36.46" stays as read."""
    text = re.sub(rf"({_LAKH})(?={_LAKH}(?!\d))", r"\g<1>-", text)
    return re.sub(r"(?<![\d.])(\d+\.\d+)\.(\d+\.\d+)(?![\d.])", r"\g<1>-\g<2>", text)


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
        tail_cells = [_mend_range(x.text) for x in row[1:]]
        first_rest = _after_name(head, t)
        ref_cell = next((c for c in reversed(tail_cells) if RANGE_RE.search(c)), None) if len(tail_cells) > 1 else None
        value_text = " ".join([first_rest] + [c for c in tail_cells if c is not ref_cell]).strip()
        if re.search(r"/\s*h\.?p\.?f|\bhpf\b", value_text, re.I):
            continue  # urine microscopy ("RBC 2-4 /hpf"), not a blood count
        if t.key == "albumin" and DIPSTICK_RE.search(value_text):
            t = TEST["urine_albumin"]  # "Albumin: Nil" under URINE ROUTINE
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
            value_text = re.sub(r"(\d)[1Il|]akh", r"\1 lakh", value_text)  # "3.001akhs": the l of lakhs read as 1
            if not NUM_RE.search(value_text.split(" ")[0] if value_text else ""):
                lk = re.match(r"([iIl|oO]?\d[\d.,]*|\d[\d.,]*[oO][\d.,]*)(?=\s|$|[a-zA-Z/%µ])", value_text)
                if lk and re.search(r"\d.*\d", lk.group(1)):  # "i75": a digit read as a letter; read, and always shown
                    fixed = lk.group(1).translate(_DIGIT_LOOKALIKE)
                    item["checks"].append(f'Value read as "{lk.group(1)}" — taken as {fixed}; check the slip')
                    item["needs_check"] = True
                    value_text = fixed + value_text[lk.end():]
            nm = NUM_RE.search(value_text)
            if not nm:
                continue
            after = value_text[nm.end():]
            if re.match(r"[,.\-–][0-9]|[A-Za-z][0-9]", after) and not UNIT_RE.match(after):
                # "4-54" (the point read as a dash), "19,9e0" (a 0 read as e): only the start of the number was read
                item["needs_check"] = True
                item["checks"].append(f'Value read as "{nm.group(1) + re.match(r"[^ ]*", after).group(0)}" — taken as {nm.group(1)}; check the slip')
            um = UNIT_RE.search(value_text[nm.end(): nm.end() + 25]) or UNIT_RE.search(value_text)
            if not um and ref_cell and (rm := UNIT_RE.match(ref_cell.lstrip())) and RANGE_RE.search(ref_cell.lstrip()[rm.end():]):
                # "Platelets | 4.87 | lakhs/cumm 1.50 - 4.50": the unit column ran into the range cell; it is the value's unit too
                um, ref_cell = rm, ref_cell.lstrip()[rm.end():].strip()
            unit = _mend_unit(um.group(1).strip()) if um else ""
            raw = _num(nm.group(1))
            kind = _unit_kind(unit) if unit else None
            if t.key in DIFF and (kind == "count" or raw > 100):  # "Neutrophils 4,520 /cumm" is the absolute count
                t = TEST[f"abs_{t.key}"]
                item.update(test_key=t.key, test=t.name, loinc=t.loinc)
            conv = CONVERT.get(t.key, {}).get(kind)
            val = conv(raw) if conv else _scale(t, raw, unit)
            item["value"] = nm.group(1)
            item["value_num"] = val
            item["unit"] = unit or t.unit
            if conv:
                item["checks"].append(f"Printed in {unit}: {raw:g} {unit} is {val:.3g} {t.unit}, the unit the rules use")
            elif kind and t.key in UNIT_OK and kind not in UNIT_OK[t.key]:
                item["needs_check"] = True
                item["checks"].append(f'"{unit}" is not a unit used for {t.name} — check the unit and the value')
            if not unit and t.unit:
                item["checks"].append(f"No unit read — {t.unit} assumed; check the slip")
                if t.key in COUNTS:  # a count without its unit could be per µL, thousands or lakhs: a 100-fold difference
                    item["needs_check"] = True
            rng = _ref(ref_cell or value_text[nm.end():]) if (ref_cell or RANGE_RE.search(value_text[nm.end():])) else None
            if rng:
                lo, hi, printed = rng
                item["reference"] = ref_cell.strip() if ref_cell else printed
                ru = ref_cell if ref_cell and UNIT_RE.search(ref_cell) else unit
                if t.key in COUNTS:  # "1.50 - 4.50" beside "3.00 lakhs/cumm" is in lakhs too
                    lo = _scale(t, lo, ru) if lo is not None else None
                    hi = _scale(t, hi, ru) if hi is not None else None
                elif rconv := CONVERT.get(t.key, {}).get(_unit_kind(UNIT_RE.search(ru).group(1)) if ru and UNIT_RE.search(ru) else None):
                    lo = rconv(lo) if lo is not None else None
                    hi = rconv(hi) if hi is not None else None
            else:
                lo, hi = _default_ref(t, sex, pregnant)
                if lo is not None or hi is not None:
                    item["reference"] = f"{lo:g}–{hi:g} (typical adult range; lab ranges vary)" if lo and hi and hi < 999 else f"> {lo:g} (typical)" if lo else f"< {hi:g} (typical)"
                    item["checks"].append("No reference range printed — compared with a typical adult range")
            plausible = t.plausible[0] <= val <= t.plausible[1]
            item["range_printed"] = bool(rng)
            if rng and plausible and not _range_fits(t, lo, hi):
                item["range_printed"] = False
                item["needs_check"] = True
                item["checks"].append(f"The printed range {item['reference']} does not look like a {t.name} range in {t.unit} — the range or the unit may be "
                                      "misread; compared with a typical adult range instead")
                lo, hi = _default_ref(t, sex, pregnant)
            item["ref_range"] = [lo, hi]
            if not plausible:
                item["needs_check"] = True
                item["status"] = "borderline"
                item["checks"].append(f"{raw:g} is outside the possible range for {t.name} — likely a misread")
            else:
                item["status"] = call = _call(val, lo, hi)
                if flag := _flag(value_text[nm.end():]):
                    item["flag"] = flag
                    word = "High" if flag == "H" else "Low"
                    if call == "normal" or (flag == "H") != (hi is not None and val > hi):
                        # The lab's mark and the value disagree: one of the value, the range or the mark is misread.
                        # Until someone looks, the result counts as out of range (urgency errs high).
                        item["status"] = max(call, "borderline", key=RANK.get)
                        where = "inside" if call == "normal" else "above" if hi is not None and val > hi else "below"
                        if item["range_printed"]:
                            item["needs_check"] = True
                            item["checks"].append(f"The report marks this {word}, but {raw:g} is {where} the printed range {item['reference']} — "
                                                  "the value, the range or the mark is misread")
                        else:
                            item["checks"].append(f"The report marks this {word}; the typical range used here may differ from the lab's")
        # Confidence of the cell the value was read from, not the whole row: a faint bracket in the range column
        # flagged one correct value in five on phone photos (docs/EVALUATION.md, OCR).
        squashed = str(item["value"]).replace(" ", "").lower()
        cells = [x.conf for x in row if squashed and squashed in x.text.replace(" ", "").lower()]  # leftmost first
        item["ocr_confidence"] = round(cells[0] if cells else conf, 3)  # not the range cell "(135-145)" beside "135"
        if item["ocr_confidence"] < CONF_FLOOR:
            item["checks"].append("Hard to read — check the value against the crop")
            item["needs_check"] = True
        out.append(item)
    # A lab that marks its out-of-range results marks all of them: an unmarked one outside its printed range means the
    # value, the range or the mark was misread (or the mark was missed).
    if sum(1 for r in out if r.get("flag")) >= 2:
        for r in out:
            if r.get("range_printed") and not r.get("flag") and _call(r["value_num"], *r["ref_range"]) != "normal":
                r["needs_check"] = True
                r["checks"].append(f"The report marks other results High or Low but not this one, though {r['value']} is outside {r['reference']} — "
                                   "the value or the range may be misread")
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
        pm = re.search(r"(?:patient|name|pt\.?)\s*(?:name)?\s*[:\-]\s*([A-Za-z][A-Za-z0-9 .]{1,40}?)(?=\s{2,}|\s*(?:age|sex|date|uhid|ref|$))", ln.text, re.I)
        if pm and "patient_name" not in meta:
            meta["patient_name"] = re.sub(r"(?<=[A-Za-z])1|1(?=[a-z])", "l", pm.group(1)).replace("0", "o").strip()  # "Gi11" → "Gill"
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


def _same(a: dict, b: dict) -> bool:
    if a.get("value_num") is not None and b.get("value_num") is not None:
        return abs(a["value_num"] - b["value_num"]) <= 1e-6 * max(1.0, abs(a["value_num"]))
    return str(a.get("value")).lower().replace(" ", "") == str(b.get("value")).lower().replace(" ", "")


def _printed_range(r: dict) -> tuple | None:
    ref = r.get("reference") or ""
    got = _ref(ref) if "typical" not in ref else None
    return got[:2] if got else None


def cross_check(rows: list[dict], rows2: list[dict], engine2: str) -> tuple[list[dict], dict]:
    """B9 for reports: the second engine's rows against the first's, test by test. A different value or printed
    range is a disagreement: the row is marked for checking and carries both readings. A test only the second engine
    found is added, marked as such. A row the second engine could not read is noted, not flagged."""
    by2: dict[str, dict] = {}
    for r in rows2:
        if r.get("value") is not None:
            by2.setdefault(r["test_key"], r)
    agree, differ = 0, []
    for r in rows:
        b = by2.pop(r["test_key"], None)
        if b is None:
            r["checks"].append("The second OCR engine could not read this row")
            continue
        if _same(r, b):
            agree += 1
            r["second_engine"] = "agrees"
        else:
            r["needs_check"] = True
            r["second_engine"] = "differs"
            r["second_value"], r["second_value_num"] = b["value"], b.get("value_num")
            r["checks"].append(f'Second OCR engine read {b["value"]}' + (f' {b["unit"]}' if b.get("unit") and b.get("value_num") is not None else "") + " — check the crop")
            differ.append({"test": r["test"], "test_key": r["test_key"], "what": "value", "first": r["value"], "second": b["value"]})
        # A different range matters only where it changes the high/low call: "<200" read as "> 200" for a cholesterol
        # of 163 does; "15-4 45" beside a urea of 67 does not. Every range difference flagged three correct values in
        # twenty on phone photos (docs/EVALUATION.md, OCR).
        ra, rb, v = _printed_range(r), _printed_range(b), r.get("value_num")
        if ra and rb and ra != rb and v is not None and (_outside(v, r.get("ref_range")) > 0) != (_outside(v, b.get("ref_range")) > 0):
            r["needs_check"] = True
            r["checks"].append(f'Second OCR engine read the reference range as {b["reference"]}')
            differ.append({"test": r["test"], "test_key": r["test_key"], "what": "range", "first": r["reference"], "second": b["reference"]})
    for b in by2.values():  # tests only the second engine read
        rows.append({**b, "needs_check": True, "engine": engine2, "second_engine": "only",
                     "checks": [*b.get("checks", []), "Read by the second OCR engine only — check the crop"]})
    return rows, {"engine": engine2, "agree": agree, "disagreements": differ, "second_only": [b["test"] for b in by2.values()]}


# ---------------------------------------------------------------- B2: the report's numbers against each other

SLACK = 0.02  # beyond rounding, labs compute some values a little differently (urea ÷ 2.14 or 2.1428; a 5-part analyser)


def _n(x: float, key: str = "") -> str:
    return f"{round(x):,}" if key in COUNTS else f"{round(x, 2):g}"


def _half(r: dict) -> float:
    """Half a unit of the last printed digit, in the unit the value is held in: "4.52" ×10³/µL → 5 /µL; "9.4" → 0.05."""
    s = str(r.get("value") or "").replace(",", "")
    d = len(s.split(".")[1]) if "." in s else 0
    try:
        raw = float(s)
    except ValueError:
        return 0.0
    scale = r["value_num"] / raw if raw else 1.0
    return 0.5 * 10 ** -d * scale


def _sums(v: dict[str, float], h: dict[str, float], names: dict[str, str]) -> list[tuple[str, bool, tuple[str, ...], str]]:
    """Every relation between printed values that holds on a correct report: (name, holds, tests, what is wrong).
    The tolerance is what rounding each printed value can account for (its last digit, carried through the sum or
    the ratio) plus SLACK; a misread digit anywhere but the last moves a value further than that."""
    out = []

    def has(*ks):
        return all(k in v for k in ks)

    def rel(exp, *ks):  # rounding of a quotient or product: relative errors add
        return exp * sum(h[k] / v[k] for k in ks if v[k])

    diff = [k for k in DIFF if k in v]
    if len(diff) >= 4:  # basophils (often 0) are sometimes left off
        s, tol = sum(v[k] for k in diff), sum(h[k] for k in diff) + 0.5
        out.append(("differential", abs(s - 100) <= tol if len(diff) == 5 else s <= 100 + tol, tuple(diff),
                    f"The WBC differential adds up to {_n(s)} % (should be 100 %) — one of these is misread"))
    for c in DIFF:
        a = f"abs_{c}"
        if has(c, a, "wbc"):
            exp = v[c] * v["wbc"] / 100
            tol = h[a] + (h[c] * v["wbc"] + v[c] * h["wbc"]) / 100 + SLACK * exp + 5
            out.append((a, abs(v[a] - exp) <= tol, (c, a, "wbc"),
                        f"{TEST[a].name} is {_n(v[a], a)} /µL, but {_n(v[c])} % of {_n(v['wbc'], 'wbc')} is {_n(exp, a)} — one of the three is misread"))
    absl = [f"abs_{c}" for c in DIFF]
    if has(*absl, "wbc"):
        s = sum(v[k] for k in absl)
        out.append(("absolute_total", abs(s - v["wbc"]) <= sum(h[k] for k in absl) + h["wbc"] + SLACK * v["wbc"], (*absl, "wbc"),
                    f"The absolute counts add up to {_n(s, 'wbc')} /µL, but the total WBC is {_n(v['wbc'], 'wbc')} — one of these is misread"))
    if has("total_protein", "albumin", "globulin"):
        exp = v["total_protein"] - v["albumin"]
        out.append(("globulin", abs(v["globulin"] - exp) <= h["total_protein"] + h["albumin"] + h["globulin"] + SLACK, ("total_protein", "albumin", "globulin"),
                    f"Globulin is {_n(v['globulin'])} g/dL, but total protein {_n(v['total_protein'])} − albumin {_n(v['albumin'])} = {_n(exp)} — one of the three is misread"))
    elif has("total_protein", "albumin"):
        out.append(("albumin_protein", v["albumin"] < v["total_protein"] + h["albumin"] + h["total_protein"], ("total_protein", "albumin"),
                    f"Albumin {_n(v['albumin'])} g/dL is more than the total protein {_n(v['total_protein'])} — one of the two is misread"))
    if has("albumin", "ag_ratio") and ("globulin" in v or "total_protein" in v):
        if "globulin" in v:
            glob, hg, src = v["globulin"], h["globulin"], ("globulin",)
        else:
            glob, hg, src = v["total_protein"] - v["albumin"], h["total_protein"] + h["albumin"], ("total_protein",)
        if glob > hg:
            exp = v["albumin"] / glob
            tol = exp * (h["albumin"] / v["albumin"] + hg / glob) + h["ag_ratio"] + SLACK * exp
            out.append(("ag_ratio", abs(v["ag_ratio"] - exp) <= tol, ("albumin", *src, "ag_ratio"),
                        f"The A/G ratio is {_n(v['ag_ratio'])}, but albumin {_n(v['albumin'])} ÷ globulin {_n(glob)} = {_n(exp)} — one of these is misread"))
    if has("bilirubin", "bilirubin_direct", "bilirubin_indirect"):
        exp = v["bilirubin"] - v["bilirubin_direct"]
        tol = h["bilirubin"] + h["bilirubin_direct"] + h["bilirubin_indirect"] + SLACK
        out.append(("bilirubin", abs(v["bilirubin_indirect"] - exp) <= tol, ("bilirubin", "bilirubin_direct", "bilirubin_indirect"),
                    f"Indirect bilirubin is {_n(v['bilirubin_indirect'])} mg/dL, but total {_n(v['bilirubin'])} − direct {_n(v['bilirubin_direct'])} = {_n(exp)} — "
                    "one of the three is misread"))
    elif has("bilirubin", "bilirubin_direct"):
        out.append(("bilirubin", v["bilirubin_direct"] <= v["bilirubin"] + h["bilirubin"] + h["bilirubin_direct"], ("bilirubin", "bilirubin_direct"),
                    f"Direct bilirubin {_n(v['bilirubin_direct'])} mg/dL is more than the total {_n(v['bilirubin'])} — one of the two is misread"))
    if has("haemoglobin", "pcv"):
        exp = v["haemoglobin"] / v["pcv"] * 100
        if "mchc" in v:
            tol = rel(exp, "haemoglobin", "pcv") + h["mchc"] + SLACK * exp
            out.append(("mchc", abs(v["mchc"] - exp) <= tol, ("haemoglobin", "pcv", "mchc"),
                        f"MCHC is {_n(v['mchc'])} g/dL, but haemoglobin {_n(v['haemoglobin'])} ÷ PCV {_n(v['pcv'])} % = {_n(exp)} — one of the three is misread"))
        else:  # no one's red cells hold less than about 22 or more than 40 g/dL of haemoglobin
            out.append(("mchc", 22 <= exp <= 40, ("haemoglobin", "pcv"),
                        f"Haemoglobin {_n(v['haemoglobin'])} g/dL and PCV {_n(v['pcv'])} % do not fit together (they give an MCHC of {_n(exp)}; "
                        "possible is about 22–40) — one of the two is misread"))
    if has("pcv", "rbc", "mcv"):
        exp = v["pcv"] / v["rbc"] * 10
        out.append(("mcv", abs(v["mcv"] - exp) <= rel(exp, "pcv", "rbc") + h["mcv"] + SLACK * exp, ("pcv", "rbc", "mcv"),
                    f"MCV is {_n(v['mcv'])} fL, but PCV {_n(v['pcv'])} ÷ RBC {_n(v['rbc'])} × 10 = {_n(exp)} — one of the three is misread"))
    if has("haemoglobin", "rbc", "mch"):
        exp = v["haemoglobin"] / v["rbc"] * 10
        out.append(("mch", abs(v["mch"] - exp) <= rel(exp, "haemoglobin", "rbc") + h["mch"] + SLACK * exp, ("haemoglobin", "rbc", "mch"),
                    f"MCH is {_n(v['mch'])} pg, but haemoglobin {_n(v['haemoglobin'])} ÷ RBC {_n(v['rbc'])} × 10 = {_n(exp)} — one of the three is misread"))
    if has("triglycerides", "vldl"):  # Friedewald: VLDL = TG ÷ 5, not used above a TG of 400
        exp = v["triglycerides"] / 5
        tol = h["triglycerides"] / 5 + h["vldl"] + SLACK * exp + 0.5
        # Above 400 a lab measures VLDL instead, so only a VLDL that is TG ÷ 5 of a TG under 400 contradicts the TG
        holds = abs(v["vldl"] - exp) <= tol if v["triglycerides"] <= 400 else v["vldl"] > 80 + tol
        out.append(("vldl", holds, ("triglycerides", "vldl"),
                    f"VLDL is {_n(v['vldl'])} mg/dL, but triglycerides {_n(v['triglycerides'])} ÷ 5 = {_n(exp)} — one of the two is misread"))
    if has("cholesterol", "hdl", "ldl"):
        if "vldl" in v and "direct" not in names.get("ldl", "").lower():  # a calculated LDL is TC − HDL − VLDL
            exp = v["hdl"] + v["ldl"] + v["vldl"]
            tol = sum(h[k] for k in ("cholesterol", "hdl", "ldl", "vldl")) + SLACK * v["cholesterol"]
            out.append(("cholesterol", abs(v["cholesterol"] - exp) <= tol, ("cholesterol", "hdl", "ldl", "vldl"),
                        f"Total cholesterol is {_n(v['cholesterol'])} mg/dL, but HDL + LDL + VLDL = {_n(exp)} — one of the four is misread"))
        else:  # HDL and LDL are parts of the total
            out.append(("cholesterol", v["hdl"] + v["ldl"] <= v["cholesterol"] + h["hdl"] + h["ldl"] + h["cholesterol"] + SLACK * v["cholesterol"],
                        ("cholesterol", "hdl", "ldl"),
                        f"HDL {_n(v['hdl'])} + LDL {_n(v['ldl'])} is more than the total cholesterol {_n(v['cholesterol'])} — one of the three is misread"))
    if has("cholesterol", "hdl", "non_hdl"):
        exp = v["cholesterol"] - v["hdl"]
        out.append(("non_hdl", abs(v["non_hdl"] - exp) <= h["cholesterol"] + h["hdl"] + h["non_hdl"] + SLACK * exp, ("cholesterol", "hdl", "non_hdl"),
                    f"Non-HDL cholesterol is {_n(v['non_hdl'])} mg/dL, but total {_n(v['cholesterol'])} − HDL {_n(v['hdl'])} = {_n(exp)} — one of the three is misread"))
    for r, top in (("tc_hdl_ratio", "cholesterol"), ("ldl_hdl_ratio", "ldl")):
        if has(r, top, "hdl") and v["hdl"] > 0:
            exp = v[top] / v["hdl"]
            out.append((r, abs(v[r] - exp) <= rel(exp, top, "hdl") + h[r] + SLACK * exp, (top, "hdl", r),
                        f"{TEST[r].name} is {_n(v[r])}, but {_n(v[top])} ÷ {_n(v['hdl'])} = {_n(exp)} — one of the three is misread"))
    if has("urea", "bun"):
        exp = v["bun"] * 2.14
        out.append(("urea_bun", abs(v["urea"] - exp) <= 2.14 * h["bun"] + h["urea"] + SLACK * exp, ("urea", "bun"),
                    f"Urea is {_n(v['urea'])} mg/dL, but BUN {_n(v['bun'])} × 2.14 = {_n(exp)} — one of the two is misread"))
    return out


def consistency(rows: list[dict]) -> dict:
    """B2: the report's own numbers checked against each other (WBC differential = 100 %, absolute count = % × total,
    globulin = total protein − albumin, MCHC = Hb ÷ PCV, …). A relation that does not hold marks every value in it for
    checking: the sum cannot tell which one is misread. Where the second OCR engine read one of them differently and
    its reading makes the relation hold, the check says so; nothing is corrected."""
    by: dict[str, dict] = {}
    for r in rows:
        t = TEST.get(r.get("test_key"))
        if t and r.get("value_num") is not None and t.plausible[0] <= r["value_num"] <= t.plausible[1]:
            by.setdefault(t.key, r)
    v = {k: r["value_num"] for k, r in by.items()}
    h = {k: _half(r) for k, r in by.items()}
    names = {k: r.get("printed_name") or "" for k, r in by.items()}
    results = _sums(v, h, names)
    failed = []
    for name, ok, keys, text in results:
        if ok:
            continue
        for k in keys:  # does the second engine's reading of one value make it add up?
            alt = by[k].get("second_value_num")
            if alt is not None and any(n == name and good for n, good, _, _ in _sums({**v, k: alt}, h, names)):
                text += f". With the second OCR engine's reading of {TEST[k].name} ({by[k]['second_value']}) it adds up"
                break
        for k in keys:
            by[k].setdefault("flagged_without_sums", by[k]["needs_check"])  # for the evaluation: what the sums added
            by[k]["needs_check"] = True
            by[k]["checks"].append(text)
        failed.append({"check": name, "keys": list(keys), "tests": [TEST[k].name for k in keys], "text": text})
    return {"checked": [n for n, *_ in results], "failed": failed}

def extract_document(data: bytes, content_type: str, *, patient_name: str | None = None, sex: str | None = None, pregnant: bool = False,
                     second: bool = False) -> dict:
    """`second`: also read the image with the second OCR engine and compare (B9). For reports; a photo of the
    problem is only scanned for ID numbers and does not need it."""
    res = read_document(data, content_type, second)
    rows = parse_labs(res, sex, pregnant) if res.lines else []
    second_check = None
    if res.second is not None and res.lines:
        rows, second_check = cross_check(rows, parse_labs(res.second, sex, pregnant) if res.second.lines else [], res.second.engine)
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
        second_check = None
    return {
        "engine": res.engine,
        "second_check": second_check,
        "consistency": consistency(rows),
        "doc_type": kind,
        "medicines": meds,
        "quality": res.quality,
        "rows": rows,
        "meta": meta,
        "warnings": warnings,
        "text": text,
        "at": datetime.now(timezone.utc).isoformat(),
    }


def wants_online_reading(ex: dict) -> bool:
    """Handwriting, or a page the offline engines could not make sense of: a prescription, a page with no lab values
    and no medicines, or text recognised with low confidence. A printed lab report read cleanly is never sent."""
    kind = (ex.get("doc_type") or {}).get("type")
    hard = any("hard to read" in w.lower() for w in ex.get("warnings", []))
    return kind == "prescription" or hard or (kind in ("other_document", "non_document") and not ex.get("rows") and not ex.get("medicines"))


def add_online_reading(ex: dict, data: bytes, filename: str, lines: list[dict] | None = None) -> dict:
    """Sarvam Vision's reading of the same page, beside the offline one (B1 handwriting, B9). Medicines it names are
    added with who read them; lab values it reads are added only where the offline engines read none, and always
    marked for checking: a handwritten number is never taken on one engine's word. `lines` lets tests skip the call."""
    from .. import sarvam
    from .images import doc_type, medicines

    if lines is None:
        try:
            lines = sarvam.read_page(data, filename)
        except sarvam.SarvamUnavailable as e:
            ex["warnings"].append(f"Online reading not available ({e}) — the reviewer should read the page directly")
            return ex
    ex["online_reading"] = {"engine": sarvam.VISION_ENGINE, "text": lines[:200]}
    have = {m["name"].lower(): m for m in ex.get("medicines") or []}
    for m in medicines(lines):
        if m["name"].lower() in have:
            have[m["name"].lower()]["read_by"] = "both"
        else:
            ex.setdefault("medicines", []).append({**m, "read_by": sarvam.VISION_ENGINE})
    for m in ex.get("medicines") or []:
        m.setdefault("read_by", ex["engine"])
    # Its boxes are fractions of the page; the row grouping works in pixels (a 4-pixel floor), so scale to 1000.
    online = OcrResult(sarvam.VISION_ENGINE, [Line(x["text"], [v * 1000 for v in x["bbox"]], float(x["conf"])) for x in lines], (1000.0, 1000.0))
    keys = {r["test_key"] for r in ex.get("rows") or []}
    for r in parse_labs(online):
        if r["test_key"] not in keys and r.get("value") is not None:
            ex.setdefault("rows", []).append({**r, "needs_check": True, "engine": sarvam.VISION_ENGINE,
                                              "checks": [*r["checks"], "Read online from the photo (handwriting?) — check against the crop"]})
    if (ex.get("doc_type") or {}).get("type") in ("other_document", "non_document"):
        better = doc_type(lines, len(ex.get("rows") or []))
        if better["type"] not in ("other_document", "non_document"):
            ex["doc_type"] = {**better, "why": f"{better['why']} (read online)"}
    return ex


def lab_values(extractions: list[dict]) -> dict[str, float]:
    """Numeric values the rules engine may use (e.g. potassium for the ATP outside-evaluation rule).
    Impossible values (misreads) are excluded. Low-confidence but possible values are kept: rules
    only ever raise urgency, so a doubtful high potassium over-triages rather than being missed."""
    out: dict[str, float] = {}
    for ex in extractions:
        for r in ex.get("rows", []):
            test = next((t for t in TESTS if t.key == r["test_key"]), None)
            if not test:
                continue
            # Where the two OCR engines read different values, the rules see the one further outside the range: the
            # reviewer is asked which is right, and until then the urgency errs high (as with a second-engine symptom).
            cands = [v for v in (r.get("value_num"), r.get("second_value_num")) if v is not None and test.plausible[0] <= v <= test.plausible[1]]
            if cands:
                out[r["test_key"]] = max(cands, key=lambda v: _outside(v, r.get("ref_range")))
    return out


def _outside(v: float, rng: list | None) -> float:
    lo, hi = (rng or [None, None])[:2]
    if lo and v < lo:
        return (lo - v) / lo
    if hi and v > hi:
        return (v - hi) / hi
    return 0.0
