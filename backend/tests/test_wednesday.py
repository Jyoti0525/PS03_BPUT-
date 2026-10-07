"""Roles and sign-off (E2), role questions (B7), capacity alert (C3), AIIMS high-risk complaints (C5), occupational
screening (D2), fever clusters (D3) and maternal missed visits (D4)."""

import uuid
from datetime import date, timedelta

import pytest
from conftest import API, DEVICE, login

from app.triage.rules import evaluate_full

NORMAL = {"bp_systolic": 120, "bp_diastolic": 80, "pulse": 80, "spo2": 98, "temp_f": 98.4, "resp_rate": 16, "avpu": "A"}
FULL = {"vitals": NORMAL, "exam": {"done": True}, "severity": 3, "duration": "3-7 days", "category": "normal"}


def said(text: str, lang: str = "en") -> dict:
    return {**FULL, "chief_complaint": text, "symptoms": [{"text": text, "original_text": text, "language": lang, "source": "text"}]}


@pytest.fixture(scope="module")
def hw(client):
    return login(client, "9000000006")


@pytest.fixture(scope="module")
def mo(client):
    return login(client, "9000000007")


def intake(client, headers, *, name="Test Person", age=40, sex="M", phone=None, village=None, **kw):
    pat = client.post(f"{API}/patients", json={"name": name, "age": age, "sex": sex, "language": "en", "phone": phone, "village": village}, headers=headers).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=headers).json()
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "en", "chief_complaint": "Headache",
            "symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [], "vitals": None, "consent_id": con["id"], "client_ref": f"w_{uuid.uuid4().hex}"}
    body.update(kw)
    r = client.post(f"{API}/encounters", json=body, headers={**headers, "X-Device-Id": DEVICE})
    assert r.status_code == 200, r.text
    return pat, r.json()


# ── C5: AIIMS 2025 high-risk complaints are never GREEN ──
@pytest.mark.parametrize("text,lang", [("shortness of breath", "en"), ("chest pain", "en"), ("सांस लेने में तकलीफ", "hi"), ("ଛାତି ଯନ୍ତ୍ରଣା", "or"),
                                       ("vomiting blood", "en"), ("fell from the roof", "en"), ("weakness on one side", "en")])
def test_high_risk_complaints_are_at_least_yellow(text, lang):
    r = evaluate_full(said(text, lang), 40, "M")
    assert r["urgency"] in ("yellow", "red"), (text, r["hits"])
    assert any(h["rule_id"].startswith("HRC-") for h in r["hits"]) or r["urgency"] == "red"


def test_high_risk_floor_is_adult_only_and_routine_stays_green():
    assert evaluate_full(said("mild headache"), 40, "M")["urgency"] == "green"
    kid = evaluate_full(said("chest pain"), 10, "M")
    assert not any(h["rule_id"].startswith("HRC-") for h in kid["hits"])


# ── D2: occupational rules ────────────────────────────
def occ(**o):
    return {**said("routine screening"), "occupational": o}


def test_silica_with_tb_symptom_is_red_and_routes_to_ntep():
    r = evaluate_full({**said("losing weight and coughing"), "occupational": {"exposures": ["silica"]}}, 38, "M")
    assert r["urgency"] == "red"
    h = next(h for h in r["hits"] if h["rule_id"] == "OCC-SILICA-TB")
    assert "NTEP" in h["source"] and any("silica" in e for e in h["evidence"])


def test_dust_with_long_cough_is_yellow_and_noise_alone_is_green():
    assert [h["rule_id"] for h in evaluate_full(occ(exposures=["coal_dust"], cough_weeks=10), 45, "M")["hits"]] == ["OCC-DUST-CHRONIC-RESP"]
    assert evaluate_full(occ(exposures=["coal_dust"], cough_weeks=6), 45, "M")["urgency"] == "green"
    assert evaluate_full(occ(exposures=["noise"]), 45, "M")["urgency"] == "green"
    assert evaluate_full(occ(exposures=["cotton_dust"], breathless_vs_last="worse"), 45, "M")["hits"][0]["rule_id"] == "OCC-BREATHLESS-WORSE"


def test_occupational_details_not_asked_never_hold_a_screening():
    r = evaluate_full(occ(exposures=["silica"]), 30, "M")
    assert r["urgency"] == "green" and not r["provisional"]


