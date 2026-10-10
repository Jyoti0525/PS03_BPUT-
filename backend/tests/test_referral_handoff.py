"""Doctor-to-doctor referral across facilities, and escalations that follow the case.

A referral names its receiving facility (on Jeevia, or a national directory entry that becomes one on send). Doctors
there see it under Incoming, find it by its ID, open that visit only (audited in both facilities) and record the
arrival, which closes it on both sides. A doctor at any third facility sees nothing, not even that the ID exists.
"""

import uuid
from datetime import timedelta

from conftest import API, DEVICE
from test_api import new_intake

from app.db import SessionLocal
from app.models import AuditEvent, DirectoryFacility, Encounter, Facility, User
from app.security import issue_tokens
from app.services import now


def receiving_hospital() -> str:
    with SessionLocal() as db:
        if not db.get(Facility, "fac_test_dh"):
            db.add(Facility(id="fac_test_dh", name="District Hospital Test", type="district_hospital", district="Gorakhpur", state="Uttar Pradesh",
                            languages=["hi"], specialists=[], source="sample"))
            db.commit()
    return "fac_test_dh"


def staff_at(facility_id: str, role: str = "doctor") -> dict:
    with SessionLocal() as db:
        u = User(phone="6" + str(uuid.uuid4().int)[:9], name=f"Dr. Test {uuid.uuid4().hex[:4]}", role=role, facility_id=facility_id)
        db.add(u)
        db.commit()
        return {"Authorization": f"Bearer {issue_tokens(u)['access_token']}"}


def new_case(client, nurse) -> dict:
    _, body = new_intake(client, nurse)
    return client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()


REF = {"specialty": "Cardiology", "reason": "Chest pain, needs ECG and troponin", "transport": "ambulance_108", "note_text": "Referral note text body"}


def test_destinations_list_facilities_on_jeevia_and_the_national_directory(client, doctor):
    with SessionLocal() as db:
        if not db.query(DirectoryFacility).filter_by(ref="osm:refdest1").first():
            db.add(DirectoryFacility(ref="osm:refdest1", name="Sub Divisional Hospital Nimapara", kind="sub_district_hospital", state="Odisha", district="Puri"))
            db.commit()
    receiving_hospital()
    all_on = client.get(f"{API}/referral-destinations", headers=doctor).json()
    ids = {d["facility_id"] for d in all_on}
    assert "fac_test_dh" in ids and "fac_phc_manikpur" not in ids  # never the doctor's own facility
    assert all(d["on_jeevia"] for d in all_on)
    hits = client.get(f"{API}/referral-destinations?q=nimapara", headers=doctor).json()
    d = next(h for h in hits if h["directory_ref"] == "osm:refdest1")
    assert d["on_jeevia"] is False and d["facility_id"] is None and d["kind_label"].startswith("Sub-district")
    assert client.get(f"{API}/referral-destinations", headers=staff_at("fac_phc_manikpur", "nurse")).status_code == 403


