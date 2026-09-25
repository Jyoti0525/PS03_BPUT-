"""Synthetic demo data. No real patient records — every name and value is invented.

Run: python -m app.seed [--reset]
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import audit, storage
from .db import Base, SessionLocal, engine, init_db
from .models import Cohort, Consent, Device, Facility, FileObject, Patient, Reminder, User
from .services import create_encounter
from .triage.reports import render

NOW = datetime.now(timezone.utc)
MIN = timedelta(minutes=1)
DAY = timedelta(days=1)

FACILITIES = [
    dict(id="fac_phc_manikpur", name="PHC Manikpur", type="phc", district="Chitrakoot", state="Uttar Pradesh", languages=["hi", "en"],
         specialists=[{"key": "genmed", "label": "General Medicine", "available": True, "schedule": "Daily"},
                      {"key": "obgyn", "label": "Obstetrics & Gynaecology", "available": False, "schedule": "Visiting Thursday"},
                      {"key": "cardio", "label": "Cardiology", "available": False, "schedule": None},
                      {"key": "pulmo", "label": "Pulmonology", "available": False, "schedule": None},
                      {"key": "paeds", "label": "Paediatrics", "available": False, "schedule": "Visiting Monday"},
                      {"key": "endo", "label": "Endocrinology", "available": False, "schedule": None}],
         referral_destination="District Hospital Gorakhpur (42 km)", beds_total=15, beds_occupied=11, offline_mode=True,
         capabilities={"lab": True, "xray": False, "ecg": True, "oxygen": True, "ambulance": True, "pharmacy": True, "labour_room": True}),
    dict(id="fac_dh_gorakhpur", name="District Hospital Gorakhpur", type="district_hospital", district="Gorakhpur", state="Uttar Pradesh", languages=["hi", "en", "bho"],
         specialists=[{"key": k, "label": l, "available": True, "schedule": s} for k, l, s in [("genmed", "General Medicine", "24×7"), ("obgyn", "Obstetrics & Gynaecology", "24×7"), ("cardio", "Cardiology", "OPD Mon–Sat"), ("pulmo", "Pulmonology", "OPD Tue/Fri"), ("paeds", "Paediatrics", "24×7"), ("endo", "Endocrinology", "OPD Wed")]],
         referral_destination="AIIMS Gorakhpur (super-speciality)", beds_total=250, beds_occupied=214, offline_mode=False,
         capabilities={"lab": True, "xray": True, "ecg": True, "oxygen": True, "ambulance": True, "pharmacy": True, "labour_room": True, "icu": True}),
    dict(id="fac_kalinganagar", name="Kalinganagar Industrial Estate Health Unit", type="industrial_unit", district="Jajpur", state="Odisha", languages=["or", "hi", "en"],
         specialists=[{"key": "genmed", "label": "Occupational Health Physician", "available": True, "schedule": "Shift A & B"},
                      {"key": "ortho", "label": "Orthopaedics", "available": False, "schedule": "Visiting Saturday"},
                      {"key": "burns", "label": "Burns & Plastic Surgery", "available": False, "schedule": None}],
         referral_destination="SCB Medical College, Cuttack (95 km)", beds_total=6, beds_occupied=1, offline_mode=False,
         capabilities={"lab": False, "xray": True, "ecg": True, "oxygen": True, "ambulance": True, "pharmacy": True}),
    dict(id="fac_bput_campus", name="BPUT Campus Health Centre", type="campus", district="Sundargarh", state="Odisha", languages=["or", "en", "hi"],
         specialists=[{"key": "genmed", "label": "General Medicine", "available": True, "schedule": "9am–5pm"},
                      {"key": "psych", "label": "Counsellor", "available": True, "schedule": "Tue/Thu"}],
         referral_destination="Ispat General Hospital, Rourkela (6 km)", beds_total=8, beds_occupied=2, offline_mode=False,
         capabilities={"lab": True, "xray": False, "ecg": False, "oxygen": True, "ambulance": True, "pharmacy": True}),
    dict(id="fac_koraput_camp", name="Public Health Camp — Koraput", type="health_camp", district="Koraput", state="Odisha", languages=["or", "hi"],
         specialists=[{"key": "genmed", "label": "Camp Medical Officer", "available": True, "schedule": "Camp days only"}],
         referral_destination="SLN Medical College, Koraput (18 km)", beds_total=0, beds_occupied=0, offline_mode=True,
         capabilities={"lab": False, "xray": False, "ecg": False, "oxygen": False, "ambulance": False, "pharmacy": True}),
]

USERS = [
    ("usr_doc1", "9000000001", "Dr. Deepa Sharma", "doctor", "fac_phc_manikpur", "UPMC-48921", "en"),
    ("usr_nurse1", "9000000002", "Sunita Yadav (ANM)", "nurse", "fac_phc_manikpur", "UPNC-22817", "hi"),
    ("usr_recep1", "9000000003", "Rakesh Tiwari", "receptionist", "fac_phc_manikpur", None, "hi"),
    ("usr_sup1", "9000000004", "Meera Nair", "supervisor", "fac_phc_manikpur", None, "en"),
    ("usr_emp1", "9000000005", "Arjun Patnaik (HR — Safety)", "employer", "fac_kalinganagar", None, "en"),
    ("usr_pat1", "9876543210", "Priya Sharma", "patient", None, None, "hi"),
]

PATIENTS = [
    ("pat_001", "JVA-P001", "Radha Kumari", 42, "F", "9876543210", "hi", "normal", "Manikpur", None),
    ("pat_002", "JVA-P002", "Suresh Babu", 68, "M", "9440123456", "te", "chronic", "Karwi", None),
    ("pat_003", "JVA-P003", "Ananya Roy", 26, "F", "9831098765", "bn", "maternal", "Manikpur", None),
    ("pat_005", "JVA-P005", "Lakshmi Devi", 55, "F", "9880111223", "kn", "chronic", "Mau", None),
    ("pat_008", "JVA-P008", "Priya Sharma", 24, "F", "9876543210", "hi", "maternal", "Manikpur", None),
    ("pat_010", "JVA-P010", "Aarav Singh", 3, "M", "9876543210", "hi", "normal", "Manikpur", None),
    ("pat_011", "JVA-P011", "Bikash Nayak", 34, "M", "9437001122", "or", "normal", "Kalinganagar", "emp_kalinga"),
    ("pat_012", "JVA-P012", "Ritika Mohanty", 20, "F", "9938112233", "or", "normal", "Rourkela", None),
]


def sym(text, original=None, language="en", source="voice"):
    return {"text": text, "original_text": original or text, "language": language, "source": source, "confirmed_by_readback": source == "voice"}


HISTORY = [
    dict(patient="pat_001", ago=60 * DAY, category="normal", language="hi", chief="BP follow-up", symptoms=[sym("Routine BP check", "BP जांच", "hi")], vitals={"bp_systolic": 138, "bp_diastolic": 86, "pulse": 84}),
    dict(patient="pat_001", ago=30 * DAY, category="normal", language="hi", chief="Headache and BP check", symptoms=[sym("Headache in the evenings", "शाम को सिरदर्द", "hi")], duration="1 week", vitals={"bp_systolic": 148, "bp_diastolic": 92, "pulse": 88}),
    dict(patient="pat_005", ago=180 * DAY, category="chronic", language="kn", chief="Diabetes check-in", symptoms=[sym("Sugar check")], vitals={"glucose": 210, "bp_systolic": 128, "bp_diastolic": 80}, chronic={"condition": "Type 2 diabetes", "feeling_vs_last": "same"}),
    dict(patient="pat_005", ago=90 * DAY, category="chronic", language="kn", chief="Diabetes check-in", symptoms=[sym("More thirst than usual")], vitals={"glucose": 265, "bp_systolic": 130, "bp_diastolic": 82}, chronic={"condition": "Type 2 diabetes", "feeling_vs_last": "worse"}),
    dict(patient="pat_003", ago=56 * DAY, category="maternal", language="bn", chief="ANC visit (24 weeks)", symptoms=[sym("Routine antenatal visit")], vitals={"bp_systolic": 118, "bp_diastolic": 76}, maternal={"gestation_weeks": 24}),
    dict(patient="pat_003", ago=28 * DAY, category="maternal", language="bn", chief="ANC visit (28 weeks)", symptoms=[sym("Routine antenatal visit")], vitals={"bp_systolic": 124, "bp_diastolic": 82}, maternal={"gestation_weeks": 28}),
    dict(patient="pat_008", ago=42 * DAY, category="maternal", language="hi", chief="ANC visit (22 weeks)", symptoms=[sym("Routine antenatal visit")], vitals={"bp_systolic": 116, "bp_diastolic": 74}, maternal={"gestation_weeks": 22}),
]

TODAY = [
    dict(patient="pat_001", ago=8 * MIN, category="normal", language="hi", chief="Chest pain radiating to left arm",
         symptoms=[sym("Chest pain since 2 hours going to the left arm, sweating a lot", "दो घंटे से सीने में दर्द है जो बाएं हाथ तक जा रहा है, बहुत पसीना आ रहा है", "hi")],
         selected=["Sweating", "Anxiety"], duration="2 hours", severity=8, answers=[{"qid": "q_onset", "question": "Did it start at rest?", "answer": "Yes, while sitting"}],
         vitals={"bp_systolic": 160, "bp_diastolic": 100, "pulse": 104, "spo2": 97, "temp_f": 98.2}, reports=["lipid"], proxy=("Ramesh Kumar", "Husband")),
    dict(patient="pat_002", ago=14 * MIN, category="chronic", language="te", chief="Breathlessness for 3 days (known COPD)",
         symptoms=[sym("Breathless for three days, yellow sputum, cannot walk to the toilet", "మూడు రోజులుగా ఆయాసం, పసుపు కఫం", "te")],
         selected=["Cough", "Fever"], duration="3 days", severity=7, vitals={"spo2": 89, "resp_rate": 28, "bp_systolic": 118, "bp_diastolic": 76, "pulse": 112},
         chronic={"condition": "COPD", "last_checkup": "3 months ago", "current_medicines": "Inhaler (name not known)", "feeling_vs_last": "worse"}),
    dict(patient="pat_003", ago=22 * MIN, category="maternal", language="bn", chief="Severe headache and blurred vision, 32 weeks pregnant",
         symptoms=[sym("Severe headache since yesterday, blurred vision, swelling in feet", "কাল থেকে প্রচণ্ড মাথাব্যথা, চোখে ঝাপসা দেখছি", "bn")],
         selected=["Swelling"], duration="1 day", severity=7, vitals={"bp_systolic": 148, "bp_diastolic": 96, "pulse": 96, "spo2": 98},
         maternal={"gestation_weeks": 32, "anc_visits": 3, "reminder_channel": "voice"}, reports=["anc"], proxy=("Sarita Roy", "Mother-in-law")),
    dict(patient="pat_010", ago=11 * MIN, category="normal", language="hi", chief="Child with high fever and one convulsion",
         symptoms=[sym("High fever since last night and had fits once this morning, very sleepy", "कल रात से तेज़ बुखार, सुबह एक बार झटके आए", "hi")],
         selected=["Fever", "Not feeding"], duration="1 day", vitals={"temp_f": 103.4, "pulse": 140, "resp_rate": 42}, proxy=("Radha Kumari", "Mother")),
    dict(patient="pat_005", ago=38 * MIN, category="chronic", language="kn", chief="Excess thirst and blurred vision (diabetic)",
         symptoms=[sym("Passing urine very often, always thirsty, vision blurry, very tired", "ಬಾಯಾರಿಕೆ ಹೆಚ್ಚು, ಕಣ್ಣು ಮಂದ", "kn")],
         selected=["Tiredness"], duration="2 weeks", severity=5, vitals={"glucose": 318, "bp_systolic": 132, "bp_diastolic": 84, "pulse": 82},
         chronic={"condition": "Type 2 diabetes", "last_checkup": "3 months ago", "current_medicines": "Metformin 500 BD, Glimepiride 1 OD — misses doses", "feeling_vs_last": "worse"}, reports=["glucose"]),
    dict(patient="pat_011", ago=26 * MIN, facility="fac_kalinganagar", category="normal", language="or", chief="Burn on forearm at work",
         symptoms=[sym("Hot metal splash burn on right forearm during shift", "କାମ କରିବା ସମୟରେ ହାତ ପୋଡ଼ିଗଲା", "or")], selected=["Injury"], duration="1 hour", severity=6,
         vitals={"bp_systolic": 128, "bp_diastolic": 82, "pulse": 96, "spo2": 99}),
    dict(patient="pat_012", ago=47 * MIN, facility="fac_bput_campus", category="normal", language="or", chief="Fever for 4 days with body ache",
         symptoms=[sym("Fever for four days with body ache and headache", "ଚାରି ଦିନ ହେଲା ଜ୍ୱର", "or")], selected=["Fever", "Body ache", "Headache"], duration="4 days", severity=5,
         vitals={"temp_f": 101.8, "pulse": 98, "spo2": 98, "bp_systolic": 112, "bp_diastolic": 72}, reports=["cbc"]),
    dict(patient="pat_008", ago=62 * MIN, category="maternal", language="hi", chief="Routine antenatal visit, mild headache",
         symptoms=[sym("Came for regular checkup, slight headache since morning", "नियमित जांच, सुबह से हल्का सिरदर्द", "hi")], duration="since morning", severity=2,
         vitals={"bp_systolic": 118, "bp_diastolic": 76, "pulse": 78, "spo2": 99, "temp_f": 98.2},
         maternal={"gestation_weeks": 28, "anc_visits": 3, "next_checkup": (NOW + 14 * DAY).date().isoformat(), "reminder_channel": "sms"}),
]

COHORTS = [
    dict(id="coh_furnace", name="Blast furnace — Shift A", employer_name="Kalinga Steel Works (synthetic)", screening_type="Periodic occupational health screening", facility_id="fac_kalinganagar",
         workers=[{"worker_code": c, "department": "Furnace", "fitness_status": s, "last_screened_at": (NOW - d * DAY).isoformat() if d is not None else None}
                  for c, s, d in [("KSW-1041", "fit", 12), ("KSW-1042", "fit", 12), ("KSW-1043", "fit_with_restrictions", 11), ("KSW-1044", "temporarily_unfit", 0.1), ("KSW-1045", "pending_review", None), ("KSW-1046", "fit", 10)]]),
    dict(id="coh_rolling", name="Rolling mill — Shift B", employer_name="Kalinga Steel Works (synthetic)", screening_type="Heat-stress screening (summer)", facility_id="fac_kalinganagar",
         workers=[{"worker_code": c, "department": "Rolling mill", "fitness_status": s, "last_screened_at": (NOW - d * DAY).isoformat() if d is not None else None}
                  for c, s, d in [("KSW-2201", "fit", 3), ("KSW-2202", "fit", 3), ("KSW-2203", "fit_with_restrictions", 4), ("KSW-2204", "pending_review", None)]]),
]


def seed(db) -> None:
    if db.scalar(select(Facility.id).limit(1)):
        return
    audit.record(db, None, "CONFIG", "system", None, "Demo database seeded with synthetic data", ts=NOW - DAY)
    for f in FACILITIES:
        db.add(Facility(**f))
    db.flush()
    for uid, phone, name, role, fac, reg, lang in USERS:
        db.add(User(id=uid, phone=phone, name=name, role=role, facility_id=fac, registration_no=reg, language=lang, created_at=NOW - 60 * DAY))
    for pid, code, name, age, sex, phone, lang, cat, village, emp in PATIENTS:
        db.add(Patient(id=pid, code=code, name=name, age=age, sex=sex, phone=phone, language=lang, category=cat, village=village, employer_id=emp, created_at=NOW - 100 * DAY))
    db.add(Device(id="dev_kiosk_manikpur_1", label="OPD entrance tablet", facility_id="fac_phc_manikpur", bound_by="Meera Nair", bound_by_id="usr_sup1", bound_at=NOW - 20 * DAY, last_seen_at=NOW))
    for c in COHORTS:
        db.add(Cohort(**c))
    db.flush()

    for i, s in enumerate(HISTORY + TODAY):
        p = db.get(Patient, s["patient"])
        created = NOW - s["ago"]
        file_ids = []
        for key in s.get("reports", []):
            svg, boxes = render(key, p.name)
            f = FileObject(filename=f"{key}_report_{p.code}.svg", content_type="image/svg+xml", size=len(svg), kind="report", uploaded_at=created, expires_at=storage.expiry_for("report", NOW), sample_key=key, boxes=boxes)
            db.add(f)
            db.flush()
            f.storage_key = f.id
            storage.put(f.id, svg.encode())
            file_ids.append(f.id)
        proxy = s.get("proxy")
        con = Consent(patient_id=p.id, mode="proxy" if proxy else "self", proxy_name=proxy[0] if proxy else None, proxy_relation=proxy[1] if proxy else None,
                      privacy_context="private", language=s["language"], scopes=["triage", "share_with_treating_team"], captured_by="Sunita Yadav (ANM)", captured_at=created)
        db.add(con)
        db.flush()
        intake = {
            "patient_id": p.id, "facility_id": s.get("facility", "fac_phc_manikpur"), "category": s["category"], "language": s["language"],
            "chief_complaint": s["chief"], "symptoms": s["symptoms"], "selected_symptoms": s.get("selected", []), "duration": s.get("duration"),
            "severity": s.get("severity"), "answers": s.get("answers", []), "file_ids": file_ids, "vitals": s.get("vitals"),
            "maternal": s.get("maternal"), "chronic": s.get("chronic"), "consent_id": con.id, "client_ref": f"seed_{i}_{uuid.uuid4().hex[:6]}",
            "captured_offline": False, "captured_at": None,
        }
        enc = create_encounter(db, intake, p, created)
        if s in HISTORY:
            enc.status, enc.reviewed_by, enc.reviewed_at = "closed", "Dr. Deepa Sharma", created
        audit.record(db, None, "CREATE", "encounter", enc.id, f"Intake captured ({s['category']}); rules engine: {enc.urgency}", p.code, enc.facility_id, ts=created)
        if enc.note and enc.note["disagreements"]:
            detail = "; ".join(f"{d['field']}: " + " vs ".join(v["value"] for v in d["values"]) for d in enc.note["disagreements"])
            audit.record(db, None, "DISAGREEMENT", "encounter", enc.id, detail, p.code, enc.facility_id, ts=created)

    for pid, kind, days, ch, status, msg in [
        ("pat_008", "anc_checkup", 14, "sms", "scheduled", "ANC check-up at PHC Manikpur (30 weeks). Bring your MCP card."),
        ("pat_008", "anc_checkup", -14, "voice", "done", "ANC check-up (26 weeks) — completed."),
        ("pat_003", "anc_checkup", 7, "voice", "scheduled", "ANC check-up (33 weeks) — voice call in Bengali."),
        ("pat_005", "chronic_checkin", 30, "sms", "scheduled", "Monthly sugar check-in. Bring your glucometer diary."),
    ]:
        db.add(Reminder(patient_id=pid, kind=kind, due_at=NOW + days * DAY, channel=ch, status=status, message=msg))

    old = NOW - 4 * DAY
    db.add(FileObject(filename="voice_intake_JVA-P002.webm", content_type="audio/webm", size=182_000, kind="audio", uploaded_at=old, expires_at=old + timedelta(hours=24), purged_at=old + timedelta(hours=25)))
    db.add(FileObject(filename="rash_photo_JVA-P012.jpg", content_type="image/jpeg", size=412_000, kind="image", uploaded_at=old, expires_at=old + timedelta(hours=72)))
    audit.record(db, None, "PURGE", "file", None, "Raw audio voice_intake_JVA-P002.webm deleted after transcript confirmation (24h policy)", "JVA-P002", "fac_phc_manikpur", ts=old + timedelta(hours=25))
    db.commit()


def main() -> None:
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as db:
        seed(db)
    print("Seeded synthetic demo data.")


if __name__ == "__main__":
    main()
