from conftest import API


def _radha_encounter(client, doctor):
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()
    return next(i["encounter_id"] for i in q if i["patient_name"] == "Radha Kumari")


def test_share_link_opens_with_code_and_serves_documents(client, doctor):
    eid = _radha_encounter(client, doctor)
    s = client.post(f"{API}/encounters/{eid}/shares", json={"hours": 72}, headers=doctor).json()
    assert len(s["access_code"]) == 6 and "/s/" in s["url"]
    token = s["url"].rsplit("/", 1)[1]
    meta = client.get(f"{API}/share/{token}").json()
    assert meta["facility_name"] == "PHC Manikpur" and "patient" not in meta  # nothing clinical before the code
    bad = client.post(f"{API}/share/{token}/open", json={"access_code": "000000" if s["access_code"] != "000000" else "111111"})
    assert bad.status_code == 403 and "attempts left" in bad.json()["detail"]
    ok = client.post(f"{API}/share/{token}/open", json={"access_code": s["access_code"]})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["patient"]["code"] == "JVA-P001" and body["encounter"]["urgency"] == "red"
    assert body["documents"] and body["documents"][0]["url"]
    doc = client.get(body["documents"][0]["url"].replace("http://testserver", ""))
    assert doc.status_code == 200 and doc.content.startswith(b"<svg")
    # listed without the code; revocable
    listed = client.get(f"{API}/encounters/{eid}/shares", headers=doctor).json()
    assert listed[0]["access_code"] is None and listed[0]["views"] == 1
    assert client.delete(f"{API}/shares/{s['id']}", headers=doctor).status_code == 204
    assert client.post(f"{API}/share/{token}/open", json={"access_code": s["access_code"]}).status_code == 404


def test_share_locks_after_repeated_wrong_codes(client, doctor):
    eid = _radha_encounter(client, doctor)
    s = client.post(f"{API}/encounters/{eid}/shares", json={"hours": 1}, headers=doctor).json()
    token = s["url"].rsplit("/", 1)[1]
    wrong = "999999" if s["access_code"] != "999999" else "888888"
    for _ in range(8):
        client.post(f"{API}/share/{token}/open", json={"access_code": wrong})
    assert client.post(f"{API}/share/{token}/open", json={"access_code": s["access_code"]}).status_code == 423


def test_expired_share(client, doctor):
    from datetime import timedelta

    from app.db import SessionLocal
    from app.models import ShareLink

    eid = _radha_encounter(client, doctor)
    s = client.post(f"{API}/encounters/{eid}/shares", json={"hours": 1}, headers=doctor).json()
    with SessionLocal() as db:
        row = db.get(ShareLink, s["id"])
        row.expires_at = row.expires_at - timedelta(hours=2)
        db.commit()
    assert client.get(f"{API}/share/{s['url'].rsplit('/', 1)[1]}").status_code == 410


def test_only_reviewers_create_shares(client, doctor, supervisor, employer):
    eid = _radha_encounter(client, doctor)
    assert client.post(f"{API}/encounters/{eid}/shares", json={"hours": 24}, headers=supervisor).status_code == 403
    assert client.post(f"{API}/encounters/{eid}/shares", json={"hours": 24}, headers=employer).status_code == 403


def test_health_reports_components(client):
    h = client.get("/health").json()
    assert h["db"]["ok"] and h["storage"]["backend"] == "local" and "uptime_s" in h and h["otp"]["configured"]
