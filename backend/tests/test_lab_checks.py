"""B2 numeric validation: the lab's own High/Low marks against the value and range, units that belong to the test (SI
units converted), printed ranges that fit the test, and the report's numbers checked against each other. No OCR engine
runs here: the lines are given as an engine returns them. Measured in docs/EVALUATION.md, "Numeric validation (B2)"."""

import io

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app.triage import extraction as E


def L(text, x, y, w=150, h=24, conf=0.97):
    return E.Line(text, [x, y, w, h], conf, 0, 0.0)


def table(rows, size=(1200, 1700)):
    """[(name, value, unit, range)] laid out as a printed table, one row per 40 px."""
    lines = []
    for i, (name, value, unit, ref) in enumerate(rows):
        y = 300 + 40 * i
        lines += [L(name, 60, y, 300), L(value, 520, y, 90)] + ([L(unit, 700, y, 90)] if unit else []) + ([L(ref, 900, y, 160)] if ref else [])
    return E.OcrResult("test", lines, size)


def labs(rows):
    return {r["test_key"]: r for r in E.parse_labs(table(rows))}


def checked(rows):
    parsed = E.parse_labs(table(rows))
    return {r["test_key"]: r for r in parsed}, E.consistency(parsed)


# ── tests that used to be read as another test ─────────────────

def test_names_once_taken_for_another_test_are_their_own_tests():
    for printed, key in [("VLDL Cholesterol", "vldl"), ("Non-HDL Cholesterol", "non_hdl"), ("Cholesterol/HDL Ratio", "tc_hdl_ratio"),
                         ("LDL/HDL Ratio", "ldl_hdl_ratio"), ("Blood Urea Nitrogen", "bun"), ("Serum Bilirubin (Direct)", "bilirubin_direct"),
                         ("RBC Count", "rbc"), ("Absolute Neutrophil Count", "abs_neutrophils"), ("Neutrophils (Absolute)", "abs_neutrophils"),
                         ("Absolute Eosinophil Count (AEC)", "abs_eosinophils"), ("A/G Ratio", "ag_ratio"), ("Polymorphs", "neutrophils")]:
        assert E.match_test(printed)[0].key == key, printed
    assert E.match_test("Serum Bilirubin (Total)")[0].key == "bilirubin"
    assert E.match_test("LDL Cholesterol (Calculated)")[0].key == "ldl"


def test_a_differential_printed_as_a_count_is_the_absolute_count():
    r = labs([("Neutrophils", "4,520", "cells/cumm", "2000 - 7000")])
    assert "abs_neutrophils" in r and r["abs_neutrophils"]["value_num"] == 4520


def test_albumin_nil_under_urine_routine_is_the_urine_test_and_microscopy_is_not_a_blood_count():
    r = labs([("Albumin", "Nil", "", ""), ("RBC", "2-4 /hpf", "", ""), ("Pus cells", "3-5 /hpf", "", "")])
    assert r["urine_albumin"]["value"] == "nil" and "rbc" not in r and "wbc" not in r


def test_a_number_ocr_broke_in_two_is_flagged_not_taken_as_its_first_part():
    # found on the B2 development photos: the decimal point read as a dash, a 0 read as e
    for name, value in [("Serum Creatinine", "4-54"), ("MCV", "107-5"), ("Total WBC Count", "19,9e0")]:
        r = next(iter(labs([(name, value, "", "")]).values()))
        assert r["needs_check"] and any(f'Value read as "{value}"' in c for c in r["checks"]), value
    r = labs([("Fasting Blood Sugar", "310H", "mg/dL", "70 - 110")])["glucose_fasting"]  # a mark glued to the value is fine
    assert r["value"] == "310" and r["flag"] == "H" and not r["needs_check"]


# ── units ──────────────────────────────────────────────────────

def test_units_as_ocr_writes_them():
    # the caret of "x10^3/µL" read as "~"; the l of "µmol/L" read as 1 on a thermal slip
    r = labs([("Absolute Neutrophil Count", "3.57", "X10~3/µL", "2.00 - 7.00"), ("Serum Creatinine", "284", "µmo1/L", "62 - 106")])
    assert r["abs_neutrophils"]["value_num"] == pytest.approx(3570) and r["abs_neutrophils"]["ref_range"] == [pytest.approx(2000), pytest.approx(7000)]
    assert r["creatinine"]["value_num"] == pytest.approx(3.21, abs=0.01)