def test_referral_reaches_the_receiving_doctor_and_only_them(client, nurse, doctor):
    receiving_hospital()
    enc = new_case(client, nurse)
    sent = client.post(f"{API}/encounters/{enc['id']}/referrals", json={**REF, "destination": "District Hospital Gorakhpur", "to_facility_id": "fac_test_dh"}, headers=doctor)
    assert sent.status_code == 200, sent.text
    r = sent.json()
    assert r["to_facility_id"] == "fac_test_dh" and r["from_facility_id"] == "fac_phc_manikpur" and r["id"].startswith("ref_")

    there, elsewhere = staff_at("fac_test_dh"), staff_at("fac_kalinganagar")
    # Incoming list and search by ID at the receiving facility
    assert r["id"] in [x["id"] for x in client.get(f"{API}/referrals/incoming", headers=there).json()]
    found = client.get(f"{API}/referrals/ {r['id']} ".replace(" ", "%20"), headers=there)
    assert found.status_code == 200 and found.json()["patient_code"] == enc["patient"]["code"]
    short = "REF-" + r["id"].removeprefix("ref_")[-6:].upper()  # as printed on the slip
    assert client.get(f"{API}/referrals/{short}", headers=there).json()["id"] == r["id"]
    assert client.get(f"{API}/referrals/{short}", headers=elsewhere).status_code == 404
    # The referred visit only: no phone number or village, and the opening is audited at both facilities
    visit = client.get(f"{API}/referrals/{r['id']}/visit", headers=there)
    assert visit.status_code == 200
    v = visit.json()
    assert v["encounter"]["chief_complaint"] == enc["chief_complaint"] and v["referral"]["id"] == r["id"]
    assert "phone" not in v["patient"] and "village" not in v["patient"]
    with SessionLocal() as db:
        opened = db.query(AuditEvent).filter(AuditEvent.resource_id == r["id"], AuditEvent.action == "VIEW").all()
        assert {a.facility_id for a in opened} == {"fac_phc_manikpur", "fac_test_dh"}
    # The receiving facility's medical officer is alerted
    mo = staff_at("fac_test_dh", "medical_officer")
    assert any(a["kind"] == "referral_in" and a["detail"]["referral_id"] == r["id"] for a in client.get(f"{API}/alerts", headers=mo).json())

    # A third facility: not found, whatever it tries, and it is not in its list
    for path in (f"/referrals/{r['id']}", f"/referrals/{r['id']}/visit"):
        assert client.get(f"{API}{path}", headers=elsewhere).status_code == 404
    assert client.post(f"{API}/referrals/{r['id']}/arrived", json={}, headers=elsewhere).status_code == 404
    assert r["id"] not in [x["id"] for x in client.get(f"{API}/referrals/incoming", headers=elsewhere).json()]
    # The sender cannot record the arrival on the receiver's behalf through this route
    assert client.post(f"{API}/referrals/{r['id']}/arrived", json={}, headers=doctor).status_code == 403

    # Arrival closes it on both sides
    done = client.post(f"{API}/referrals/{r['id']}/arrived", json={"note": "Seen in casualty"}, headers=there)
    assert done.status_code == 200 and done.json()["status"] == "received" and done.json()["received_via"] == "account"
    sender_view = next(x for x in client.get(f"{API}/referrals", headers=doctor).json() if x["id"] == r["id"])
    assert sender_view["status"] == "received" and "Dr. Test" in sender_view["received_by"]
    assert not any(a["kind"] == "referral_in" and a["detail"]["referral_id"] == r["id"] and a["status"] != "resolved" for a in client.get(f"{API}/alerts", headers=mo).json())
    assert client.post(f"{API}/referrals/{r['id']}/arrived", json={}, headers=there).status_code == 409


def test_directory_destination_becomes_a_facility_that_can_receive(client, nurse, doctor):
    with SessionLocal() as db:
        if not db.query(DirectoryFacility).filter_by(ref="osm:refdest2").first():
            db.add(DirectoryFacility(ref="osm:refdest2", name="Community Health Centre Delang", kind="chc", state="Odisha", district="Puri"))
            db.commit()
    enc = new_case(client, nurse)
    r = client.post(f"{API}/encounters/{enc['id']}/referrals", json={**REF, "destination": "Community Health Centre Delang", "to_directory_ref": "osm:refdest2"}, headers=doctor).json()
    with SessionLocal() as db:
        f = db.query(Facility).filter_by(directory_ref="osm:refdest2").one()
        assert r["to_facility_id"] == f.id and f.source == "directory"
    assert r["id"] in [x["id"] for x in client.get(f"{API}/referrals/incoming", headers=staff_at(f.id)).json()]
    # Picking it again reuses the same facility
    enc2 = new_case(client, nurse)
    r2 = client.post(f"{API}/encounters/{enc2['id']}/referrals", json={**REF, "destination": "CHC Delang", "to_directory_ref": "osm:refdest2"}, headers=doctor).json()
    assert r2["to_facility_id"] == f.id


