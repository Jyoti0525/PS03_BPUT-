"""OCR reading checks (B1, B9, B10): what the synthetic-report evaluation found and fixed (docs/EVALUATION.md, OCR),
the second OCR engine's cross-check, the online handwriting reader and brand names on prescriptions. No OCR engine
runs here: the engines' lines are given, as they came out on the evaluation photos."""

import io

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app import sarvam
from app.triage import extraction as E
from app.triage import images


def L(text, x, y, w=150, h=24, conf=0.97, slope=0.0):
    return E.Line(text, [x, y, w, h], conf, 0, slope)


def labs(lines, size=(1200, 1700)):
    return {r["test_key"]: r for r in E.parse_labs(E.OcrResult("test", lines, size))}


# ── reading the table ──────────────────────────────────
def test_a_tilted_photo_pairs_each_test_with_its_own_value():
    # 2.5° tilt: the value column sits 18 px lower than its test name, closer to the next row's name than its own
    s = 0.044
    rows = [("Total Cholesterol", "245", "< 200"), ("Triglycerides", "159", "35 - 150"), ("HDL Cholesterol", "55", "40 - 60")]
    lines = []
    for i, (name, value, ref) in enumerate(rows):
        y = 300 + 46 * i
        lines += [L(name, 70, y, 300, slope=s), L(value, 560, y + 560 * s, 60, slope=s), L(ref, 960, y + 960 * s, 110, slope=s)]
    got = labs(lines)
    assert [got[k]["value"] for k in ("cholesterol", "triglycerides", "hdl")] == ["245", "159", "55"]


def test_a_range_printed_under_its_value_belongs_to_the_test_above():
    # thermal slip: name and value, then "(70 - 110)" halfway to the next test
    lines = [L("Fasting Blood Sugar", 20, 300, 260), L("158 mg/dl", 330, 300, 120), L("(70 - 110)", 330, 322, 110, h=18),
             L("Post Prandial Blood Su", 20, 344, 260), L("314 mg/dl", 330, 344, 120), L("(< 140)", 330, 366, 90, h=18)]
    got = labs(lines, (640, 900))
    assert got["glucose_fasting"]["reference"] == "(70 - 110)" and got["glucose_pp"]["reference"] == "(< 140)"
    assert got["glucose_pp"]["test"] == "Post-prandial blood sugar"  # the printer cut the name short


def test_what_ocr_writes_is_read_as_printed():
    assert E._clean("（<200）") == "(<200)" and E._clean("µIU/mL") == "µIU/mL"  # full-width brackets; µ stays µ
    assert E.match_test("Dengue Nsl Antigen")[0].key == "dengue_ns1" and E.match_test("Dengue Nsi Antigen")[0].key == "dengue_ns1"
    assert E._mend_range("1,50,0004,50,000") == "1,50,000-4,50,000" and E._mend_range("0.4.4.0") == "0.4-4.0"
    assert E._mend_range("36.46") == "36.46"  # could be 36-46 or a value: left as read


def test_platelets_in_lakhs_are_compared_with_a_range_in_lakhs():
    got = labs([L("Platelet Count", 70, 300, 200), L("3.00", 560, 300, 60), L("lakhs/cumm", 760, 300, 120), L("1.50 - 4.50", 960, 300, 120)])
    p = got["platelets"]
    assert p["value_num"] == 300000 and p["ref_range"] == [150000, 450000] and p["status"] == "normal"


def test_a_lakh_read_as_one_and_a_digit_read_as_a_letter_are_shown_not_hidden():
    got = labs([L("Platelet Count", 70, 300, 200), L("3.001akhs/cumm", 560, 300, 160), L("SGOT", 70, 360, 80), L("i75", 560, 360, 50), L("U/L", 760, 360, 50)])
    assert got["platelets"]["value_num"] == 300000
    assert got["ast"]["value_num"] == 175 and got["ast"]["needs_check"] and 'read as "i75"' in got["ast"]["checks"][0]


def test_a_unit_not_read_is_said_and_a_faint_range_does_not_flag_a_clear_value():
    got = labs([L("Serum Sodium", 70, 300, 200), L("135", 560, 300, 50), L("(135-145)", 960, 300, 110, conf=0.6)])
    assert any("No unit read" in c for c in got["sodium"]["checks"])
    assert not got["sodium"]["needs_check"]  # the value cell was read at 0.97


# ── the second engine ──────────────────────────────────
def row(key, value, num, ref="70 - 110", rr=(70, 110), conf=0.97):
    return {"test_key": key, "test": key, "value": value, "value_num": num, "unit": "mg/dL", "reference": ref, "ref_range": list(rr),
            "status": "normal", "needs_check": False, "checks": [], "ocr_confidence": conf}