def test_a_unit_that_ran_into_the_range_cell_is_the_values_unit():
    """Held-out scan r003: "4.87 lakhs/cumm" was once taken as 4,870 /µL against 1.5–4.5 lakh, a high count shown as very low."""
    p = labs([("Platelets", "4.87", None, "lakhs/cumm 1.50 - 4.50")])["platelets"]
    assert p["value_num"] == 487000 and p["unit"] == "lakhs/cumm" and p["reference"] == "1.50 - 4.50" and p["ref_range"] == [150000, 450000]
    assert p["status"] != "normal" and p["value_num"] > p["ref_range"][1]


def test_a_count_with_no_unit_read_is_flagged():
    p = labs([("Platelets", "2.10", None, None)])["platelets"]
    assert p["needs_check"] and any("No unit read" in c for c in p["checks"])


def test_si_units_are_converted_for_the_rules_with_their_range():
    r = labs([("Fasting Blood Sugar", "17.0", "mmol/L", "3.9 - 5.6"), ("Serum Creatinine", "133", "µmol/L", "62 - 106"),
              ("HbA1c", "64", "mmol/mol", "20 - 38"), ("Haemoglobin", "94", "g/L", "120 - 150")])
    g = r["glucose_fasting"]
    assert g["value"] == "17.0" and g["unit"] == "mmol/L" and g["value_num"] == pytest.approx(306.3, abs=0.1)
    assert g["ref_range"][0] == pytest.approx(70.3, abs=0.1) and g["status"] == "abnormal" and not g["needs_check"]
    assert any("the unit the rules use" in c for c in g["checks"])
    assert r["creatinine"]["value_num"] == pytest.approx(1.50, abs=0.01) and r["creatinine"]["status"] == "abnormal"
    assert r["hba1c"]["value_num"] == pytest.approx(8.0, abs=0.01)
    assert r["haemoglobin"]["value_num"] == pytest.approx(9.4) and r["haemoglobin"]["status"] == "abnormal"
    assert E.lab_values([{"rows": list(r.values())}])["glucose_fasting"] == pytest.approx(306.3, abs=0.1)


def test_a_unit_that_does_not_belong_to_the_test_is_flagged():
    r = labs([("Haemoglobin", "9.4", "mg/dL", "12.0 - 15.0"), ("Potassium", "4.2", "mmol/L", "3.5 - 5.1")])
    assert r["haemoglobin"]["needs_check"] and any("not a unit used for Haemoglobin" in c for c in r["haemoglobin"]["checks"])
    assert not r["potassium"]["needs_check"]


def test_gm_per_dl_and_g_percent_are_read_as_haemoglobin_units():
    assert labs([("Haemoglobin", "9.4", "gm/dL", "12.0 - 15.0")])["haemoglobin"]["unit"] == "gm/dL"
    r = labs([("Hb", "9.4", "g%", "12.0 - 15.0")])["haemoglobin"]
    assert r["unit"] == "g%" and not r["needs_check"]


def test_a_range_in_another_unit_is_not_used_for_the_high_low_call():
    # the value was read in mg/dL but the range is mmol/L (or misread): against "3.9 - 5.5" any glucose is "high"
    r = labs([("Fasting Blood Sugar", "92", "mg/dL", "3.9 - 5.5")])["glucose_fasting"]
    assert r["needs_check"] and any("does not look like" in c for c in r["checks"])
    assert r["ref_range"] == [70, 100] and r["status"] == "normal"


# ── the lab's own High / Low marks ─────────────────────────────

def test_a_mark_that_agrees_is_kept_and_the_l_of_mmol_per_l_is_not_a_mark():
    r = labs([("Fasting Blood Sugar", "310 H", "mg/dL", "70 - 110"), ("Serum Potassium", "4.2", "mmol/L", "3.5 - 5.1"), ("Serum Sodium", "128 L", "mmol/L", "135 - 145")])
    assert r["glucose_fasting"]["flag"] == "H" and not r["glucose_fasting"]["needs_check"]
    assert "flag" not in r["potassium"] and r["sodium"]["flag"] == "L" and not r["sodium"]["needs_check"]


def test_a_mark_that_contradicts_the_value_is_flagged_and_counts_as_out_of_range():
    r = labs([("Serum Potassium", "4.9 H", "mmol/L", "3.5 - 5.1")])["potassium"]  # 5.9 read as 4.9?
    assert r["needs_check"] and r["status"] == "borderline"
    assert any("marks this High, but 4.9 is inside" in c for c in r["checks"])
    r = labs([("Haemoglobin", "15.2 L", "g/dL", "12.0 - 15.0")])["haemoglobin"]
    assert r["needs_check"] and any("marks this Low, but 15.2 is above" in c for c in r["checks"])


