"""Security controls (SECURITY.md): encryption at rest, upload checks, rate limits, headers, share minimum, production
settings."""

import io
from pathlib import Path

import pytest
from conftest import API

from app import crypto, ratelimit
from app.config import Settings, get_settings
from app.filetypes import check, sniff

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


# ── encryption at rest ───────────────────────────────
def test_patient_identifiers_are_ciphertext_in_the_database(client, nurse):
    from sqlalchemy import text

    from app.db import SessionLocal

    p = client.post(f"{API}/patients", json={"name": "Cipher Test", "age": 30, "sex": "F", "phone": "9333333333", "village": "Baripada"}, headers=nurse).json()
    assert p["name"] == "Cipher Test" and p["phone"] == "9333333333"  # staff see plain text
    with SessionLocal() as db:
        name, phone, village, ph = db.execute(text("SELECT name, phone, village, phone_hash FROM patients WHERE id = :i"), {"i": p["id"]}).one()
    for v in (name, phone, village):
        assert v.startswith(crypto.PREFIX) and "Cipher" not in v and "9333" not in v and "Baripada" not in v
    assert ph == crypto.blind("9333333333") and "9333" not in ph
    found = client.get(f"{API}/patients", params={"q": "9333333333"}, headers=nurse).json()  # full phone: by its hash
    assert any(c["patient"]["id"] == p["id"] for c in found)
    found = client.get(f"{API}/patients", params={"q": "cipher"}, headers=nurse).json()  # part of a name: after decrypting
    assert any(c["patient"]["id"] == p["id"] for c in found)


def test_rows_stored_before_encryption_are_encrypted_at_start_up():
    from sqlalchemy import text

    from app.db import SessionLocal

    with SessionLocal() as db:
        db.execute(text("INSERT INTO patients (id, code, name, age, sex, phone, language, category, data_origin, created_at) "
                        "VALUES ('pat_legacy01', 'JVA-LEG1', 'Old Plain', 40, 'M', '9444444444', 'en', 'normal', 'SYNTHETIC', CURRENT_TIMESTAMP)"))
        db.commit()
        assert crypto.encrypt_existing(db) >= 1
        name, ph = db.execute(text("SELECT name, phone_hash FROM patients WHERE id = 'pat_legacy01'")).one()
        assert name.startswith(crypto.PREFIX) and ph == crypto.blind("9444444444")
        from app.models import Patient

        assert db.get(Patient, "pat_legacy01").name == "Old Plain"


def test_uploaded_files_are_encrypted_on_disk(client, nurse):
    f = client.post(f"{API}/files", files={"file": ("slip.png", io.BytesIO(PNG), "image/png")}, data={"kind": "image", "read": "false"}, headers=nurse).json()
    raw = (Path(get_settings().storage_dir) / f["id"]).read_bytes()
    assert raw.startswith(crypto.FILE_MAGIC) and b"PNG" not in raw
    served = client.get(f["url"].replace("http://testserver", ""))
    assert served.status_code == 200 and served.content.startswith(b"\x89PNG")
    assert "sandbox" in served.headers["content-security-policy"] and served.headers["cache-control"] == "private, no-store"


# ── upload checks ────────────────────────────────────
def test_the_contents_decide_the_file_type(client, nurse):
    def up(name, data, ctype, kind="report", **form):
        return client.post(f"{API}/files", files={"file": (name, io.BytesIO(data), ctype)}, data={"kind": kind, "read": "false", **form}, headers=nurse)

    assert up("report.png", b"MZ\x90\x00 an exe", "image/png").status_code == 415  # renamed program
    assert up("report.pdf", PNG, "application/pdf").status_code == 415  # label and contents disagree
    assert up("a.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml").status_code == 415  # SVG only as a sample
    evil = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    assert up("a.svg", evil, "image/svg+xml", sample_key="cbc").status_code == 415
    assert up("voice.webm", PNG, "audio/webm", kind="audio").status_code == 415
    assert up("ok.png", PNG, "image/png").status_code == 200


def test_sniffing():
    assert sniff(b"%PDF-1.7 ...") == "application/pdf"
    assert sniff(b"RIFF\x00\x00\x00\x00WAVEfmt ") == "audio/wav"
    assert sniff(b"\x00\x00\x00\x18ftypheic") == "image/heic"
    assert sniff(b"#!/bin/sh") is None
    with pytest.raises(ValueError):
        check(b"<html><script>", "image/png", ("image/",))


def test_a_recording_must_be_audio(client, nurse):
    r = client.post(f"{API}/speech/transcribe", headers=nurse, files={"audio": ("a.webm", PNG, "audio/webm")}, data={"language": "hi"})
    assert r.status_code == 422