def test_fev1_decline_against_own_baseline():
    hit = evaluate_full(occ(exposures=["silica"], fev1_l=2.5, fev1_baseline_l=3.0), 40, "M")["hits"]
    assert hit[0]["rule_id"] == "OCC-FEV1-DECLINE" and "16.7 %" in hit[0]["evidence"][0]
    assert evaluate_full(occ(exposures=["silica"], fev1_l=2.7, fev1_baseline_l=3.0), 40, "M")["urgency"] == "green"
    assert evaluate_full(occ(exposures=["silica"], fev1_l=2.0), 40, "M")["urgency"] == "green"  # no earlier test: nothing to compare


def test_ppe_gap_is_a_flag_not_urgency_and_missing_details_are_listed(client, nurse, doctor):
    _, e = intake(client, nurse, chief_complaint="Routine workplace screening", vitals=NORMAL,
                  occupational={"exposures": ["silica"], "ppe_issued": True, "ppe_used": "sometimes"})
    full = client.get(f"{API}/encounters/{e['id']}", headers=doctor).json()
    flags = {f["code"]: f for f in full["note"]["flags"]}
    assert "PPE-GAP" in flags and flags["PPE-GAP"]["label"].startswith("Workplace finding")
    assert not any(h["rule_id"] == "PPE-GAP" for h in full["note"]["rules_fired"])
    assert any("Years of workplace exposure" in m for m in full["note"]["missing_info"])
    assert any("Spirometry" in m for m in full["note"]["missing_info"])


def test_fev1_baseline_comes_from_the_workers_earlier_screening(client, nurse, doctor):
    pat, first = intake(client, nurse, chief_complaint="Annual screening", vitals=NORMAL, occupational={"exposures": ["silica"], "fev1_l": 3.2})
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": "en", "chief_complaint": "Annual screening",
            "vitals": NORMAL, "occupational": {"exposures": ["silica"], "fev1_l": 2.6}, "consent_id": first["consent"]["id"], "client_ref": f"w_{uuid.uuid4().hex}"}
    second = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    note = client.get(f"{API}/encounters/{second['id']}", headers=doctor).json()["note"]
    hit = next(h for h in note["rules_fired"] if h["rule_id"] == "OCC-FEV1-DECLINE")
    assert "3.2 L" in hit["evidence"][0] and "18.8 %" in hit["evidence"][0]


def test_employer_department_rates_hide_small_groups_and_symptoms(client, employer):
    from app.db import SessionLocal
    from app.models import Consent, Patient
    from app.services import create_encounter

    tag = uuid.uuid4().hex[:5]
    plan = [("Crusher " + tag, 6, {"exposures": ["silica"], "cough_weeks": 10, "ppe_used": "never", "ppe_issued": True}),
            ("Stores " + tag, 6, {"exposures": ["noise"]}),
            ("Lab " + tag, 2, {"exposures": ["chemicals"]})]
    with SessionLocal() as db:
        for dept, n, o in plan:
            for i in range(n):
                p = Patient(code=f"T{tag}{dept[:2]}{i}", name=f"Worker {i}", age=35, sex="M", organisation_id="org_kalinganagar", employee_code=f"{tag}-{dept[:2]}-{i}", department=dept)
                db.add(p)
                db.flush()
                c = Consent(patient_id=p.id, mode="self", privacy_context="private", language="or", scopes=["triage"], captured_by="test")
                db.add(c)
                db.flush()
                create_encounter(db, {"patient_id": p.id, "facility_id": "fac_kalinganagar", "category": "normal", "language": "en",
                                      "chief_complaint": "persistent cough" if o.get("cough_weeks") else "screening", "vitals": NORMAL, "exam": {"done": True},
                                      "occupational": o, "consent_id": c.id, "client_ref": f"w_{uuid.uuid4().hex}", "symptoms": []}, p)
        db.commit()
    r = client.get(f"{API}/employer/department-rates", headers=employer)
    assert r.status_code == 200
    rows = {d["department"]: d for d in r.json()["departments"]}
    assert rows["Crusher " + tag]["follow_up_pct"] == 100 and rows["Crusher " + tag]["ppe_gap_pct"] == 100 and rows["Crusher " + tag]["above_others"]
    assert rows["Stores " + tag]["follow_up_pct"] == 0 and not rows["Stores " + tag]["above_others"]
    assert rows["Lab " + tag]["suppressed"] and rows["Lab " + tag]["screened"] is None
    text = r.text.lower()
    for word in ("cough", "weight", "breath", "silica", "fever", "worker 0", "tb"):
        assert word not in text, word


