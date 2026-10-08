"""Review time per case is measured from the audit trail: the confirming clinician's first view to their confirmation."""

import uuid

from conftest import API, DEVICE

from app.db import SessionLocal
from app.review_time import review_times


def _case(client, nurse):
    pat = client.post(f"{API}/patients", json={"name": "Review Timer", "age": 45, "sex": "F", "language": "en"}, headers=nurse).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]},
                      headers=nurse).json()
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "en", "chief_complaint": "Fever for two days",
            "consent_id": con["id"], "client_ref": f"rt_{uuid.uuid4().hex}",
            "vitals": {"bp_systolic": 120, "bp_diastolic": 80, "pulse": 84, "spo2": 98, "resp_rate": 16, "temp_f": 100.2, "avpu": "A"}}
    r = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_view_then_confirm_is_one_timed_case(client, nurse, doctor):
    with SessionLocal() as db:
        before = review_times(db)["cases"]
    seen, unseen = _case(client, nurse), _case(client, nurse)
    client.get(f"{API}/encounters/{seen}", headers=nurse)  # a nurse's view does not start the doctor's clock
    client.get(f"{API}/encounters/{seen}", headers=doctor)
    assert client.post(f"{API}/encounters/{seen}/confirm", headers=doctor).status_code == 200
    assert client.post(f"{API}/encounters/{unseen}/confirm", headers=doctor).status_code == 200  # never opened: not counted
    with SessionLocal() as db:
        got = review_times(db)
    assert got["cases"] == before + 1 and got["confirmed_without_view"] >= 1
    case = next(c for c in got["per_case"] if c["encounter_id"] == seen)
    assert 0 <= case["seconds"] < 60 and case["by_role"] == "doctor"