def test_engines_that_read_a_value_differently_flag_it_with_both_readings():
    rows, check = E.cross_check([row("glucose_fasting", "158", 158), row("urea", "45", 45, "15 - 45", (15, 45))],
                                [row("glucose_fasting", "168", 168), row("urea", "45", 45, "15 - 45", (15, 45)), row("hba1c", "6.1", 6.1, "4.0 - 5.6", (4, 5.6))], "second")
    g, u = rows[0], rows[1]
    assert g["needs_check"] and g["second_value"] == "168" and "Second OCR engine read 168" in g["checks"][0]
    assert not u["needs_check"] and u["second_engine"] == "agrees"
    assert rows[2]["test_key"] == "hba1c" and rows[2]["needs_check"] and rows[2]["second_engine"] == "only"
    assert check["agree"] == 1 and check["disagreements"][0]["first"] == "158" and check["second_only"] == ["hba1c"]


def test_a_different_range_matters_only_where_it_changes_high_or_low():
    rows, check = E.cross_check([row("cholesterol", "163", 163, "< 200", (None, 200)), row("urea", "67", 67, "15 - 45", (15, 45))],
                                [row("cholesterol", "163", 163, "> 200", (200, None)), row("urea", "67", 67, "15-4 45", (15, 4))], "second")
    assert rows[0]["needs_check"] and "range as > 200" in rows[0]["checks"][-1]  # normal under one, low under the other
    assert not rows[1]["needs_check"]  # high under both
    assert [d["what"] for d in check["disagreements"]] == ["range"]


def test_until_someone_checks_the_rules_use_the_reading_further_from_normal():
    r, _ = E.cross_check([row("potassium", "5.0", 5.0, "3.5 - 5.1", (3.5, 5.1))], [row("potassium", "6.0", 6.0, "3.5 - 5.1", (3.5, 5.1))], "second")
    assert E.lab_values([{"rows": r}]) == {"potassium": 6.0}


def _page(n, scale, thick, gap):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    page = np.full((1754, 1240), 255, np.uint8)
    for i in range(n):
        cv2.putText(page, f"Serum Creatinine   1.{i % 10}4 mg/dL   0.6 - 1.3", (70, 150 + gap * i), cv2.FONT_HERSHEY_SIMPLEX, scale, 0, thick, cv2.LINE_AA)
    return page


def _blur(page, sigma, dim=1.0):
    import cv2
    import numpy as np

    return np.clip(cv2.GaussianBlur(page, (0, 0), sigma) * dim + np.random.default_rng(1).normal(0, 9, page.shape), 0, 255).astype(np.uint8)


def test_the_quality_check_passes_a_clean_white_page_and_stops_a_blurred_photo():
    assert E.image_quality(_page(12, 0.9, 2, 60))["ok"]  # mostly white: the old whole-page contrast measure asked for a retake
    q = E.image_quality(_blur(_page(40, 0.6, 1, 38), 3.0))  # a full page of small print, shaken
    assert not q["ok"] and any("Blurry" in i for i in q["issues"])  # sensor noise no longer passes for sharpness


def test_a_page_blurred_past_reading_asks_for_a_retake_even_when_it_scores_sharp():
    cv2 = pytest.importorskip("cv2")
    if not E.ocr_available():
        pytest.skip("OCR engine not installed")
    big = _page(12, 0.9, 2, 60)
    dim = _blur(big, 3.0, 0.7)  # large print, dim and shaken: noise lifts the blur score over the line
    assert E.image_quality(dim)["ok"]
    q = E.ocr_image(cv2.imencode(".png", dim)[1].tobytes()).quality
    assert not q["ok"] and any("hard to read" in i for i in q["issues"])  # the reader's own confidence catches it
    q = E.ocr_image(cv2.imencode(".png", _blur(big, 8.0, 0.7))[1].tobytes()).quality
    assert not q["ok"] and any("No text could be read" in i for i in q["issues"])


# ── prescriptions, brands and handwriting ──────────────
def rx(*texts):
    return [{"text": t, "conf": 0.6, "bbox": [0.1, 0.1 * i, 0.6, 0.05]} for i, t in enumerate(texts)]


def test_brand_names_on_drug_orders_are_named_with_what_they_contain():
    meds = {m["name"]: m for m in images.medicines(rx("Rx", "1 Tab Dolo 650 - 1-0-1 x 5 days", "2 Tab Montair FX 10 OD", "Rest at home"))}
    assert set(meds) == {"Dolo", "Montair FX"}  # "Rest" and "Days" are brands too, but not where a medicine's name goes
    assert "Paracetamol" in meds["Dolo"]["contains"] and meds["Dolo"]["strength"] == "650 mg"  # unit from Dolo's own products
    assert meds["Montair FX"]["contains"] == "Montelukast (10mg) + Fexofenadine (120mg)"
    assert all(m["kind"] == "brand" and m["status"] == "awaiting_confirmation" for m in meds.values())


