import gzip
import json
import uuid

import pytest
from conftest import API, DEVICE, login

from app import directory


def register(client, role, name, **extra):
    phone = "8" + str(uuid.uuid4().int)[:9]
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    body = {"registration_token": v["registration_token"], "name": name, "role": role, "facility_id": None, "language": "en", "accepted_terms": True, "pin": "7391", **extra}
    r = client.post(f"{API}/auth/register", json=body)
    return r, phone


def auth(r):
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


@pytest.fixture(scope="module")
def loaded_directory(client, tmp_path_factory):
    rows = [
        {"ref": "osm:n1", "name": "Primary Health Centre Balipatna", "amenity": "clinic", "healthcare": "centre", "state": "Odisha", "district": "Khordha", "pincode": "752102"},
        {"ref": "osm:n2", "name": "Sub Centre Kaimatia", "amenity": "clinic", "state": "Odisha", "district": "Khordha"},
        {"ref": "osm:n3", "name": "Apollo Hospitals", "amenity": "hospital", "operator_type": "private", "state": "Odisha", "district": "Khordha"},
        {"ref": "osm:w4", "name": "District Headquarters Hospital Puri", "amenity": "hospital", "state": "Odisha", "district": "Puri", "beds": "300"},
        {"ref": "osm:n5", "name": "", "amenity": "clinic", "state": "Odisha"},
    ]
    p = tmp_path_factory.mktemp("dir") / "snap.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    from app.db import SessionLocal

    with SessionLocal() as db:
        assert directory.load(db, p) == 4  # nameless row skipped
        assert directory.load(db, p) == 4  # idempotent upsert
    return p


def test_classification():
    assert directory.classify("Primary Health Centre Balipatna", "clinic", None) == "phc"
    assert directory.classify("Health & Wellness Centre Kaimatia", "clinic", None) == "sub_centre"
    assert directory.classify("CHC Jatni", "clinic", None) == "chc"
    assert directory.classify("District Headquarters Hospital Puri", "hospital", None) == "district_hospital"
    assert directory.classify("SCB Medical College", "hospital", None) == "medical_college"
    assert directory.classify("ESIC Dispensary", "clinic", None) == "esi"
    assert directory.classify("City Care Clinic", "clinic", None) == "clinic"
    assert directory.ownership("Apollo Hospitals", "hospital", "private") == "private"
    assert directory.ownership("Govt Hospital Jatni", "hospital", None) == "public"


def test_directory_search_and_join_activates_facility(client, loaded_directory):
    hits = [h for h in client.get(f"{API}/directory/search", params={"q": "balipatna"}).json() if h["key"] == "dir:osm:n1"]
    assert hits and hits[0]["kind"] == "phc" and hits[0]["facility_id"] is None
    assert client.get(f"{API}/directory/search", params={"q": "752102"}).json()[0]["name"].startswith("Primary Health")
    assert any(s["state"] == "Odisha" for s in client.get(f"{API}/directory/states").json())
    r, _ = register(client, "nurse", "Nurse Balipatna", registration_no="ODNC-1234", directory_ref=hits[0]["directory_ref"])
    assert r.status_code == 200, r.text
    fid = r.json()["user"]["facility_id"]
    fac = client.get(f"{API}/facilities/{fid}").json()
    assert fac["source"] == "directory" and fac["verified"] and fac["type"] == "phc" and fac["pincode"] == "752102"
    # second person joins the same activated facility, not a duplicate
    r2, _ = register(client, "doctor", "Dr Balipatna", registration_no="ODMC-5678", directory_ref=hits[0]["directory_ref"])
    assert r2.json()["user"]["facility_id"] == fid
    assert next(h for h in client.get(f"{API}/directory/search", params={"q": "balipatna"}).json() if h["key"] == "dir:osm:n1")["facility_id"] == fid


def test_workplace_is_required_and_rules(client, loaded_directory):
    r, _ = register(client, "nurse", "No Workplace", registration_no="ODNC-9999")
    assert r.status_code == 422
    r, _ = register(client, "nurse", "Adds Facility", registration_no="ODNC-9999", new_facility={"name": "PHC Missing", "type": "phc", "district": "Puri", "state": "Odisha"})
    assert r.status_code == 403  # only supervisors add missing facilities
    r, _ = register(client, "supervisor", "Sup Company", new_facility={"name": "Acme Clinic", "type": "company_clinic", "district": "Puri", "state": "Odisha"})
    assert r.status_code == 422  # organisation workplaces come from organisations
    r, _ = register(client, "employer", "HR Without Org")
    assert r.status_code == 422


