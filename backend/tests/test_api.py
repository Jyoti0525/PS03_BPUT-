import uuid

from conftest import API, DEVICE, GOOD_PIN, login


def new_intake(client, headers, **kw):
    pat = client.post(f"{API}/patients", json={"name": "Test Person", "age": 40, "sex": "M", "language": "en"}, headers=headers).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=headers).json()
    body = {
        "patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "en",
        "chief_complaint": "Chest pain spreading to left arm", "symptoms": [], "selected_symptoms": [], "answers": [],
        "file_ids": [], "vitals": {"bp_systolic": 150, "bp_diastolic": 90}, "consent_id": con["id"], "client_ref": f"t_{uuid.uuid4().hex}",
    }
    body.update(kw)
    return pat, body


# ── Auth ───────────────────────────────────────────────
def test_wrong_otp_rejected_and_attempts_limited(client):
    ch = client.post(f"{API}/auth/otp/request", json={"phone": "9000000001"}).json()
    for _ in range(5):
        assert client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": "000000"}).status_code == 400
    assert client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).status_code == 429


def test_register_requires_a_strong_pin_and_login_needs_otp_plus_pin(client):
    phone = "7" + uuid.uuid4().int.__str__()[:9]
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    reg = {"registration_token": v["registration_token"], "name": "New Nurse", "role": "nurse", "facility_id": "fac_kalinganagar", "language": "hi", "accepted_terms": True, "registration_no": "UPNC-1111"}
    assert client.post(f"{API}/auth/register", json=reg).status_code == 422  # PIN required
    assert "easy to guess" in client.post(f"{API}/auth/register", json={**reg, "pin": "1234"}).json()["detail"]
    assert client.post(f"{API}/auth/register", json={**reg, "pin": "4567"}).status_code == 422  # sequence
    r = client.post(f"{API}/auth/register", json={**reg, "pin": GOOD_PIN})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["has_pin"]
    # next sign-in: OTP alone gives no session
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    assert v["status"] == "pin_required" and "tokens" not in v and v["can_reset_pin"] is False
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {v['pin_token']}"}).status_code == 401  # step token is not a session
    bad = client.post(f"{API}/auth/pin/verify", json={"pin_token": v["pin_token"], "pin": "0000"})
    assert bad.status_code == 400 and "4 tries left" in bad.json()["detail"]
    ok = client.post(f"{API}/auth/pin/verify", json={"pin_token": v["pin_token"], "pin": GOOD_PIN})
    assert ok.status_code == 200 and ok.json()["tokens"]["access_token"]
    h = {"Authorization": f"Bearer {ok.json()['tokens']['access_token']}"}
    # change PIN from the dashboard
    assert client.post(f"{API}/auth/pin/change", json={"current_pin": "0000", "new_pin": "8264"}, headers=h).status_code == 400
    assert client.post(f"{API}/auth/pin/change", json={"current_pin": GOOD_PIN, "new_pin": "8264"}, headers=h).status_code == 204
    # nurses cannot reset their own PIN
    assert client.post(f"{API}/auth/pin/forgot", json={"pin_token": v["pin_token"]}).status_code == 403


def test_pin_lockout(client):
    phone = "7" + uuid.uuid4().int.__str__()[:9]
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    client.post(f"{API}/auth/register", json={"registration_token": v["registration_token"], "name": "Lock Test", "role": "receptionist", "facility_id": "fac_kalinganagar", "language": "en", "accepted_terms": True, "pin": GOOD_PIN})
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    v = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    codes = [client.post(f"{API}/auth/pin/verify", json={"pin_token": v["pin_token"], "pin": "9999"}).status_code for _ in range(5)]
    assert codes == [400, 400, 400, 400, 423]
    assert client.post(f"{API}/auth/pin/verify", json={"pin_token": v["pin_token"], "pin": GOOD_PIN}).status_code == 423  # locked even with the right PIN