# ── E2 / B7: roles, density, sign-off ─────────────────
def test_health_worker_gets_the_short_note_and_only_their_questions(client, nurse, hw, doctor, mo):
    _, e = intake(client, nurse, chief_complaint="fever and cough with chest pain", vitals={"spo2": 85, "avpu": "A"})
    short = client.get(f"{API}/encounters/{e['id']}", headers=hw).json()["note"]
    assert short["detail_level"] == "summary"
    assert "rules_fired" not in short and "labs" not in short and "summary" in short
    assert {q["for_role"] for q in short["followup_questions"]} == {"health_worker"}
    n = client.get(f"{API}/encounters/{e['id']}", headers=nurse).json()["note"]
    assert {q["for_role"] for q in n["followup_questions"]} <= {"health_worker", "nurse"} and "rules_fired" in n
    d = client.get(f"{API}/encounters/{e['id']}", headers=mo).json()["note"]
    roles = [q["for_role"] for q in d["followup_questions"]]
    assert "medical_officer" in roles and "doctor" in roles  # RED: the transfer question for the MO
    assert all(roles.count(r) <= 3 for r in set(roles))


def test_sign_off_limits(client, nurse, hw, mo):
    _, red = intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    assert red["urgency"] == "red" and red["sign_off"] == "doctor"
    assert client.post(f"{API}/encounters/{red['id']}/confirm", headers=hw).status_code == 403
    r = client.post(f"{API}/encounters/{red['id']}/confirm", headers=nurse)
    assert r.status_code == 403 and "doctor or medical officer" in r.json()["detail"]
    assert client.post(f"{API}/encounters/{red['id']}/confirm", headers=mo).json()["status"] == "confirmed"

    _, yellow = intake(client, nurse, chief_complaint="Headache")  # no vitals: provisional YELLOW
    assert yellow["urgency"] == "yellow"
    assert client.post(f"{API}/encounters/{yellow['id']}/confirm", headers=hw).status_code == 403
    assert client.post(f"{API}/encounters/{yellow['id']}/confirm", headers=nurse).json()["status"] == "confirmed"

    _, green = intake(client, nurse, chief_complaint="mild headache", vitals=NORMAL, severity=2, duration="3-7 days", exam={"done": True})
    client.post(f"{API}/encounters/{green['id']}/observations", json={"exam_done": True}, headers=nurse)
    g = client.get(f"{API}/encounters/{green['id']}", headers=hw).json()
    assert g["urgency"] == "green" and g["can_confirm"]
    assert client.post(f"{API}/encounters/{green['id']}/confirm", headers=hw).json()["status"] == "confirmed"


def test_health_worker_cannot_override_refer_or_confirm_medicines(client, nurse, hw):
    _, e = intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    ok = {"to_urgency": "yellow", "category": "Re-measured", "reason": "Repeat ECG normal and pain is reproducible on palpation."}
    assert client.post(f"{API}/encounters/{e['id']}/override", json=ok, headers=hw).status_code == 403
    assert client.post(f"{API}/encounters/{e['id']}/medications", json={"confirm": [], "reject": []}, headers=hw).status_code == 403


# ── C3: queue order reason and capacity alert ─────────
def test_queue_rows_say_why_and_capacity_alert_goes_to_the_mo(client, nurse, doctor, mo):
    from app.db import SessionLocal
    from app.models import User

    intake(client, nurse, chief_complaint="Chest pain spreading to left arm")
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json()
    reds = [i for i in q if i["urgency"] == "red"]
    assert reds[0]["order_reason"].startswith("RED") and f"1st of {len(reds)} RED" in reds[0]["order_reason"] and "waiting" in reds[0]["order_reason"]
    assert reds[0]["top_flags"] and len(reds[0]["top_flags"]) <= 2 and reds[0]["flag_count"] >= len(reds[0]["top_flags"])  # flags in words, not a count
    assert "SAFE-PROVISIONAL" not in reds[0]["order_reason"]
    with SessionLocal() as db:  # only one doctor on duty
        db.get(User, "usr_mo1").on_duty = False
        db.commit()
    try:
        cap = client.get(f"{API}/capacity", headers=nurse).json()
        assert cap["over"] and cap["doctors_on_duty"] == 1 and cap["open_red"] >= 2
        assert cap["alert"]["to_role"] == "medical_officer" and "RED" in cap["alert"]["title"]
        assert not any("name" in r for r in cap["reds"])
        alerts = client.get(f"{API}/alerts?status=active", headers=mo).json()
        a = next(a for a in alerts if a["kind"] == "capacity")
        assert client.post(f"{API}/alerts/{a['id']}/acknowledge", json={"note": "Calling Dr. B"}, headers=nurse).status_code == 403
        assert client.post(f"{API}/alerts/{a['id']}/acknowledge", json={"note": "Calling Dr. B"}, headers=mo).json()["status"] == "acknowledged"
        # clear the REDs: the alert resolves itself
        for i in client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doctor).json():
            if i["urgency"] == "red":
                client.post(f"{API}/encounters/{i['encounter_id']}/confirm", headers=doctor)
        cap = client.get(f"{API}/capacity", headers=nurse).json()
        assert not cap["over"] and cap["alert"] is None
        assert next(x for x in client.get(f"{API}/alerts", headers=mo).json() if x["id"] == a["id"])["status"] == "resolved"
    finally:
        with SessionLocal() as db:
            db.get(User, "usr_mo1").on_duty = True
            db.commit()


