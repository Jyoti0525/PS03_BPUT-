"""C3: filling in from home, arrival check-in at the desk, waiting time from arrival, and the GREEN long-wait alert."""

import uuid
from datetime import timedelta

from conftest import API
from test_kiosk import kiosk_intake, kiosk_session
from test_wednesday import NORMAL, intake

from app.db import SessionLocal
from app.models import Encounter
from app.services import now

HOME = "MKHOME"
ANY = "fac_any_centre"
Q = f"{API}/queue?facility_id=fac_phc_manikpur"
BOARD = f"{API}/facilities/fac_phc_manikpur/tokens"


def test_home_intake_waits_until_checked_in(client, doctor, supervisor):
    assert client.get(f"{API}/kiosk/{HOME}").json()["for_home"] is True
    h = kiosk_session(client, HOME)
    _, enc = kiosk_intake(client, h, "From Home", "Fever for 4 days")
    assert enc["channel"] == "home_link" and enc["status"] == "expected" and enc["token"].startswith("H-")
    assert enc["home_advice"] == "show_at_desk" and enc["urgency"] is None  # the patient never sees a tier
    assert enc["id"] not in {i["encounter_id"] for i in client.get(Q, headers=doctor).json()}  # not in the queue before arriving
    row = next(b for b in client.get(BOARD, headers=supervisor).json() if b["encounter_id"] == enc["id"])
    assert row["status"] == "expected" and row["arrived_at"] is None and row["wait_minutes"] == 0

    r = client.post(f"{API}/encounters/{enc['id']}/arrive", headers=supervisor)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["status"] == "queued" and got["token"].startswith("T-") and got["arrived_at"]
    item = next(i for i in client.get(Q, headers=doctor).json() if i["encounter_id"] == enc["id"])
    assert item["wait_minutes"] == 0 and "filled in from home" in item["order_reason"] and "since arrival" in item["order_reason"]
    assert client.post(f"{API}/encounters/{enc['id']}/arrive", headers=supervisor).status_code == 409  # only once
    assert client.post(f"{API}/encounters/{enc['id']}/arrive", headers=h).status_code == 403  # the desk checks in, not the link


def test_filling_in_early_does_not_jump_people_already_waiting(client, doctor, supervisor):
    """Sent from home hours ago, arrived now: behind a walk-in of the same tier who has been waiting 30 minutes."""
    walk = kiosk_intake(client, kiosk_session(client, "MANIKPUR"), "Waiting Since Morning", "Fever for 4 days")[1]
    home = kiosk_intake(client, kiosk_session(client, HOME), "Sent At Six", "Fever for 4 days")[1]
    with SessionLocal() as db:
        db.get(Encounter, home["id"]).created_at = now() - timedelta(hours=4)
        w = db.get(Encounter, walk["id"])
        w.arrived_at = w.created_at = now() - timedelta(minutes=30)
        db.commit()
    client.post(f"{API}/encounters/{home['id']}/arrive", headers=supervisor)
    q = [i["encounter_id"] for i in client.get(Q, headers=doctor).json()]
    assert q.index(walk["id"]) < q.index(home["id"])


