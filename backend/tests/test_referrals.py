"""E4: a referral closes only when care is received; an open referral past due raises an alert; destinations by specialist."""
from datetime import timedelta

from conftest import API
from test_wednesday import intake, mo  # noqa: F401  (mo is a fixture)

REF = {"destination": "District Hospital Gorakhpur", "specialty": "Cardiology", "reason": "Chest pain", "transport": "ambulance_108", "note_text": "Referral note text body"}


def test_referral_stays_open_until_care_is_received(client, nurse, doctor):
    _, e = intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    r = client.post(f"{API}/encounters/{e['id']}/referrals", json=REF, headers=doctor).json()
    assert r["status"] == "sent" and r["due_at"] and not r["overdue"]
    share = client.post(f"{API}/encounters/{e['id']}/shares", json={"hours": 72, "purpose": "referral"}, headers=doctor).json()
    token = share["url"].rstrip("/").split("/")[-1]
    bad = client.post(f"{API}/share/{token}/received", json={"access_code": "000000", "confirmed_by": "Dr Rao, DH casualty"})
    assert bad.status_code == 403
    ok = client.post(f"{API}/share/{token}/received", json={"access_code": share["access_code"], "confirmed_by": "Dr Rao, DH casualty", "note": "ECG done"})
    assert ok.status_code == 200, ok.text
    got = [x for x in client.get(f"{API}/referrals", headers=doctor).json() if x["id"] == r["id"]][0]
    assert got["status"] == "received" and got["received_via"] == "qr" and got["received_by"] == "Dr Rao, DH casualty"
    assert client.post(f"{API}/referrals/{r['id']}/received", json={"confirmed_by": "again"}, headers=doctor).status_code == 409


def test_referral_without_destination_uses_qr_handoff_at_patient_chosen_facility(client, nurse, doctor):
    _, e = intake(client, nurse, chief_complaint="Needs specialist review")
    payload = {k: v for k, v in REF.items() if k != "destination"}
    payload["note_text"] = "Referral note. Destination is advisory; patient may choose another facility."
    sent = client.post(f"{API}/encounters/{e['id']}/referrals", json=payload, headers=doctor)
    assert sent.status_code == 200, sent.text
    referral = sent.json()
    assert referral["destination"] == "Patient's choice — no specific facility selected"
    assert referral["to_facility_id"] is None

    share = client.post(f"{API}/encounters/{e['id']}/shares", json={"hours": 168, "purpose": "referral"}, headers=doctor).json()
    token = share["url"].rstrip("/").split("/")[-1]
    opened = client.post(f"{API}/share/{token}/open", json={"access_code": share["access_code"]})
    assert opened.status_code == 200, opened.text
    summary = opened.json()
    assert summary["referral"]["note_text"] == payload["note_text"]
    assert "Patient's choice" in summary["referral"]["destination"]

    # The public QR confirmation has no destination-facility constraint: a clinician elsewhere can confirm care.
    confirmed = client.post(f"{API}/share/{token}/received", json={"access_code": share["access_code"], "confirmed_by": "Nurse Rao (ANM), patient-chosen clinic"})
    assert confirmed.status_code == 200, confirmed.text
    final = next(x for x in client.get(f"{API}/referrals", headers=doctor).json() if x["id"] == referral["id"])
    assert final["status"] == "received" and "patient-chosen clinic" in final["received_by"]


def test_overdue_referral_raises_an_alert_until_confirmed(client, nurse, doctor, mo):
    from app.db import SessionLocal
    from app.models import Referral
    from app.services import now

    _, e = intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    r = client.post(f"{API}/encounters/{e['id']}/referrals", json=REF, headers=doctor).json()
    with SessionLocal() as db:
        db.get(Referral, r["id"]).due_at = now() - timedelta(minutes=1)
        db.commit()
    assert [x for x in client.get(f"{API}/referrals", headers=doctor).json() if x["id"] == r["id"]][0]["overdue"]
    alerts = client.get(f"{API}/alerts?status=active", headers=mo).json()
    assert any(a["kind"] == "referral_overdue" and a["detail"]["referral_id"] == r["id"] for a in alerts)
    client.post(f"{API}/referrals/{r['id']}/received", json={"confirmed_by": "Phoned DH casualty, patient admitted"}, headers=doctor)
    alerts = client.get(f"{API}/alerts?status=active", headers=mo).json()
    assert not any(a["kind"] == "referral_overdue" and a["detail"]["referral_id"] == r["id"] for a in alerts)
    assert client.post(f"{API}/referrals/{r['id']}/received", json={"confirmed_by": "x"}, headers=nurse).status_code in (403, 422)