def test_employer_registers_org_then_staff_join_and_fitness_flows(client, loaded_directory):
    org = {
        "name": "Tata Kalinga Test Works", "kind": "industrial", "state": "Odisha", "district": "Jajpur",
        "facility": {"name": "Tata Kalinga Plant Clinic", "type": "industrial_unit", "district": "Jajpur", "state": "Odisha", "pincode": "755026"},
    }
    r, _ = register(client, "employer", "HR Head", new_organisation=org)
    assert r.status_code == 200, r.text
    emp = auth(r)
    home = client.get(f"{API}/organisations/me", headers=emp).json()
    assert home["organisation"]["name"] == org["name"] and home["facilities"][0]["source"] == "organisation"
    fid = home["facilities"][0]["id"]

    # workplace now searchable, with the organisation name
    hit = next(h for h in client.get(f"{API}/directory/search", params={"q": "kalinga plant"}).json() if h["facility_id"] == fid)
    assert hit["organisation_name"] == org["name"]

    # roster: single + CSV import (one bad row)
    assert client.post(f"{API}/organisations/me/workers", json={"employee_code": "TK-1", "name": "Ravi Das", "age": 40, "sex": "M", "department": "Coke oven"}, headers=emp).status_code == 200
    imp = client.post(f"{API}/organisations/me/workers/import", json={"csv": "employee_code,name,age,sex,department,phone\nTK-2,Mina Sahu,31,F,Rolling mill,9123000001\nTK-3,Bad Age,abc,M,Rolling mill,\nTK-1,Ravi Kumar Das,40,M,Coke oven,"}, headers=emp).json()
    assert imp["created"] == 1 and imp["updated"] == 1 and len(imp["errors"]) == 1

    # a doctor joins the organisation's clinic and a worker checks in with their employee code
    rd, _ = register(client, "doctor", "Dr Plant", registration_no="ODMC-4321", facility_id=fid)
    doc = auth(rd)
    rn, _ = register(client, "nurse", "Nurse Plant", registration_no="ODNC-4321", facility_id=fid)
    nurse = auth(rn)
    dev = f"dev_plant_{uuid.uuid4().hex[:6]}"
    client.post(f"{API}/devices", json={"label": "Plant tablet", "device_id": dev}, headers=nurse)
    wrong = client.post(f"{API}/patients", json={"name": "Somebody Else", "age": 30, "sex": "M", "employee_code": "TK-2"}, headers=nurse)
    assert wrong.status_code == 409
    p = client.post(f"{API}/patients", json={"name": "Mina Sahu", "age": 31, "sex": "F", "employee_code": "TK-2"}, headers=nurse).json()
    assert p["employee_code"] == "TK-2" and p["organisation_id"]
    con = client.post(f"{API}/consents", json={"patient_id": p["id"], "mode": "self", "privacy_context": "private", "language": "or", "scopes": ["triage"]}, headers=nurse).json()
    enc = client.post(f"{API}/encounters", json={"patient_id": p["id"], "facility_id": fid, "category": "normal", "language": "or", "chief_complaint": "Heat exhaustion at work", "consent_id": con["id"], "client_ref": f"w_{uuid.uuid4().hex}"}, headers={**nurse, "X-Device-Id": dev}).json()
    full = client.get(f"{API}/encounters/{enc['id']}", headers=doc).json()
    assert full["worker"]["employee_code"] == "TK-2" and full["worker"]["latest"] is None
    assert client.post(f"{API}/encounters/{enc['id']}/fitness", json={"status": "temporarily_unfit", "valid_until": "2026-10-10"}, headers=nurse).status_code == 403
    f = client.post(f"{API}/encounters/{enc['id']}/fitness", json={"status": "temporarily_unfit", "restrictions": "Rest from furnace duty", "valid_until": "2026-10-10"}, headers=doc)
    assert f.status_code == 200, f.text

    # employer sees the outcome and nothing clinical
    ws = {w["employee_code"]: w for w in client.get(f"{API}/organisations/me/workers", headers=emp).json()}
    assert ws["TK-2"]["fitness_status"] == "temporarily_unfit" and ws["TK-1"]["fitness_status"] == "pending_review"
    assert "chief_complaint" not in str(ws)
    cohorts = client.get(f"{API}/employer/cohorts", headers=emp).json()
    assert {c["name"] for c in cohorts} == {"Coke oven", "Rolling mill"}
    assert client.get(f"{API}/encounters/{enc['id']}", headers=emp).status_code == 403
    # removing a worker keeps the health record
    assert client.patch(f"{API}/organisations/me/workers/TK-1", json={"active": False}, headers=emp).status_code == 200
    assert "TK-1" not in {w["employee_code"] for w in client.get(f"{API}/organisations/me/workers", headers=emp).json()}