# ── D3: fever cluster ─────────────────────────────────
def test_fever_cluster_alert_is_deidentified_and_export_suppresses_small_counts(client, nurse, mo, hw):
    block = f"Hostel Block {uuid.uuid4().hex[:4]}"
    for i in range(4):
        intake(client, nurse, name=f"Student {i}", age=20, chief_complaint="fever since yesterday", cluster_key=block)
    assert not any(a["kind"] == "fever_cluster" and a["key"] == block for a in client.get(f"{API}/alerts", headers=mo).json())
    intake(client, nurse, name="Student 4", age=20, chief_complaint="headache", cluster_key=block, vitals={"temp_f": 101.2})  # fever by thermometer
    a = next(a for a in client.get(f"{API}/alerts?status=active", headers=mo).json() if a["kind"] == "fever_cluster" and a["key"] == block)
    assert a["to_role"] == "medical_officer" and a["detail"]["cases_72h"] == 5
    assert "Student" not in str(a)
    assert not any(x["kind"] == "fever_cluster" for x in client.get(f"{API}/alerts", headers=hw).json())  # MO's alert, not the ASHA's
    csv = client.get(f"{API}/surveillance/syndromic.csv?days=3", headers=mo)
    assert csv.status_code == 200 and csv.text.startswith("date,place,visits,fever")
    row = next(line for line in csv.text.splitlines() if block in line)
    assert row.split(",")[3] == "5"  # five fevers today
    assert "<5" in csv.text  # small counts are written as <5
    assert client.get(f"{API}/surveillance/syndromic.csv", headers=nurse).status_code == 403


def test_fever_cluster_needs_three_times_the_usual_rate():
    from app import alerts as al

    # 5 now vs 14 in the 14 days before (3 per 72 h expected): 5 is not more than 3 x 3
    assert not (5 > al.RATIO * (14 / al.BASELINE_DAYS * al.WINDOW_H / 24))
    assert 5 > al.RATIO * (2 / al.BASELINE_DAYS * al.WINDOW_H / 24)


# ── D4: maternal missed visits ────────────────────────
def test_missed_visit_goes_to_the_assigned_asha_then_a_neutral_call(client, nurse, hw, mo):
    past = (date.today() - timedelta(days=3)).isoformat()
    pat, e = intake(client, nurse, name="Sita Devi", age=26, sex="F", phone="9811122233", village="Bhanpur", category="maternal",
                    chief_complaint="ANC visit", maternal={"gestation_weeks": 30, "next_checkup": past, "phone_belongs_to": "husband", "assigned_worker_id": "usr_hw1"})
    rows = client.get(f"{API}/followups", headers=hw).json()
    f = next(x for x in rows if x["patient_id"] == pat["id"])
    assert f["status"] == "missed" and f["assigned_name"].startswith("Kamla")
    assert "pregnan" not in f["call_script"].lower() and "check-up" not in f["call_script"].lower() and "Sita" in f["call_script"]
    alert = next(a for a in client.get(f"{API}/alerts", headers=hw).json() if a["kind"] == "missed_visit" and a["key"] == f["id"])
    assert alert["assigned_to"] == "usr_hw1"
    for _ in range(2):
        f = client.post(f"{API}/followups/{f['id']}/attempt", json={"outcome": "not_reached", "note": "House locked"}, headers=hw).json()
    assert f["status"] == "call_due"
    assert f["who_calls"]["who"] == "human"  # no vitals were taken at that visit, so a person calls (E6), with neutral wording
    call = client.post(f"{API}/followups/{f['id']}/calls", json={"operator": "human"}, headers=hw).json()
    assert call["audience"] == "other" and "pregnan" not in call["turns"][0]["text_en"].lower()
    call = client.post(f"{API}/calls/{call['id']}/answer", json={"text": "Yes, I will tell her"}, headers=hw).json()
    assert call["outcome"] == "message_left"
    f = next(x for x in client.get(f"{API}/followups", headers=hw).json() if x["id"] == f["id"])
    assert f["attempts"][-1]["outcome"] == "call" and f["attempts"][-1]["call_outcome"] == "message_left"
    # She comes back: a new pregnancy visit closes the follow-up and its alert
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "maternal", "language": "en", "chief_complaint": "ANC visit",
            "consent_id": e["consent"]["id"], "client_ref": f"w_{uuid.uuid4().hex}"}
    assert client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).status_code == 200
    assert not any(x["id"] == f["id"] for x in client.get(f"{API}/followups", headers=hw).json())
    assert next(a for a in client.get(f"{API}/alerts", headers=mo).json() if a["key"] == f["id"])["status"] == "resolved"