# ── E5: follow-up dates follow the facility's own visit calendar ─────────
def test_follow_up_lands_on_the_facility_clinic_day(client, nurse, supervisor):
    from datetime import date

    from app import visits

    v = client.get(f"{API}/facilities/fac_phc_manikpur/visit-days?kind=anc_checkup&after=2026-10-10", headers=nurse).json()
    days = [date.fromisoformat(d) for d in v["days"]]
    assert all(d.weekday() == 2 or d.day == 9 for d in days) and "Wednesday" in v["rule"] and "9th" in v["rule"]
    # The facility sets its own days: ANC on Thursdays, closed on a holiday.
    cfg = {"visits": {"anc_checkup": {"weekdays": [3], "monthdays": []}, "closed_dates": ["2026-10-15"]}}
    assert client.patch(f"{API}/facilities/fac_phc_manikpur", json={"region_config": cfg}, headers=supervisor).status_code == 200
    v = client.get(f"{API}/facilities/fac_phc_manikpur/visit-days?kind=anc_checkup&after=2026-10-10", headers=nurse).json()
    assert v["days"][0] == "2026-10-22"  # Thursday 15th is a holiday
    p, e = intake(client, nurse, category="maternal", chief_complaint="Routine ANC visit",
                  maternal={"gestation_weeks": 20, "next_checkup": "2026-10-13", "reminder_channel": "none"})
    fu = [f for f in client.get(f"{API}/followups?scope=all", headers=nurse).json() if f["patient_id"] == p["id"]]
    assert fu and fu[0]["due_at"].startswith("2026-10-22")
    client.patch(f"{API}/facilities/fac_phc_manikpur", json={"region_config": {}}, headers=supervisor)
    assert visits.snap(type("F", (), {"type": "industrial_unit", "region_config": None})(), "chronic_checkin", date(2026, 10, 11))[0] == date(2026, 10, 12)


# ── F2: the facility's patient load is a setting the kiosk reads ─────────
def test_patient_load_is_configurable(client, nurse, supervisor):
    f = client.get(f"{API}/facilities/fac_phc_manikpur", headers=nurse).json()
    assert f["patient_load"] == "normal"
    assert client.patch(f"{API}/facilities/fac_phc_manikpur", json={"patient_load": "busy"}, headers=supervisor).status_code == 422
    assert client.patch(f"{API}/facilities/fac_phc_manikpur", json={"patient_load": "high"}, headers=supervisor).json()["patient_load"] == "high"
    client.patch(f"{API}/facilities/fac_phc_manikpur", json={"patient_load": "normal"}, headers=supervisor)


# ── A7: an online voice when the device has none (no Sarvam call in tests) ─────────
def test_speak_uses_the_online_voice_and_never_stores(client, nurse, monkeypatch):
    from app import sarvam

    monkeypatch.setattr(sarvam, "enabled", lambda: True)
    monkeypatch.setattr(sarvam, "speak", lambda text, lang: b"ID3fake-" + lang.encode())
    r = client.post(f"{API}/language/speak", json={"text": "ନମସ୍କାର", "language": "or"}, headers=nurse)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content.endswith(b"or")
    assert client.post(f"{API}/language/speak", json={"text": "x", "language": "sat"}, headers=nurse).status_code == 422
    monkeypatch.setattr(sarvam, "enabled", lambda: False)
    assert client.post(f"{API}/language/speak", json={"text": "x", "language": "or"}, headers=nurse).status_code == 503


# ── H3: run profiles ─────────
def test_profiles_switch_what_runs(monkeypatch):
    from app.config import Settings

    stub = Settings(profile="stub", _env_file=None)
    assert not stub.language_models and not stub.ocr_enabled and stub.llm_url is None and stub.sarvam_api_key is None
    assert Settings(profile="full", _env_file=None).preload_language_models
    demo = Settings(profile="demo", _env_file=None)
    assert demo.language_models and demo.ocr_enabled and not demo.preload_language_models
    # an explicit setting wins over the profile
    assert Settings(profile="stub", ocr_enabled=True, _env_file=None).ocr_enabled


def test_stub_profile_reads_no_documents_and_says_so(monkeypatch):
    from app.config import get_settings
    from app.triage import extraction

    monkeypatch.setattr(get_settings(), "ocr_enabled", False)
    assert not extraction.ocr_available()
