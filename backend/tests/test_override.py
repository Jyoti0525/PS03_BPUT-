"""E9: raising the urgency is free; lowering it needs a doctor and a reason; the rules' output stays; rates per rule."""
from conftest import API
from test_wednesday import hw, intake  # noqa: F401  (hw is a fixture)


def test_any_reviewer_can_raise_without_a_reason(client, nurse, hw):
    _, e = intake(client, nurse, chief_complaint="Mild cough for two days")
    assert e["urgency"] != "red"
    r = client.post(f"{API}/encounters/{e['id']}/override", json={"to_urgency": "red"}, headers=hw)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["urgency"] == "red" and o["override"]["direction"] == "up" and o["override"]["by_role"] == "health_worker"
    assert o["override"]["from_urgency"] == e["urgency"]


def test_lowering_needs_a_doctor_and_a_reason(client, nurse, doctor):
    _, e = intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    assert e["urgency"] == "red"
    url = f"{API}/encounters/{e['id']}/override"
    assert client.post(url, json={"to_urgency": "yellow", "reason": "Repeat ECG normal and pain reproducible."}, headers=nurse).status_code == 403
    assert client.post(url, json={"to_urgency": "yellow", "reason": "ok"}, headers=doctor).status_code == 422
    assert client.post(url, json={"to_urgency": "red"}, headers=doctor).status_code == 400  # no change
    o = client.post(url, json={"to_urgency": "yellow", "reason": "Repeat ECG normal and pain reproducible."}, headers=doctor).json()
    assert o["override"]["direction"] == "down" and o["override"]["from_urgency"] == "red"
    assert any(h["urgency"] == "red" for h in o["note"]["rules_fired"])  # locked flags stay on record
    assert o["override"]["overruled_non_downgradable"]


def test_override_rate_per_rule(client, nurse, doctor):
    _, e = intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    client.post(f"{API}/encounters/{e['id']}/override", json={"to_urgency": "green", "reason": "Musculoskeletal pain, reproducible on palpation."}, headers=doctor)
    s = client.get(f"{API}/override-stats", headers=doctor).json()
    assert s["lowered"] >= 1 and s["overrides"] >= s["lowered"]
    red = [r for r in s["rules"] if r["urgency"] == "red" and r["lowered"]]
    assert red and 0 < red[0]["lowered_rate"] <= 1


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
