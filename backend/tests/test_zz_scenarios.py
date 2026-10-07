"""The demo scenarios (app/scenarios.py) load once and each gives its demo moment. Runs last: it adds data."""

import uuid

from conftest import API, login


def test_scenarios_load_once_and_each_demo_moment_works(client, employer):
    from app.db import SessionLocal
    from app.models import User
    from app.scenarios import call_scenarios, scenarios

    with SessionLocal() as db:
        assert scenarios(db) is True
        assert scenarios(db) is False
        assert call_scenarios(db) is True
        assert call_scenarios(db) is False

    # D3: one more fever from Hostel Block C at the campus raises the alert to the campus MO
    mo, nurse = login(client, "9000000008"), login(client, "9000000009")
    assert not any(a["kind"] == "fever_cluster" for a in client.get(f"{API}/alerts", headers=mo).json())
    pat = client.post(f"{API}/patients", json={"name": "Student Live", "age": 20, "sex": "F", "language": "en"}, headers=nurse).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=nurse).json()
    body = {"patient_id": pat["id"], "facility_id": "fac_campus_demo", "category": "normal", "language": "en", "chief_complaint": "Fever and headache since last night",
            "cluster_key": "Hostel Block C", "consent_id": con["id"], "client_ref": f"z_{uuid.uuid4().hex}"}
    assert client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": "dev_kiosk_campus_1"}).status_code == 200
    a = next(a for a in client.get(f"{API}/alerts", headers=mo).json() if a["kind"] == "fever_cluster")
    assert a["key"] == "Hostel Block C" and a["detail"]["cases_72h"] == 5 and a["detail"]["baseline_14d"] == 1

    # D4: Sunita's missed check-up is on ASHA Kamla Devi's list with a neutral call script
    hw, mo = login(client, "9000000006"), login(client, "9000000007")
    f = next(x for x in client.get(f"{API}/followups", headers=hw).json() if x["patient_name"] == "Sunita Kewat")
    assert f["status"] == "missed" and f["phone_belongs_to"] == "husband" and "pregnan" not in f["call_script"].lower()

    # E6: Rina's reminder call is due and the agent may make it; "headache" ends the call and pages a person.
    # Kusum's last visit was RED, so the agent may not call her.
    rows = {x["patient_name"]: x for x in client.get(f"{API}/followups", headers=hw).json()}
    rina, ram, kusum = rows["Rina Majhi"], rows["Ramprasad Sahu"], rows["Kusum Behera"]
    assert rina["status"] == ram["status"] == "call_due" and rina["who_calls"]["who"] == ram["who_calls"]["who"] == "agent"
    assert ram["programme"] == "chronic" and kusum["who_calls"]["who"] == "human" and "RED" in kusum["who_calls"]["why"]
    assert client.post(f"{API}/followups/{kusum['id']}/calls", json={}, headers=hw).status_code == 409
    call = client.post(f"{API}/followups/{rina['id']}/calls", json={}, headers=hw).json()
    assert call["language"] == "or" and "ନମସ୍କାର" in call["turns"][0]["text"]
    for said in ("ହଁ", "ହଁ", "ନା"):  # it's me; I can come; no bleeding
        call = client.post(f"{API}/calls/{call['id']}/answer", json={"text": said}, headers=hw).json()
    assert call["turns"][-1]["key"] == "headache"
    call = client.post(f"{API}/calls/{call['id']}/answer", json={"text": "Yes, I have a headache since yesterday", "original_text": "ହଁ, କାଲିଠୁ ମୁଣ୍ଡବିନ୍ଧା"}, headers=hw).json()
    assert call["outcome"] == "danger_sign" and call["turns"][-1]["key"] == "end_danger"
    a = next(a for a in client.get(f"{API}/alerts", headers=mo).json() if a["kind"] == "call_escalation" and a["key"] == rina["id"])
    assert a["status"] == "open" and "headache" in a["title"].lower()

    # C3: marking one of the two doctors off duty tips PHC Manikpur over capacity
    doc = login(client, "9000000001")
    for i in client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doc).json():  # earlier tests left REDs open
        if i["urgency"] == "red" and i["patient_code"] not in ("JVA-P001", "JVA-P202"):
            client.post(f"{API}/encounters/{i['encounter_id']}/confirm", headers=doc)
    before = client.get(f"{API}/capacity", headers=doc).json()
    assert before["over"] is False and before["doctors_on_duty"] == 2 and 1 <= before["open_red"] <= 2  # Ramesh, and Radha unless a test confirmed her
    with SessionLocal() as db:
        db.get(User, "usr_doc1").on_duty = False
        db.commit()
    try:
        cap = client.get(f"{API}/capacity", headers=doc).json()
        assert cap["doctors_on_duty"] == 1 and cap["over"] is (cap["open_red"] == 2)
    finally:
        with SessionLocal() as db:
            db.get(User, "usr_doc1").on_duty = True
            db.commit()

    # D2: the crusher department stands out; the FEV1 decline is measured against last year's test
    rates = {d["department"]: d for d in client.get(f"{API}/employer/department-rates", headers=employer).json()["departments"]}
    assert rates["Crusher"]["screened"] == 6 and rates["Crusher"]["above_others"] and rates["Crusher"]["ppe_gap_pct"] == 50
    assert rates["Furnace"]["screened"] == 6 and rates["Stores"]["screened"] == 5
    ksw = login(client, "9000000010")
    q = client.get(f"{API}/queue?facility_id=fac_kalinganagar", headers=ksw).json()
    tiers = {i["patient_code"]: i["urgency"] for i in q}
    assert tiers["JVA-KSW-2102"] == "red" and tiers["JVA-KSW-2103"] == "yellow"
    e = next(i for i in q if i["patient_code"] == "JVA-KSW-2103")
    note = client.get(f"{API}/encounters/{e['encounter_id']}", headers=ksw).json()["note"]
    assert any(h["rule_id"] == "OCC-FEV1-DECLINE" and "3.6 L" in h["evidence"][0] for h in note["rules_fired"])