def test_refresh_rotates_and_logout_revokes(client):
    ch = client.post(f"{API}/auth/otp/request", json={"phone": "9000000003"}).json()
    step = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    t = client.post(f"{API}/auth/pin/verify", json={"pin_token": step["pin_token"], "pin": "4826"}).json()["tokens"]
    new = client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert new.status_code == 200
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401  # single use
    h = {"Authorization": f"Bearer {new.json()['access_token']}"}
    assert client.get(f"{API}/auth/me", headers=h).status_code == 200
    assert client.post(f"{API}/auth/logout", headers=h).status_code == 204
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401


# ── Intake + review ───────────────────────────────────
def test_staff_intake_requires_bound_device(client, nurse):
    _, body = new_intake(client, nurse)
    assert client.post(f"{API}/encounters", json=body, headers=nurse).status_code == 403
    r = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE})
    assert r.status_code == 200, r.text
    enc = r.json()
    assert enc["urgency"] == "red"  # ATP-CARD-01 from the rules engine
    # idempotent replay (offline outbox)
    again = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    assert again["id"] == enc["id"]


def test_consent_required(client, nurse):
    _, body = new_intake(client, nurse, consent_id=None)
    assert client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).status_code == 422


def test_override_requires_reason_and_keeps_rules_output(client, nurse, doctor):
    _, body = new_intake(client, nurse)
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    short = {"to_urgency": "yellow", "category": "Vitals re-measured", "reason": "too short"}
    assert client.post(f"{API}/encounters/{enc['id']}/override", json=short, headers=doctor).status_code == 422
    ok = {**short, "reason": "Repeat ECG normal, chest wall tenderness reproduces the pain."}
    assert client.post(f"{API}/encounters/{enc['id']}/override", json=ok, headers=nurse).status_code == 403  # doctors only
    r = client.post(f"{API}/encounters/{enc['id']}/override", json=ok, headers=doctor).json()
    assert r["urgency"] == "yellow" and r["urgency_source"] == "override"
    assert r["override"]["from_urgency"] == "red"
    log = client.get(f"{API}/audit?action=OVERRIDE", headers=doctor).json()
    assert any(enc["patient"]["code"] == a["patient_code"] and "retained" in a["detail"] for a in log)


def test_escalation_and_acknowledgement(client, nurse, doctor):
    _, body = new_intake(client, nurse)
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    x = client.post(f"{API}/encounters/{enc['id']}/escalations", json={"to_role": "senior_mo", "reason": "SpO2 falling"}, headers=nurse).json()
    assert x["status"] == "open"
    assert client.post(f"{API}/escalations/{x['id']}/acknowledge", json={"note": "Seeing now"}, headers=nurse).status_code == 403
    ack = client.post(f"{API}/escalations/{x['id']}/acknowledge", json={"note": "Seeing now"}, headers=doctor).json()
    assert ack["status"] == "acknowledged" and ack["acknowledged_by"] == "Dr. Deepa Sharma"


def test_referral_and_exports(client, nurse, doctor):
    _, body = new_intake(client, nurse)
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    ref = {"destination": "District Hospital Gorakhpur", "specialty": "Cardiology", "reason": "Chest pain", "transport": "ambulance_108", "note_text": "Referral note text body"}
    r = client.post(f"{API}/encounters/{enc['id']}/referrals", json=ref, headers=doctor)
    assert r.status_code == 200
    assert client.get(f"{API}/encounters/{enc['id']}", headers=doctor).json()["status"] == "referred"
    pdf = client.get(f"{API}/encounters/{enc['id']}/export?format=pdf", headers=doctor)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    fhir = client.get(f"{API}/encounters/{enc['id']}/export?format=fhir", headers=doctor).json()
    assert fhir["resourceType"] == "Bundle" and fhir["entry"][0]["resource"]["resourceType"] == "Composition"


def test_queue_sorted_by_urgency(client, doctor):
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()
    ranks = [{"red": 0, "yellow": 1, "green": 2}[i["urgency"]] for i in q]
    assert ranks == sorted(ranks)
    assert client.get(f"{API}/queue?facility_id=fac_dh_gorakhpur", headers=doctor).status_code == 403