def test_a_slightly_misread_brand_is_still_found_on_a_drug_line():
    meds = images.medicines(rx("Tab Azithrel 500 OD x 3 days"))  # handwriting: Azithral (Azithree is as close; fewer products)
    assert [m["name"] for m in meds] == ["Azithral"]


def test_dose_words_and_everyday_words_are_not_named_as_medicines():
    meds = images.medicines(rx("5 ml - Twice a day X 4 Days", "1 sachet - Once a day X 1 Month", "Throat normal", "Eat papaya, iron rich food"))
    assert meds == []


def test_a_brand_and_the_contents_printed_under_it_are_one_medicine():
    meds = images.medicines(rx("1. Syrup Allegra:", "FEXOFENADINE(30 MG)", "5 ml - Twice a day X 4 Days"))
    assert [(m["name"], m["kind"]) for m in meds] == [("Allegra", "brand")]


def test_only_pages_the_offline_engines_could_not_read_go_online():
    assert E.wants_online_reading({"doc_type": {"type": "prescription"}, "rows": [], "warnings": []})
    assert E.wants_online_reading({"doc_type": {"type": "other_document"}, "rows": [], "medicines": [], "warnings": []})
    assert not E.wants_online_reading({"doc_type": {"type": "lab_report"}, "rows": [{}, {}], "warnings": []})


def test_the_online_reading_adds_what_it_read_marked_and_never_unchecked():
    ex = {"engine": "RapidOCR", "doc_type": {"type": "other_document", "label": "Other", "why": ""}, "rows": [], "medicines": [], "warnings": []}
    online = rx("Advice:", "Rx", "Tab Dolo 650 1-0-1", "Syp Azithral 200 OD", "Hb 9.4 g/dL")
    ex = E.add_online_reading(ex, b"", "rx.jpg", lines=online)
    assert {m["name"] for m in ex["medicines"]} == {"Dolo", "Azithral"} and all(m["read_by"] == sarvam.VISION_ENGINE for m in ex["medicines"])
    hb = ex["rows"][0]
    assert hb["test_key"] == "haemoglobin" and hb["needs_check"] and hb["engine"] == sarvam.VISION_ENGINE
    assert ex["doc_type"]["type"] == "prescription" and ex["doc_type"]["why"].endswith("(read online)")


def _fake_prescription(data, ctype, second=False, **kw):
    return {"engine": "RapidOCR", "second_check": None, "doc_type": {"type": "prescription", "label": "Prescription", "why": "rx"},
            "medicines": [], "quality": {"ok": True, "issues": []}, "rows": [], "meta": {}, "warnings": [], "text": [], "at": "now"}


def test_a_handwritten_page_goes_online_only_with_the_patients_consent(client, nurse, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from app.routers import files

    sent = []
    monkeypatch.setattr(files, "extract_document", _fake_prescription)
    monkeypatch.setattr(sarvam, "enabled", lambda: True)
    monkeypatch.setattr(sarvam, "read_page", lambda data, name, lang="en": sent.append(name) or rx("Tab Dolo 650 1-0-1"))
    png = cv2.imencode(".png", np.full((600, 600, 3), 240, np.uint8))[1].tobytes()

    def up(**form):
        return client.post(f"{API}/files", files={"file": ("rx.png", io.BytesIO(png), "image/png")}, data={"kind": "report", **form}, headers=nurse).json()

    up()  # staff upload, no consent asked: offline only
    assert sent == []
    f = up(online="true")
    assert sent == ["rx.png"] and f["read_quality"]["engine"] == "RapidOCR"


def test_note_says_when_two_ocr_engines_read_a_report_differently(client, nurse, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from app.routers import files

    def read(data, ctype, second=False, **kw):
        rows, check = E.cross_check([row("potassium", "5.0", 5.0, "3.5 - 5.1", (3.5, 5.1))], [row("potassium", "6.0", 6.0, "3.5 - 5.1", (3.5, 5.1))], "docTR")
        return {**_fake_prescription(data, ctype), "doc_type": {"type": "lab_report", "label": "Lab report", "why": "1"}, "rows": rows, "second_check": check}

    monkeypatch.setattr(files, "extract_document", read)
    png = cv2.imencode(".png", np.full((600, 600, 3), 240, np.uint8))[1].tobytes()
    f = client.post(f"{API}/files", files={"file": ("k.png", io.BytesIO(png), "image/png")}, data={"kind": "report"}, headers=nurse).json()
    _, body = new_intake(client, nurse, chief_complaint="weakness", file_ids=[f["id"]])
    note = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()["note"]
    d = next(x for x in note["disagreements"] if x["field"].startswith("potassium"))
    assert [v["value"] for v in d["values"]] == ["5.0", "6.0"] and "further from normal" in d["action"]
