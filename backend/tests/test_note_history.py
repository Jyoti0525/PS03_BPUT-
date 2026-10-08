"""The note a doctor reads: pertinent negatives, allergies, medicines, past history, and the questions that feed them."""

from types import SimpleNamespace

from app.triage import findings, pipeline, rules

VITALS = {"bp_systolic": 120, "bp_diastolic": 80, "pulse": 80, "spo2": 98, "temp_f": 98.6, "resp_rate": 16, "avpu": "A"}


def _note(intake, age=40, sex="M"):
    t = rules.evaluate_full(intake, age, sex)
    return t, pipeline.build_note(intake=intake, patient=SimpleNamespace(name="T", age=age, sex=sex), triage=t, files=[], history=[], proxy=False)


def _a(qid, answer):
    return {"qid": qid, "question": qid, "answer": answer}


def test_not_sure_is_not_no():
    got = findings.extract({"answers": [_a("chest_radiation", "Not sure"), _a("allergy", "Not sure"), _a("long_illness", "None")]})
    assert "chest_pain_radiating" not in got and "allergy_drug" not in got and got["diabetes_known"].value is False


def test_history_block_and_summary():
    intake = {"chief_complaint": "chest pain", "selected_symptoms": ["Chest pain"], "category": "normal", "duration": "Today", "symptoms": [], "vitals": VITALS,
              "answers": [_a("chest_radiation", "No"), _a("chest_sweat", "Yes — sweating"), _a("allergy", "No known allergy"),
                          _a("long_illness", "Diabetes (sugar)"), _a("regular_meds", "Yes — other medicines")]}
    _, n = _note(intake, 52)
    h = n["history"]
    assert h["negatives"] == ["chest pain spreading to arm, jaw or back"] and h["positives"] == ["sweating with symptoms"]
    assert h["allergies"] == "no known medicine allergy" and h["past"] == ["Known diabetes"] and "names not given" in h["medicines"][0]
    s = n["summary"]
    assert "since today" in s and "Also reports" not in s and "Denies: chest pain spreading" in s and "Allergies: no known" in s


def test_allergy_not_asked_is_missing():
    _, n = _note({"chief_complaint": "cough", "category": "normal", "symptoms": [], "vitals": VITALS})
    assert n["history"]["allergies"] == "not asked" and any("allergies not recorded" in m for m in n["missing_info"])


def test_flags_are_grouped():
    intake = {"chief_complaint": "chest pain", "category": "normal", "symptoms": [], "vitals": VITALS, "captured_offline": True}
    _, n = _note(intake, 55)
    g = {f["code"]: f["group"] for f in n["flags"]}
    assert g["OFFLINE"] == "data" and any(v == "clinical" for k, v in g.items() if k != "OFFLINE")


def test_possible_ectopic_and_long_cough():
    t, _ = _note({"chief_complaint": "stomach pain", "category": "normal", "symptoms": [], "vitals": VITALS, "answers": [_a("preg_check", "Period is late — maybe")]}, 24, "F")
    assert any(h["rule_id"] == "LOCAL-POSSIBLE-ECTOPIC" for h in t["hits"]) and t["urgency"] in ("yellow", "red")
    t, _ = _note({"chief_complaint": "cough", "category": "normal", "symptoms": [], "vitals": VITALS, "answers": [_a("cough_weeks", "Yes — 2 weeks or more")]})
    assert any(h["rule_id"] == "NTEP-PRESUMPTIVE-TB" for h in t["hits"])


def test_hba1c_trend_across_visits():
    from datetime import datetime

    old = SimpleNamespace(created_at=datetime(2026, 4, 1), intake={"vitals": {}}, chief_complaint="Diabetes follow-up",
                          note={"labs": [{"label": "HbA1c", "value": "7.1"}]})
    today = SimpleNamespace(id="r", filename="a1c.pdf", kind="report", extraction={"engine": "pdf", "rows": [
        {"test": "HbA1c", "test_key": "hba1c", "value": "8.4", "value_num": 8.4, "unit": "%", "reference": "4.0–5.6", "status": "abnormal", "needs_check": False}], "meta": {}, "warnings": []})
    intake = {"chief_complaint": "Diabetes follow-up", "category": "chronic", "symptoms": [], "chronic": {"condition": "diabetes"}}
    n = pipeline.build_note(intake=intake, patient=SimpleNamespace(name="T", age=55, sex="F"), triage=rules.evaluate_full(intake, 55, "F"),
                            files=[today], history=[old], proxy=False)
    t = next(x for x in n["trend"] if x["parameter"] == "HbA1c (%)")
    assert [p["value"] for p in t["points"]] == [7.1, 8.4] and t["direction"] == "worse"