def test_danger_sign_from_home_goes_to_emergency_and_to_the_doctors_now(client, doctor):
    h = kiosk_session(client, HOME)
    pat = client.post(f"{API}/patients", json={"name": "Chest Pain Home", "age": 55, "sex": "M", "language": "en"}, headers=h).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=h).json()
    r = client.post(f"{API}/encounters", headers=h, json={
        "patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "en", "chief_complaint": "Chest pain spreading to left arm",
        "symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [], "consent_id": con["id"], "client_ref": f"h_{uuid.uuid4().hex}"})
    assert r.status_code == 200, r.text
    enc = r.json()
    assert enc["home_advice"] == "emergency" and enc["urgency"] is None  # told to go now / call 108, never shown "RED"
    item = next(i for i in client.get(Q, headers=doctor).json() if i["encounter_id"] == enc["id"])
    assert item["urgency"] == "red" and item["status"] in ("queued", "escalated")


def test_green_waiting_too_long_tells_the_medical_officer_without_reordering(client, nurse, doctor):
    _, green = intake(client, nurse, chief_complaint="mild headache", vitals=NORMAL, severity=2, duration="3-7 days", exam={"done": True})
    client.post(f"{API}/encounters/{green['id']}/observations", json={"exam_done": True}, headers=nurse)  # releases the provisional YELLOW
    assert client.get(f"{API}/encounters/{green['id']}", headers=doctor).json()["urgency"] == "green"
    with SessionLocal() as db:
        db.get(Encounter, green["id"]).arrived_at = now() - timedelta(minutes=150)
        db.commit()
    q = client.get(Q, headers=doctor).json()
    item = next(i for i in q if i["encounter_id"] == green["id"])
    assert "medical officer told" in item["order_reason"]
    ranks = [{"red": 0, "yellow": 1, "green": 2}[i["urgency"]] for i in q]
    assert ranks == sorted(ranks)  # still behind every RED and YELLOW
    alert = next(a for a in client.get(f"{API}/alerts", headers=doctor).json() if a["kind"] == "long_wait" and a["status"] != "resolved")
    assert green["token"] in alert["detail"]["tokens"] and alert["to_role"] == "medical_officer"
    assert client.post(f"{API}/encounters/{green['id']}/confirm", headers=nurse).status_code == 200
    client.get(Q, headers=doctor)
    still = [a for a in client.get(f"{API}/alerts", headers=doctor).json() if a["kind"] == "long_wait" and a["status"] != "resolved"]
    assert all(green["token"] not in a["detail"]["tokens"] for a in still)


def test_supervisor_creates_a_from_home_link(client, supervisor):
    link = client.post(f"{API}/kiosk-links", json={"label": "SMS link", "for_home": True}, headers=supervisor).json()
    assert link["for_home"] is True
    assert client.get(f"{API}/kiosk/{link['code']}").json()["for_home"] is True


def test_long_waits_read_in_hours():
    from app.alerts import _mins
    assert (_mins(12), _mins(60), _mins(1653)) == ("12 min", "1 h", "27 h 33 min")


def test_finder_lists_only_from_home_links(client):
    """A patient without a code finds a facility: Jeevia ones with their from-home link, never a waiting-room link."""
    hits = client.get(f"{API}/kiosk-finder", params={"q": "manikpur"}).json()
    codes = [h["code"] for h in hits if h["code"]]
    assert codes == [HOME] and "MANIKPUR" not in codes
    assert client.get(f"{API}/kiosk-finder", params={"q": "nowhere-xyz-qq"}).json() == []
    assert client.get(f"{API}/kiosk-finder").json() == []  # nothing to search by


def test_any_centre_form_is_claimed_by_the_centre_the_patient_reaches(client, doctor):
    """Fill in without choosing a centre, get a J- reference; the desk of whichever centre the patient reaches claims it."""
    from conftest import login

    receptionist = login(client, "9000000003")
    _, enc = kiosk_intake(client, kiosk_session(client, "ANYCARE"), "Any Centre", "Fever for 4 days", ANY)
    ref = enc["token"]
    assert ref.startswith("J-") and enc["status"] == "expected" and enc["home_advice"] == "show_at_desk"
    assert enc["id"] not in {i["encounter_id"] for i in client.get(Q, headers=doctor).json()}
    assert "ANYCARE" not in {x["code"] for x in client.get(f"{API}/kiosk-finder", params={"q": "any"}).json()}
    assert client.post(f"{API}/encounters/claim", json={"reference": "J-NOPE99"}, headers=receptionist).status_code == 404
    r = client.post(f"{API}/encounters/claim", json={"reference": f"jeevia:{ref.lower()}"}, headers=receptionist)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued" and r.json()["token"].startswith("T-")
    assert enc["id"] in {i["encounter_id"] for i in client.get(Q, headers=doctor).json()}
    assert client.post(f"{API}/encounters/claim", json={"reference": ref}, headers=receptionist).status_code == 409


def test_any_centre_red_waits_for_a_centre(client):
    """No one can see an any-centre form until it is claimed, so even a RED waits (the patient is told to call 108)."""
    _, enc = kiosk_intake(client, kiosk_session(client, "ANYCARE"), "Any Red", "Snake bite on the foot one hour ago, gums bleeding", ANY)
    assert enc["status"] == "expected" and enc["token"].startswith("J-")


def test_any_centre_form_is_found_by_mobile_when_the_reference_is_lost(client):
    """The patient closed the page without noting the J- reference: the desk finds the form by the mobile number given."""
    from conftest import login

    receptionist = login(client, "9000000003")
    _, enc = kiosk_intake(client, kiosk_session(client, "ANYCARE"), "Lost Reference", "Knee pain for two months", ANY)
    assert client.post(f"{API}/encounters/claim", json={"reference": "9000011111"}, headers=receptionist).status_code == 404
    r = client.post(f"{API}/encounters/claim", json={"reference": "+91 91234 56780"}, headers=receptionist)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == enc["id"] and r.json()["token"].startswith("T-")


def test_any_centre_form_needs_a_mobile_number(client):
    """Without a number the form could not be found again if the reference is lost, so the server refuses it."""
    h = kiosk_session(client, "ANYCARE")
    pat = client.post(f"{API}/patients", json={"name": "No Phone", "age": 30, "sex": "F", "language": "or"}, headers=h).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "or", "scopes": ["triage"]}, headers=h).json()
    body = {"patient_id": pat["id"], "facility_id": ANY, "category": "normal", "language": "or", "chief_complaint": "Fever", "duration": "1-2 days", "consent_id": con["id"], "client_ref": "k_nophone"}
    assert client.post(f"{API}/encounters", json=body, headers=h).status_code == 422