def test_supervisor_manages_staff(client, supervisor):
    r, _ = register(client, "nurse", "Temp Nurse", registration_no="UPNC-7777", facility_id="fac_phc_manikpur")
    nurse = auth(r)
    uid = r.json()["user"]["id"]
    assert client.patch(f"{API}/users/{uid}", json={"role": "doctor"}, headers=nurse).status_code == 403
    up = client.patch(f"{API}/users/{uid}", json={"role": "receptionist"}, headers=supervisor).json()
    assert up["role"] == "receptionist"
    assert client.patch(f"{API}/users/{uid}", json={"is_active": False}, headers=supervisor).json()["is_active"] is False
    assert client.get(f"{API}/auth/me", headers=nurse).status_code == 401  # sessions end immediately
    me = client.get(f"{API}/auth/me", headers=supervisor).json()
    assert client.patch(f"{API}/users/{me['id']}", json={"is_active": False}, headers=supervisor).status_code == 422


def test_patient_correction(client, doctor, supervisor):
    radha = client.get(f"{API}/patients/by-code/JVA-P001", headers=doctor).json()
    r = client.patch(f"{API}/patients/{radha['id']}", json={"age": 43, "village": "Manikpur East"}, headers=supervisor)
    assert r.status_code == 200 and r.json()["age"] == 43
    log = client.get(f"{API}/audit", params={"q": "corrected"}, headers=supervisor).json()
    assert any("age" in a["detail"] and "village" in a["detail"] for a in log)


def test_otp_request_limits(client):
    phone = "7" + str(uuid.uuid4().int)[:9]
    codes = [client.post(f"{API}/auth/otp/request", json={"phone": phone}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert all(client.post(f"{API}/auth/otp/request", json={"phone": "9000000001"}).status_code == 200 for _ in range(4))  # sample accounts exempt


def test_otp_per_network_limit(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "otp_per_ip_hour", 0)
    r = client.post(f"{API}/auth/otp/request", json={"phone": "9000000001"})
    assert r.status_code == 429 and "network" in r.json()["detail"]


def test_login_helper_still_works(client):
    assert login(client, "9000000002")
    assert DEVICE


def test_pin_setup_forgot_and_supervisor_reset(client, supervisor):
    r, phone = register(client, "doctor", "Dr Reset", registration_no="UPMC-2222", facility_id="fac_phc_manikpur")
    uid = r.json()["user"]["id"]
    assert client.post(f"{API}/users/{uid}/reset-pin", headers=auth(r)).status_code == 403  # doctors can't
    assert client.post(f"{API}/users/{uid}/reset-pin", headers=supervisor).status_code == 204
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    assert v["status"] == "pin_setup_required"
    assert client.post(f"{API}/auth/pin/setup", json={"pin_token": v["pin_token"], "pin": "1111"}).status_code == 422
    assert client.post(f"{API}/auth/pin/setup", json={"pin_token": v["pin_token"], "pin": "5820"}).status_code == 200
    assert client.post(f"{API}/auth/pin/setup", json={"pin_token": v["pin_token"], "pin": "5821"}).status_code == 409  # already set
    # a supervisor may reset their own PIN after OTP
    rs, sphone = register(client, "supervisor", "Sup Forgot", facility_id="fac_phc_manikpur")
    ch = client.post(f"{API}/auth/otp/request", json={"phone": sphone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    assert v["can_reset_pin"] is True
    f = client.post(f"{API}/auth/pin/forgot", json={"pin_token": v["pin_token"]}).json()
    assert f["status"] == "pin_setup_required"
    assert client.post(f"{API}/auth/pin/setup", json={"pin_token": f["pin_token"], "pin": "6093"}).status_code == 200


def test_documents_only_for_treating_clinicians(client, doctor, nurse, supervisor, patient):
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()
    eid = next(i["encounter_id"] for i in q if i["patient_name"] == "Radha Kumari")
    fid = client.get(f"{API}/encounters/{eid}", headers=doctor).json()["intake"]["file_ids"][0]
    assert client.get(f"{API}/files/{fid}", headers=doctor).status_code == 200
    assert client.get(f"{API}/files/{fid}", headers=nurse).status_code == 200
    rec = login(client, "9000000003")  # receptionist, same facility
    assert client.get(f"{API}/files/{fid}", headers=rec).status_code == 403
    assert client.get(f"{API}/files/{fid}", headers=supervisor).status_code == 403
    assert client.get(f"{API}/files/{fid}", headers=patient).status_code == 403  # Radha's file, not Priya's
    r, _ = register(client, "doctor", "Dr Elsewhere", registration_no="ODMC-8888", new_facility=None, facility_id="fac_kalinganagar")
    assert client.get(f"{API}/files/{fid}", headers=auth(r)).status_code == 403  # another facility
    views = client.get(f"{API}/audit", params={"action": "VIEW", "q": "Document opened"}, headers=doctor).json()
    assert views, "document views are audited"
