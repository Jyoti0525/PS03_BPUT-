import uuid

from conftest import API


def kiosk_session(client, code):
    r = client.post(f"{API}/kiosk/{code}/session", json={"device_id": f"tab-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def kiosk_intake(client, h, name="Kiosk Walk-in", complaint="Fever for 4 days"):
    pat = client.post(f"{API}/patients", json={"name": name, "age": 30, "sex": "F", "phone": "9123456780", "language": "hi"}, headers=h)
    assert pat.status_code == 200, pat.text
    pat = pat.json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "hi", "scopes": ["triage"]}, headers=h).json()
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "hi", "chief_complaint": complaint, "duration": "3-7 days", "consent_id": con["id"], "client_ref": f"k_{uuid.uuid4().hex}"}
    r = client.post(f"{API}/encounters", json=body, headers=h)
    assert r.status_code == 200, r.text
    return pat, r.json()


def test_public_kiosk_intake_gets_token_and_reaches_queue(client, doctor, supervisor):
    info = client.get(f"{API}/kiosk/manikpur").json()  # codes are case-insensitive
    assert info["facility_name"] == "PHC Manikpur"
    h = kiosk_session(client, "MANIKPUR")
    _, enc = kiosk_intake(client, h)
    assert enc["token"].startswith("T-") and enc["channel"] == "kiosk_link"
    assert enc["urgency"] is None and enc["note"] is None  # kiosk never sees triage output
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()
    item = next(i for i in q if i["encounter_id"] == enc["id"])
    assert item["token"] == enc["token"] and item["urgency"] == "yellow"  # ATP-FEVER-02
    board = client.get(f"{API}/facilities/fac_phc_manikpur/tokens", headers=supervisor).json()
    row = next(b for b in board if b["encounter_id"] == enc["id"])
    assert row["token"] == enc["token"] and "urgency" not in row and "chief_complaint" not in row


def test_tokens_increment_per_facility(client):
    h = kiosk_session(client, "MANIKPUR")
    _, a = kiosk_intake(client, h, "Token A")
    _, b = kiosk_intake(client, h, "Token B")
    assert int(b["token"][2:]) == int(a["token"][2:]) + 1


def test_kiosk_role_is_intake_only(client, doctor):
    h = kiosk_session(client, "MANIKPUR")
    eid = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()[0]["encounter_id"]
    assert client.get(f"{API}/encounters/{eid}", headers=h).status_code == 403
    assert client.get(f"{API}/patients?q=Radha", headers=h).status_code == 403
    assert client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=h).status_code == 403
    assert client.get(f"{API}/audit", headers=h).status_code == 403


def test_returning_patient_needs_id_and_phone(client):
    h = kiosk_session(client, "MANIKPUR")
    ok = client.post(f"{API}/kiosk/identify", json={"patient_code": "JVA-P003", "phone": "9876543210"}, headers=h)
    assert ok.status_code == 200 and ok.json()["name"] == "Priya Sharma"
    assert client.post(f"{API}/kiosk/identify", json={"patient_code": "JVA-P003", "phone": "9000000000"}, headers=h).status_code == 404


def test_admin_creates_and_revokes_links(client, supervisor, doctor):
    link = client.post(f"{API}/kiosk-links", json={"label": "Camp tablet"}, headers=supervisor).json()
    assert link["url"].endswith(f"/k/{link['code']}") and len(link["code"]) == 8
    assert client.post(f"{API}/kiosk-links", json={"label": "x" * 3}, headers=doctor).status_code == 403
    h = kiosk_session(client, link["code"])
    assert client.delete(f"{API}/kiosk-links/{link['id']}", headers=supervisor).status_code == 204
    assert client.get(f"{API}/kiosk/{link['code']}").status_code == 404
    assert client.post(f"{API}/patients", json={"name": "After revoke", "age": 30, "sex": "M"}, headers=h).status_code == 401  # open sessions end too


def test_supervisor_can_create_facility_at_registration(client):
    phone = "6" + str(uuid.uuid4().int)[:9]
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    r = client.post(f"{API}/auth/register", json={
        "registration_token": v["registration_token"], "name": "New Supervisor", "role": "supervisor", "facility_id": None, "language": "or", "accepted_terms": True, "pin": "7391",
        "new_facility": {"name": "CHC Balipatna", "type": "chc", "district": "Khordha", "state": "Odisha"},
    })
    assert r.status_code == 200, r.text
    fid = r.json()["user"]["facility_id"]
    fac = client.get(f"{API}/facilities/{fid}").json()
    assert fac["name"] == "CHC Balipatna" and fac["languages"][0] == "or"


def test_twilio_provider_used_for_real_numbers(client, monkeypatch):
    from app import otp
    from app.config import get_settings

    s = get_settings()
    calls = []
    monkeypatch.setattr(s, "otp_provider", "twilio")
    monkeypatch.setattr(otp, "send", lambda phone: calls.append(("send", phone)))
    monkeypatch.setattr(otp, "check", lambda phone, code: calls.append(("check", phone, code)) or code == "424242")
    ch = client.post(f"{API}/auth/otp/request", json={"phone": "9812345678"}).json()
    assert ch.get("dev_code") is None and calls == [("send", "9812345678")]
    assert client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": "111111"}).status_code == 400
    assert client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": "424242"}).json()["status"] == "new_user"
    # sample accounts keep the documented code and never hit Twilio
    calls.clear()
    demo = client.post(f"{API}/auth/otp/request", json={"phone": "9000000001"}).json()
    assert calls == []
    assert client.post(f"{API}/auth/otp/verify", json={"challenge_id": demo["challenge_id"], "code": "123456"}).json()["status"] == "pin_required"
