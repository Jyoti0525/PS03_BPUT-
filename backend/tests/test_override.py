"""First-review staff can raise queue priority with a reason; nobody can manually downgrade the rules output."""
from conftest import API
from test_wednesday import NORMAL, hw, intake  # noqa: F401  (hw is a fixture)


def test_first_review_staff_can_raise_with_a_reason(client, nurse, hw):
    _, e = intake(client, nurse, chief_complaint="mild headache", vitals=NORMAL, severity=2, duration="3-7 days", exam={"done": True})
    e = client.post(f"{API}/encounters/{e['id']}/observations", json={"exam_done": True}, headers=nurse).json()
    assert e["urgency"] == "green"
    url = f"{API}/encounters/{e['id']}/override"
    assert client.post(url, json={"to_urgency": "red"}, headers=nurse).status_code == 422
    r = client.post(url, json={"to_urgency": "red", "reason": "Bedside assessment"}, headers=hw)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["urgency"] == "red" and o["override"]["direction"] == "up" and o["override"]["by_role"] == "health_worker"
    assert o["override"]["from_urgency"] == e["urgency"]


def test_manual_lowering_is_rejected_for_first_review_staff_and_doctors(client, nurse, doctor):
    _, e = intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    assert e["urgency"] == "red"
    url = f"{API}/encounters/{e['id']}/override"
    assert client.post(url, json={"to_urgency": "yellow", "reason": "Repeat ECG normal and pain reproducible."}, headers=nurse).status_code == 403
    assert client.post(url, json={"to_urgency": "yellow", "reason": "Repeat ECG normal and pain reproducible."}, headers=doctor).status_code == 403


def test_new_measurements_can_raise_above_first_review_priority(client, nurse, hw, doctor):
    _, e = intake(client, nurse, chief_complaint="mild headache", vitals=NORMAL, severity=2, duration="3-7 days", exam={"done": True})
    e = client.post(f"{API}/encounters/{e['id']}/observations", json={"exam_done": True}, headers=nurse).json()
    assert e["urgency"] == "green"
    priority = client.post(f"{API}/encounters/{e['id']}/override", json={"to_urgency": "yellow", "category": "Bedside reassessment", "reason": "Recheck for queue"}, headers=hw)
    assert priority.status_code == 200, priority.text
    updated = client.post(f"{API}/encounters/{e['id']}/observations", json={"vitals": {"spo2": 86, "pulse": 118}}, headers=nurse)
    assert updated.status_code == 200, updated.text
    enc = updated.json()
    assert enc["urgency"] == "red" and enc["urgency_source"] == "rules"
    queued = next(x for x in client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json() if x["encounter_id"] == e["id"])
    assert queued["urgency"] == "red"


def test_priority_raise_stats_show_no_manual_downgrades(client, nurse, doctor):
    _, e = intake(client, nurse, chief_complaint="Mild cough for two days")
    assert e["urgency"] != "red"
    client.post(f"{API}/encounters/{e['id']}/override", json={"to_urgency": "red", "category": "Bedside reassessment", "reason": "Breathing worsened"}, headers=nurse)
    s = client.get(f"{API}/override-stats", headers=doctor).json()
    assert s["raised"] >= 1 and s["lowered"] == 0


# ── G6 / G8: disclaimer and data origin on every record and export ─────────
def test_every_export_carries_the_disclaimer_and_data_origin(client, nurse, doctor):
    p, e = intake(client, nurse, chief_complaint="Mild cough for two days")
    assert e["data_origin"] == "SYNTHETIC"
    assert client.get("/health").json()["data_origin"] == "SYNTHETIC"
    url = f"{API}/encounters/{e['id']}/export?format="
    csv_ = client.get(url + "csv", headers=doctor).text
    assert "Not a diagnosis" in csv_ and '"data_origin","SYNTHETIC"' in csv_
    j = client.get(url + "json", headers=doctor).json()
    assert "Not a diagnosis" in j["disclaimer"] and j["data_origin"] == "SYNTHETIC"
    f = client.get(url + "fhir", headers=doctor).json()
    assert f["meta"]["tag"][0]["code"] == "synthetic"
    assert f["entry"][0]["resource"]["section"][0]["title"] == "Disclaimer"
    assert client.get(url + "pdf", headers=doctor).status_code == 200


# ── H5: a stage that fell back or failed is visible on the note ─────────
def test_note_says_which_stage_fell_back(client, nurse, doctor):
    from app import llm
    from app.triage.pipeline import processing_status

    note = {"summary": "s", "flags": [], "processing_status": processing_status([{"stage": "Report reading", "status": "failed", "detail": '"a.jpg": OCR engine not installed'}])}
    from types import SimpleNamespace

    pat = SimpleNamespace(age=40, sex="M", name="Test Person", language="en", category="normal")
    out = llm.apply(note, {"ai_assist": True}, pat) if not llm.get_settings().llm_url else note
    st = out["processing_status"]
    assert st["overall"] == "degraded" and st["stages"][0]["stage"] == "Report reading"
    if out is not note:  # no model server in tests: the AI summary stage fell back, and the reviewer is told
        assert any(s["stage"] == "AI summary" and s["status"] == "fallback" for s in st["stages"])
        assert any(f["code"] == "LLM-OFF" for f in out["flags"])
    _, e = intake(client, nurse, chief_complaint="Mild cough for two days")
    got = client.get(f"{API}/encounters/{e['id']}", headers=doctor).json()["note"]
    assert "processing_status" in got


# ── A6: a candidate pick is a person's choice, logged; nothing is merged ─────────
def test_patient_pick_is_logged_and_nothing_merges(client, nurse, doctor):
    a = client.post(f"{API}/patients", json={"name": "Asha Pick", "age": 30, "sex": "F", "language": "en", "phone": "9000011111"}, headers=nurse).json()
    b = client.post(f"{API}/patients", json={"name": "Bina Pick", "age": 60, "sex": "F", "language": "en", "phone": "9000011111"}, headers=nurse).json()
    found = client.get(f"{API}/patients?q=9000011111", headers=nurse).json()
    assert {c["patient"]["id"] for c in found} >= {a["id"], b["id"]}  # both offered; neither merged
    r = client.post(f"{API}/patients/{b['id']}/pick", json={"match_reason": "Shared household phone", "candidates": len(found)}, headers=nurse)
    assert r.status_code == 200 and r.json()["id"] == b["id"]
    log = client.get(f"{API}/audit?q=picked", headers=doctor).json()
    assert any(x["patient_code"] == b["code"] and "Shared household phone" in x["detail"] for x in log)


# ── A8: fixed units, plausible ranges, blank means not measured ─────────
def test_vitals_bounds_and_units(client, nurse):
    from conftest import DEVICE

    p, e = intake(client, nurse, chief_complaint="Fever")
    base = {"patient_id": p["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "en", "chief_complaint": "Fever",
            "symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [], "consent_id": e["consent"]["id"]}
    post = lambda v: client.post(f"{API}/encounters", json={**base, "vitals": v, "client_ref": f"a8_{id(v)}"}, headers={**nurse, "X-Device-Id": DEVICE})  # noqa: E731
    assert post({"temp_f": 38.5}).status_code == 422  # Celsius typed into the °F box: refused, not converted
    assert post({"bp_systolic": 80, "bp_diastolic": 120}).status_code == 422
    assert post({"spo2": 140}).status_code == 422
    ok = post({"pulse": 96, "temp_f": None})
    assert ok.status_code == 200
    assert not any(v["label"] == "Temperature" for v in ok.json()["note"]["vitals"])  # not measured stays absent, never a default