# ── Privacy / RBAC ────────────────────────────────────
def test_admin_cannot_read_clinical_notes(client, supervisor, doctor):
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()
    eid = q[0]["encounter_id"]
    assert client.get(f"{API}/encounters/{eid}", headers=supervisor).status_code == 403
    assert client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=supervisor).status_code == 403
    assert client.get(f"{API}/facilities/fac_phc_manikpur/stats", headers=supervisor).status_code == 200


def test_patient_never_sees_urgency_or_note(client, patient):
    rec = client.get(f"{API}/me/record", headers=patient).json()
    assert rec["patient"]["name"] == "Priya Sharma"
    assert rec["encounters"], "seeded encounters expected"
    for e in rec["encounters"]:
        assert e["urgency"] is None and e["note"] is None


def test_patient_cannot_read_household_members_records(client, patient, doctor):
    radha = client.get(f"{API}/patients/by-code/JVA-P001", headers=doctor).json()
    assert client.get(f"{API}/patients/{radha['id']}/encounters", headers=patient).status_code == 403


def test_employer_sees_cohorts_only(client, employer, doctor):
    c = client.get(f"{API}/employer/cohorts", headers=employer)
    assert c.status_code == 200 and all(set(w) == {"worker_code", "department", "fitness_status", "last_screened_at"} for co in c.json() for w in co["workers"])
    eid = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()[0]["encounter_id"]
    assert client.get(f"{API}/encounters/{eid}", headers=employer).status_code == 403


# ── Audit ──────────────────────────────────────────────
def test_views_are_audited_and_chain_verifies(client, doctor):
    eid = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()[0]["encounter_id"]
    client.get(f"{API}/encounters/{eid}", headers=doctor)
    views = client.get(f"{API}/audit?action=VIEW", headers=doctor).json()
    assert any(a["resource_id"] == eid for a in views)
    v = client.get(f"{API}/audit/verify", headers=doctor).json()
    assert v["ok"] and v["checked"] > 10


def test_audit_is_append_only():
    import pytest
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AuditEvent

    with SessionLocal() as db:
        e = db.scalars(select(AuditEvent).limit(1)).first()
        e.detail = "tampered"
        with pytest.raises(PermissionError):
            db.commit()
        db.rollback()
        db.delete(db.scalars(select(AuditEvent).limit(1)).first())
        with pytest.raises(PermissionError):
            db.commit()


# ── Files ──────────────────────────────────────────────
def test_upload_signed_url_and_retention(client, nurse, supervisor):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    r = client.post(f"{API}/files", data={"kind": "report", "sample_key": "cbc"}, files={"file": ("r.svg", svg, "image/svg+xml")}, headers=nurse)
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["expires_at"] > f["uploaded_at"]
    content = client.get(f["url"].replace("http://testserver", ""))
    assert content.status_code == 200 and content.content == svg
    bad = client.get(f"{API}/files/{f['id']}/content?sig=nope")
    assert bad.status_code == 401
    assert client.post(f"{API}/files", data={"kind": "audio"}, files={"file": ("x.exe", b"MZ", "application/x-msdownload")}, headers=nurse).status_code == 415
    ret = client.get(f"{API}/retention", headers=supervisor).json()
    assert ret["policy_hours"]["audio"] == 24 and all(x["url"] is None for x in ret["files"])


def test_health_and_metrics(client):
    assert client.get("/health").json()["status"] == "ok"
    m = client.get("/metrics").text
    assert "jeevia_http_requests_total" in m


def test_new_login_helper(client):
    assert login(client, "9000000002")


def test_concurrent_audited_requests_keep_chain_intact(client, doctor):
    """Regression: parallel requests that write audit events must not deadlock or fork the chain."""
    from concurrent.futures import ThreadPoolExecutor

    paths = [f"{API}/escalations", f"{API}/queue?facility_id=fac_phc_manikpur", f"{API}/facilities/fac_phc_manikpur/stats", f"{API}/patients?q=JVA"] * 6
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda p: client.get(p, headers=doctor, timeout=20).status_code, paths))
    assert all(c == 200 for c in codes), codes
    v = client.get(f"{API}/audit/verify", headers=doctor).json()
    assert v["ok"], v
