"""PP-StructureV3 table reading as a third check on report rows (no PaddlePaddle needed: tables are given)."""

from app.triage import tables
from app.triage.extraction import Line, OcrResult, parse_labs

TABLE = [[["Test", "Result", "Unit", "Reference range"],
          ["Haemoglobin", "11.2", "g/dL", "13.0 - 17.0"],
          ["Fasting blood glucose", "142", "mg/dL", "70 - 100"],
          ["Serum creatinine", "1.1", "mg/dL", "0.7 - 1.3"]]]


def _ocr_rows(hb="11.2"):
    text = [f"Haemoglobin {hb} g/dL 13.0 - 17.0", "Fasting blood glucose 142 mg/dL 70 - 100", "Serum creatinine 1.1 mg/dL 0.7 - 1.3"]
    return parse_labs(OcrResult("RapidOCR", [Line(t, [0, 40 * i, 1000, 30], 0.95) for i, t in enumerate(text)], (1000, 200)))


def test_rows_from_a_table():
    got = {r["test_key"]: r["value_num"] for r in tables.rows_from_tables(TABLE)}
    assert len(got) == 3 and 11.2 in got.values() and 142 in got.values()


def test_same_values_agree():
    rows = _ocr_rows()
    tally = tables.check(rows, tables.rows_from_tables(TABLE))
    assert tally["agree"] == 3 and not tally["disagreements"] and all(r["table_reader"] == "agrees" for r in rows)


def test_a_different_value_is_marked_not_replaced():
    rows = _ocr_rows(hb="17.2")  # the OCR reading misread 11 as 17
    tally = tables.check(rows, tables.rows_from_tables(TABLE))
    hb = next(r for r in rows if r["value_num"] == 17.2)
    assert hb["needs_check"] and hb["table_reader"] == "differs" and "11.2" in hb["checks"][-1]
    assert len(tally["disagreements"]) == 1


def test_off_without_the_paddle_python():
    assert not tables.enabled() and tables.read_tables(b"jpeg") is None