def test_own_phone_mentions_the_checkup_and_no_phone_cannot_be_called(client, nurse, hw):
    past = (date.today() - timedelta(days=2)).isoformat()
    _, _ = intake(client, nurse, name="Gita Bai", age=22, sex="F", phone="9822233344", category="maternal", chief_complaint="ANC",
                  maternal={"gestation_weeks": 20, "next_checkup": past, "phone_belongs_to": "self", "assigned_worker_id": "usr_hw1"})
    f = next(x for x in client.get(f"{API}/followups", headers=hw).json() if x["patient_name"] == "Gita Bai")
    assert "pregnancy check-up" in f["call_script"]
    _, _ = intake(client, nurse, name="Rani Kumari", age=23, sex="F", category="maternal", chief_complaint="ANC",
                  maternal={"gestation_weeks": 22, "next_checkup": past, "assigned_worker_id": "usr_hw1"})
    f = next(x for x in client.get(f"{API}/followups", headers=hw).json() if x["patient_name"] == "Rani Kumari")
    assert f["call_script"] is None and f["phone_belongs_to"] == "none"
    assert f["who_calls"]["who"] == "home_visit"
    assert client.post(f"{API}/followups/{f['id']}/calls", json={}, headers=hw).status_code == 422


def test_health_worker_list_for_assignment(client, nurse, employer):
    hws = client.get(f"{API}/health-workers", headers=nurse).json()
    assert {"id": "usr_hw1", "name": "Kamla Devi (ASHA)"} in hws
    assert client.get(f"{API}/health-workers", headers=employer).status_code == 403


def test_assigned_worker_must_be_a_health_worker_here(client, nurse):
    pat = client.post(f"{API}/patients", json={"name": "Asha Test", "age": 25, "sex": "F", "language": "en"}, headers=nurse).json()
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=nurse).json()
    body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "maternal", "language": "en", "chief_complaint": "ANC",
            "maternal": {"next_checkup": date.today().isoformat(), "assigned_worker_id": "usr_doc1"}, "consent_id": con["id"], "client_ref": f"w_{uuid.uuid4().hex}"}
    assert client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).status_code == 422


def test_household_phone_reminder_says_nothing_reproductive(client):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Patient, Reminder

    with SessionLocal() as db:  # reminders go to a phone the household shares (JVA-P001 and JVA-P003)
        rems = list(db.scalars(select(Reminder).join(Patient, Reminder.patient_id == Patient.id).where(Patient.phone == "9876543210")))
    assert rems
    for r in rems:
        assert "pregnan" not in r.message.lower() and "anc" not in r.message.lower()


# ── SQLite: columns added after the database was made ─
def test_sqlite_adds_missing_columns(tmp_path):
    import sqlalchemy as sa

    from app import db as dbmod

    eng = sa.create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:
        c.execute(sa.text("CREATE TABLE reminders (id VARCHAR(64) PRIMARY KEY, patient_id VARCHAR(64), kind VARCHAR(20), due_at DATETIME, channel VARCHAR(8), status VARCHAR(12), message TEXT)"))
    old = dbmod.engine
    dbmod.engine = eng
    try:
        dbmod._add_missing_columns()
    finally:
        dbmod.engine = old
    cols = {c["name"] for c in sa.inspect(eng).get_columns("reminders")}
    assert {"facility_id", "assigned_to", "phone_belongs_to", "attempts", "missed_at"} <= cols


def test_sqlite_adds_required_columns_with_their_default(tmp_path):
    import sqlalchemy as sa

    from app import db as dbmod

    eng = sa.create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:
        c.execute(sa.text("CREATE TABLE facilities (id VARCHAR(64) PRIMARY KEY, name VARCHAR(200))"))
        c.execute(sa.text("INSERT INTO facilities VALUES ('f1', 'Old PHC')"))
    old = dbmod.engine
    dbmod.engine = eng
    try:
        dbmod._add_missing_columns()
    finally:
        dbmod.engine = old
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT patient_load FROM facilities")).scalar() == "normal"