def test_typed_destination_still_works_and_own_facility_is_refused(client, nurse, doctor):
    enc = new_case(client, nurse)
    r = client.post(f"{API}/encounters/{enc['id']}/referrals", json={**REF, "destination": "Tele-consultation (eSanjeevani hub)"}, headers=doctor)
    assert r.status_code == 200 and r.json()["to_facility_id"] is None
    enc2 = new_case(client, nurse)
    assert client.post(f"{API}/encounters/{enc2['id']}/referrals", json={**REF, "destination": "Here", "to_facility_id": "fac_phc_manikpur"}, headers=doctor).status_code == 400
    assert client.post(f"{API}/encounters/{enc2['id']}/referrals", json={**REF, "destination": "Nowhere", "to_facility_id": "fac_nope"}, headers=doctor).status_code == 404


# ── Escalations ───────────────────────────────────────
def _red_case(client, nurse, doctor) -> dict:
    enc = new_case(client, nurse)
    if enc["urgency"] != "red":
        client.post(f"{API}/encounters/{enc['id']}/override", json={"to_urgency": "red", "category": "clinical_judgement", "reason": "raised for the test"}, headers=doctor)
    return enc


def _past_due(eid: str) -> None:
    with SessionLocal() as db:
        e = db.get(Encounter, eid)
        e.escalation_due_at = now() - timedelta(minutes=1)
        db.commit()


def test_a_red_case_someone_only_opened_still_escalates(client, nurse, doctor):
    enc = _red_case(client, nurse, doctor)
    assert client.get(f"{API}/encounters/{enc['id']}", headers=nurse).json()["status"] == "in_review"  # looked at, not decided
    _past_due(enc["id"])
    esc = [x for x in client.get(f"{API}/escalations", headers=doctor).json() if x["encounter_id"] == enc["id"]]
    assert len(esc) == 1 and esc[0]["auto"] and esc[0]["status"] == "open"
    assert len([x for x in client.get(f"{API}/escalations", headers=doctor).json() if x["encounter_id"] == enc["id"]]) == 1  # raised once


def test_a_decision_closes_open_escalations(client, nurse, doctor):
    enc = _red_case(client, nurse, doctor)
    assert client.post(f"{API}/encounters/{enc['id']}/escalations", json={"to_role": "senior_mo", "reason": "Needs a senior look"}, headers=nurse).status_code == 200
    assert client.post(f"{API}/encounters/{enc['id']}/confirm", headers=doctor).status_code == 200
    esc = [x for x in client.get(f"{API}/escalations", headers=doctor).json() if x["encounter_id"] == enc["id"]]
    assert esc and all(x["status"] == "acknowledged" and x["ack_note"].startswith("Closed: note confirmed") for x in esc)

    enc2 = _red_case(client, nurse, doctor)
    receiving_hospital()
    client.post(f"{API}/encounters/{enc2['id']}/escalations", json={"to_role": "senior_mo", "reason": "Needs a senior look"}, headers=nurse)
    client.post(f"{API}/encounters/{enc2['id']}/referrals", json={**REF, "destination": "District Hospital Gorakhpur", "to_facility_id": "fac_test_dh"}, headers=doctor)
    assert all(x["status"] == "acknowledged" for x in client.get(f"{API}/escalations", headers=doctor).json() if x["encounter_id"] == enc2["id"])


def test_override_timer_counts_from_arrival(client, nurse, doctor):
    enc = new_case(client, nurse)
    with SessionLocal() as db:
        e = db.get(Encounter, enc["id"])
        e.created_at = now() - timedelta(hours=3)  # form filled at home hours earlier
        e.arrived_at = now()
        if e.urgency == "red":
            e.urgency = "yellow"
        db.commit()
    client.post(f"{API}/encounters/{enc['id']}/override", json={"to_urgency": "red", "category": "clinical_judgement", "reason": "looks worse"}, headers=doctor)
    with SessionLocal() as db:
        due = db.get(Encounter, enc["id"]).escalation_due_at
    assert due.replace(tzinfo=None) > (now() + timedelta(minutes=10)).replace(tzinfo=None)  # 15 min from arrival, not already past
