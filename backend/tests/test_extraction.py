"""Document extraction: synthetic slips only (SVG text layer, and a rendered photo for real OCR)."""

import io

import pytest

from app.triage.extraction import document_checks, extract_document, lab_values, match_test, ocr_available
from app.triage.reports import render


def test_test_name_matching_handles_ocr_slips():
    assert match_test("HbAlc")[0].key == "hba1c"  # 1 read as l
    assert match_test("SerumPotassium")[0].key == "potassium"  # spaces dropped
    assert match_test("Fasting Blood Sugar")[0].key == "glucose_fasting"
    assert match_test("Patient: Asha") is None


def test_svg_sample_is_read_from_the_file_itself():
    ex = extract_document(render("cbc", "Asha Devi")[0].encode(), "image/svg+xml")
    assert ex["engine"].startswith("SVG text layer")
    rows = {r["test_key"]: r for r in ex["rows"]}
    assert rows["haemoglobin"]["value"] == "9.4" and rows["haemoglobin"]["status"] == "abnormal"
    assert rows["platelets"]["value_num"] == 96000 and rows["platelets"]["status"] == "abnormal"
    assert all(r["bbox"] and 0 <= r["bbox"][1] <= 1 for r in ex["rows"])


def test_dipstick_and_bp_from_anc_card():
    ex = extract_document(render("anc", "Asha Devi")[0].encode(), "image/svg+xml")
    rows = {r["test_key"]: r for r in ex["rows"]}
    assert rows["bp"]["values"] == {"systolic": 150, "diastolic": 98}
    assert rows["urine_albumin"]["value"] == "2+" and lab_values([ex])["urine_albumin"] == 2


def test_name_mismatch_and_stale_report_are_flagged():
    from datetime import date

    warns = document_checks({"date": "2026-01-02", "patient_name": "Asha Devi"}, "Ritu Kumari", today=date(2026, 10, 3))
    assert any("days old" in w for w in warns) and any("does not match" in w for w in warns)
    assert document_checks({"date": "2026-10-01", "patient_name": "Asha Devi"}, "Asha Devi", today=date(2026, 10, 3)) == []


def test_unreadable_file_never_raises():
    ex = extract_document(b"not an image", "image/png")
    assert ex["rows"] == [] and ex["warnings"]


@pytest.mark.skipif(not ocr_available(), reason="RapidOCR not installed")
def test_real_ocr_on_a_rendered_slip():
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default(size=22)
    im = Image.new("RGB", (900, 400), "white")
    d = ImageDraw.Draw(im)
    d.text((40, 30), "Patient: Test Person   Date: 01/10/2026", font=font, fill="black")
    for i, (t, v, r) in enumerate([("Serum Potassium", "5.9 mmol/L", "3.5-5.1"), ("Haemoglobin", "9.4 g/dL", "13.0-17.0")]):
        y = 120 + i * 60
        d.text((40, y), t, font=font, fill="black")
        d.text((420, y), v, font=font, fill="black")
        d.text((640, y), r, font=font, fill="black")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    ex = extract_document(buf.getvalue(), "image/png")
    assert ex["engine"].startswith("RapidOCR")
    vals = lab_values([ex])
    assert vals.get("potassium") == 5.9 and vals.get("haemoglobin") == 9.4