def test_an_unmarked_result_outside_its_range_is_flagged_when_the_lab_marks_the_others():
    r = labs([("Fasting Blood Sugar", "310 H", "mg/dL", "70 - 110"), ("Serum Sodium", "128 L", "mmol/L", "135 - 145"),
              ("Serum Potassium", "6.1", "mmol/L", "3.5 - 5.1"), ("Serum Creatinine", "0.9", "mg/dL", "0.6 - 1.3")])
    assert r["potassium"]["needs_check"] and any("marks other results" in c for c in r["potassium"]["checks"])
    assert not r["creatinine"]["needs_check"]
    # a lab that marks nothing: no such check
    r = labs([("Serum Potassium", "6.1", "mmol/L", "3.5 - 5.1"), ("Fasting Blood Sugar", "310", "mg/dL", "70 - 110")])
    assert not r["potassium"]["needs_check"]


# ── the report's numbers against each other ────────────────────

CBC = [("Haemoglobin", "9.4", "g/dL", "12.0 - 15.0"), ("PCV", "31.0", "%", "36 - 46"), ("RBC Count", "3.62", "mill/cumm", "3.8 - 4.8"),
       ("MCV", "85.6", "fL", "83 - 101"), ("MCH", "26.0", "pg", "27 - 32"), ("MCHC", "30.3", "g/dL", "31.5 - 34.5"),
       ("Total WBC Count", "8,000", "/cumm", "4000 - 11000"), ("Neutrophils", "62", "%", "40 - 80"), ("Lymphocytes", "28", "%", "20 - 40"),
       ("Monocytes", "6", "%", "2 - 10"), ("Eosinophils", "3", "%", "1 - 6"), ("Basophils", "1", "%", "0 - 2"),
       ("Absolute Neutrophil Count", "4960", "/cumm", "2000 - 7000"), ("Absolute Eosinophil Count", "0.24", "x10^3/µL", "0.02 - 0.50")]
LFT = [("Total Bilirubin", "2.78", "mg/dL", "0.2 - 1.2"), ("Direct Bilirubin", "0.33", "mg/dL", "0.0 - 0.3"), ("Indirect Bilirubin", "2.45", "mg/dL", "0.2 - 0.8"),
       ("Total Protein", "6.8", "g/dL", "6.0 - 8.3"), ("Serum Albumin", "3.1", "g/dL", "3.5 - 5.2"), ("Globulin", "3.7", "g/dL", "2.0 - 3.5"),
       ("A/G Ratio", "0.84", "", "1.0 - 2.2")]
LIPID = [("Total Cholesterol", "236", "mg/dL", "< 200"), ("Triglycerides", "180", "mg/dL", "< 150"), ("HDL Cholesterol", "38", "mg/dL", "40 - 60"),
         ("LDL Cholesterol", "162", "mg/dL", "< 100"), ("VLDL Cholesterol", "36", "mg/dL", "< 30"), ("Non-HDL Cholesterol", "198", "mg/dL", "< 130"),
         ("Chol/HDL Ratio", "6.21", "", "< 4.5"), ("LDL/HDL Ratio", "4.26", "", "< 3.0"), ("Blood Urea", "64", "mg/dL", "15 - 45"),
         ("BUN", "29.9", "mg/dL", "7 - 20")]


def test_a_correct_report_adds_up():
    rows, c = checked(CBC + LFT + LIPID)
    assert c["failed"] == [] and len(c["checked"]) >= 15
    assert rows["abs_eosinophils"]["value_num"] == 240 and rows["ag_ratio"]["unit"] == ""
    assert not any(r["needs_check"] for r in rows.values())


@pytest.mark.parametrize("test,slip,relation", [
    ("Absolute Neutrophil Count", "4360", "abs_neutrophils"),  # 9 read as 3
    ("Eosinophils", "8", "differential"),  # 3 read as 8: the differential adds up to 105
    ("Haemoglobin", "8.4", "mchc"),
    ("Globulin", "2.7", "globulin"),
    ("Indirect Bilirubin", "2.15", "bilirubin"),
    ("VLDL Cholesterol", "86", "vldl"),
    ("Non-HDL Cholesterol", "168", "non_hdl"),
    ("BUN", "23.9", "urea_bun"),
    ("MCV", "65.6", "mcv"),
])
def test_one_misread_digit_breaks_a_sum_and_every_value_in_it_is_flagged(test, slip, relation):
    report = [(n, slip if n == test else v, u, r) for n, v, u, r in CBC + LFT + LIPID]
    rows, c = checked(report)
    failed = [f for f in c["failed"] if f["check"] == relation]
    assert failed, c["failed"]
    assert all(rows[k]["needs_check"] and failed[0]["text"] in rows[k]["checks"] for k in failed[0]["keys"])


