"""A returning patient: the note sets the last visit beside this one (what changed in between), and the presenting
complaint comes as label/value rows instead of a paragraph."""

from conftest import API
from test_wednesday import DEVICE, NORMAL, intake  # noqa: F401


def test_second_visit_is_compared_with_the_first(client, nurse):
    pat, first = intake(client, nurse, chief_complaint="Fever for two days", vitals=NORMAL, severity=4, duration="1-2 days")
    assert first["note"]["since_last"] is None
    rows = {r["label"]: r["value"] for r in first["note"]["presenting"]}
    assert rows["Complaint"] == "Fever for two days" and rows["Severity"].startswith("4/10")
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=nurse).json()
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "en",
            "chief_complaint": "Cough and fever", "symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [],
            "vitals": {**NORMAL, "temp_f": 102.2}, "consent_id": con["id"], "client_ref": "w_second_visit", "severity": 6}
    r = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE})
    assert r.status_code == 200, r.text
    s = r.json()["note"]["since_last"]
    assert s["encounter_id"] == first["id"] and s["complaint"] == "Fever for two days" and s["days_ago"] == 0
    assert s["urgency"] == first["urgency"]
    assert any(v["now"] != v["then"] for v in s["vitals"]), s["vitals"]