# ── rate limits ──────────────────────────────────────
@pytest.fixture
def limits(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit", True)
    monkeypatch.setattr(s, "rate_per_min_public", 5)
    monkeypatch.setattr(s, "rate_per_phone_10min", 3)
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_public_links_are_rate_limited(client, limits):
    codes = [client.get(f"{API}/share/no-such-token").status_code for _ in range(7)]
    assert codes[:5] == [404] * 5 and codes[5:] == [429, 429]
    r = client.get(f"{API}/share/no-such-token")
    assert int(r.headers["retry-after"]) >= 1
    other = client.get(f"{API}/share/no-such-token", headers={"X-Device-Id": "another-kiosk"})
    assert other.status_code == 404  # counted per device


def test_kiosk_lookup_is_limited_per_phone(limits):
    from fastapi import HTTPException

    for _ in range(3):  # from any device: the count is kept per phone number
        ratelimit.per_phone("9555555555", "kiosk-identify")
    with pytest.raises(HTTPException) as e:
        ratelimit.per_phone("+91 9555555555", "kiosk-identify")
    assert e.value.status_code == 429
    ratelimit.per_phone("9555555556", "kiosk-identify")  # another number is not affected


# ── headers ──────────────────────────────────────────
def test_api_sends_browser_protections(client, nurse):
    r = client.get(f"{API}/auth/me", headers=nurse)
    for k in ("x-content-type-options", "x-frame-options", "referrer-policy", "content-security-policy"):
        assert k in r.headers
    assert "default-src 'none'" in r.headers["content-security-policy"] and r.headers["cache-control"] == "no-store"
    assert "strict-transport-security" in client.get("/health", headers={"X-Forwarded-Proto": "https"}).headers


# ── shares: the minimum ──────────────────────────────
def test_shared_summary_leaves_out_contact_details(client, doctor):
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()
    eid = next(i["encounter_id"] for i in q if i["patient_name"] == "Radha Kumari")
    s = client.post(f"{API}/encounters/{eid}/shares", json={"hours": 24}, headers=doctor).json()
    body = client.post(f"{API}/share/{s['url'].rsplit('/', 1)[1]}/open", json={"access_code": s["access_code"]}).json()
    assert "phone" not in body["patient"] and "village" not in body["patient"]
    assert body["encounter"]["consent"] is None or "proxy_name" not in body["encounter"]["consent"]
    assert client.post(f"{API}/encounters/{eid}/shares", json={"hours": 24 * 30}, headers=doctor).status_code == 422  # a week at most


# ── production settings ──────────────────────────────
def test_production_refuses_development_settings():
    with pytest.raises(ValueError) as e:
        Settings(env="production", rate_limit=True, _env_file=None)
    msg = str(e.value)
    assert "JEEVIA_JWT_SECRET" in msg and "JEEVIA_DATA_KEY" in msg and "mock" in msg
    ok = Settings(env="production", jwt_secret="x" * 40, data_key="y" * 40, otp_provider="twilio", cors_origins="https://jeevia-triage.vercel.app", rate_limit=True, _env_file=None)
    assert ok.env == "production"
    with pytest.raises(ValueError):
        Settings(env="production", jwt_secret="x" * 40, data_key="y" * 40, otp_provider="twilio", cors_origins="*", rate_limit=True, _env_file=None)


# ── DPDP: children and grievances ────────────────────
def test_under_18_needs_a_parent_or_guardian(client, nurse):
    child = client.post(f"{API}/patients", json={"name": "Minor Test", "age": 12, "sex": "F", "language": "or"}, headers=nurse).json()
    base = {"patient_id": child["id"], "privacy_context": "assisted", "language": "or", "scopes": ["triage"]}
    assert client.post(f"{API}/consents", json={**base, "mode": "self"}, headers=nurse).status_code == 422
    assert client.post(f"{API}/consents", json={**base, "mode": "proxy", "proxy_name": "Asha Didi", "proxy_relation": "Caregiver"}, headers=nurse).status_code == 422
    ok = client.post(f"{API}/consents", json={**base, "mode": "proxy", "proxy_name": "Sita Nayak", "proxy_relation": "Mother"}, headers=nurse)
    assert ok.status_code == 200 and ok.json()["grievance_contact"]  # the slip carries the grievance contact
    adult = client.post(f"{API}/patients", json={"name": "Adult Test", "age": 18, "sex": "M", "language": "or"}, headers=nurse).json()
    assert client.post(f"{API}/consents", json={**base, "patient_id": adult["id"], "mode": "self"}, headers=nurse).status_code == 200