def test_physiological_bounds_where_nothing_is_printed_to_add_up_to():
    _, c = checked([("Haemoglobin", "16.3", "g/dL", "12.0 - 15.0"), ("PCV", "23.5", "%", "36 - 46")])  # MCHC 69
    assert [f["check"] for f in c["failed"]] == ["mchc"]
    _, c = checked([("Total Bilirubin", "0.9", "mg/dL", "0.2 - 1.2"), ("Direct Bilirubin", "1.4", "mg/dL", "0.0 - 0.3")])
    assert [f["check"] for f in c["failed"]] == ["bilirubin"]
    _, c = checked([("Total Cholesterol", "160", "mg/dL", "< 200"), ("HDL Cholesterol", "48", "mg/dL", "40 - 60"), ("LDL Cholesterol", "142", "mg/dL", "< 100")])
    assert [f["check"] for f in c["failed"]] == ["cholesterol"]


def test_a_triglyceride_misread_above_400_still_meets_its_vldl():
    report = [(n, "780" if n == "Triglycerides" else v, u, r) for n, v, u, r in LIPID]  # 1 read as 7
    _, c = checked(report)
    assert "vldl" in [f["check"] for f in c["failed"]]
    _, c = checked([("Triglycerides", "620", "mg/dL", "< 150"), ("VLDL Cholesterol", "118", "mg/dL", "< 30")])  # measured above 400: fine
    assert c["failed"] == []


def test_a_direct_ldl_is_not_expected_to_add_up_with_vldl():
    report = [(("LDL Cholesterol (Direct)" if n == "LDL Cholesterol" else n), ("150" if n == "LDL Cholesterol" else v), u, r) for n, v, u, r in LIPID]
    _, c = checked(report)
    assert "cholesterol" not in [f["check"] for f in c["failed"]]


def test_where_the_second_engine_reading_makes_it_add_up_the_check_says_so():
    parsed = E.parse_labs(table([(n, "4360" if n == "Absolute Neutrophil Count" else v, u, r) for n, v, u, r in CBC]))
    second = E.parse_labs(table(CBC))
    rows, _ = E.cross_check(parsed, second, "docTR")
    c = E.consistency(rows)
    text = next(f["text"] for f in c["failed"] if f["check"] == "abs_neutrophils")
    assert "second OCR engine's reading of Absolute neutrophil count (4960) it adds up" in text
    assert next(r for r in rows if r["test_key"] == "abs_neutrophils")["value"] == "4360"  # nothing is corrected


def test_rounding_alone_never_fails_a_sum():
    # an analyser's one-decimal differential adds to 100.2; a globulin and A/G worked from unrounded values
    _, c = checked([("Neutrophils", "61.4", "%", ""), ("Lymphocytes", "29.3", "%", ""), ("Monocytes", "6.2", "%", ""), ("Eosinophils", "2.8", "%", ""),
                    ("Basophils", "0.5", "%", ""), ("Total Protein", "6.9", "g/dL", ""), ("Serum Albumin", "4.0", "g/dL", ""), ("Globulin", "3.0", "g/dL", ""),
                    ("A/G Ratio", "1.33", "", "")])
    assert c["failed"] == []


def test_the_note_lists_a_sum_that_does_not_add_up(client, nurse, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from app.routers import files

    def read(data, ctype, second=False, **kw):
        rows = E.parse_labs(table([(n, "2.7" if n == "Globulin" else v, u, r) for n, v, u, r in LFT]))
        return {"engine": "RapidOCR", "second_check": None, "doc_type": {"type": "lab_report", "label": "Lab report", "why": "rows"}, "medicines": [],
                "quality": {"ok": True, "issues": []}, "rows": rows, "consistency": E.consistency(rows), "meta": {}, "warnings": [], "text": [], "at": "now"}

    monkeypatch.setattr(files, "extract_document", read)
    png = cv2.imencode(".png", np.full((600, 600, 3), 240, np.uint8))[1].tobytes()
    f = client.post(f"{API}/files", files={"file": ("lft.png", io.BytesIO(png), "image/png")}, data={"kind": "report"}, headers=nurse).json()
    _, body = new_intake(client, nurse, chief_complaint="yellow eyes", file_ids=[f["id"]])
    note = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()["note"]
    flag = next(x for x in note["flags"] if x["code"] == "LAB-SUM")
    assert "Globulin is 2.7 g/dL, but total protein 6.8 − albumin 3.1 = 3.7" in flag["label"]
    glob = next(v for v in note["labs"] if v["label"] == "Globulin")
    assert glob["needs_check"] and any("total protein" in c for c in glob["checks"])
