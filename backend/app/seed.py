"""Minimal sample data: two facilities, sample staff accounts, three sample patients and one kiosk link.
Everything else is created by real use. No real patient records.

Run: python -m app.seed [--reset]
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import audit, storage
from .db import Base, SessionLocal, engine, init_db
from .models import Consent, Device, Facility, FileObject, FitnessAssessment, Organisation, Patient, Reminder, User
from .config import get_settings
from .security import PIN_ROLES, hash_pin
from .services import create_encounter, local_day
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
    dict(id="fac_kalinganagar", name="Kalinganagar Industrial Estate Health Unit", type="industrial_unit", district="Jajpur", state="Odisha", languages=["or", "hi", "en"],
         specialists=[{"key": "genmed", "label": "Occupational Health Physician", "available": True, "schedule": "Shift A & B"},
                      {"key": "ortho", "label": "Orthopaedics", "available": False, "schedule": "Visiting Saturday"},
                      {"key": "burns", "label": "Burns & Plastic Surgery", "available": False, "schedule": None}],
         referral_destination="SCB Medical College, Cuttack (95 km)", beds_total=6, beds_occupied=1, offline_mode=False,
         capabilities={"lab": False, "xray": True, "ecg": True, "oxygen": True, "ambulance": True, "pharmacy": True}),
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
    ("pat_002", "JVA-P002", "Lakshmi Devi", 55, "F", "9880111223", "kn", "chronic", "Mau", None),
    ("pat_003", "JVA-P003", "Priya Sharma", 24, "F", "9876543210", "hi", "maternal", "Manikpur", None),
]


def sym(text, original=None, language="en", source="voice"):
    return {"text": text, "original_text": original or text, "language": language, "source": source, "confirmed_by_readback": source == "voice"}


HISTORY = [
    dict(patient="pat_002", ago=90 * DAY, category="chronic", language="kn", chief="Diabetes check-in", symptoms=[sym("More thirst than usual")], vitals={"glucose": 265, "bp_systolic": 130, "bp_diastolic": 82}, chronic={"condition": "Type 2 diabetes", "feeling_vs_last": "worse"}),
]

TODAY = [
    dict(patient="pat_001", ago=8 * MIN, category="normal", language="hi", chief="Chest pain radiating to left arm",
         symptoms=[sym("Chest pain since 2 hours going to the left arm, sweating a lot", "दो घंटे से सीने में दर्द है जो बाएं हाथ तक जा रहा है, बहुत पसीना आ रहा है", "hi")],
         selected=["Sweating"], duration="2 hours", severity=8, vitals={"bp_systolic": 160, "bp_diastolic": 100, "pulse": 104, "spo2": 97, "temp_f": 98.2},
         reports=["lipid"], proxy=("Ramesh Kumar", "Husband")),
    dict(patient="pat_002", ago=38 * MIN, category="chronic", language="kn", chief="Excess thirst and blurred vision (diabetic)",
         symptoms=[sym("Passing urine very often, always thirsty, vision blurry, very tired", "ಬಾಯಾರಿಕೆ ಹೆಚ್ಚು, ಕಣ್ಣು ಮಂದ", "kn")],
         selected=["Tiredness"], duration="2 weeks", severity=5, vitals={"glucose": 318, "bp_systolic": 132, "bp_diastolic": 84, "pulse": 82},
         chronic={"condition": "Type 2 diabetes", "last_checkup": "3 months ago", "current_medicines": "Metformin 500 BD, Glimepiride 1 OD — misses doses", "feeling_vs_last": "worse"}, reports=["glucose"]),
    dict(patient="pat_003", ago=62 * MIN, category="maternal", language="hi", chief="Routine antenatal visit, mild headache",
         symptoms=[sym("Came for regular checkup, slight headache since morning", "नियमित जांच, सुबह से हल्का सिरदर्द", "hi")], duration="since morning", severity=2,
         vitals={"bp_systolic": 118, "bp_diastolic": 76, "pulse": 78, "spo2": 99, "temp_f": 98.2},
         maternal={"gestation_weeks": 28, "anc_visits": 3, "next_checkup": (NOW + 14 * DAY).date().isoformat(), "reminder_channel": "sms"}),
]

SAMPLE_ORG = dict(id="org_kalinganagar", name="Kalinga Steel Works (sample)", kind="industrial", state="Odisha", district="Jajpur", verified=False)
SAMPLE_WORKERS = [  # employee code, department, fitness status (None = not yet assessed), days since assessment
    ("KSW-1041", "Furnace", "fit", 12),
    ("KSW-1043", "Furnace", "fit_with_restrictions", 11),
    ("KSW-1045", "Furnace", None, None),
]


def seed(db) -> None:
    if db.scalar(select(Facility.id).limit(1)):
        return
    audit.record(db, None, "CONFIG", "system", None, "Demo database seeded with synthetic data", ts=NOW - DAY)
    db.add(Organisation(**SAMPLE_ORG))
    db.flush()
    for f in FACILITIES:
        org = {"organisation_id": SAMPLE_ORG["id"], "source": "organisation"} if f["id"] == "fac_kalinganagar" else {"source": "sample"}
        db.add(Facility(**f, **org))
    db.flush()
    for uid, phone, name, role, fac, reg, lang in USERS:
        u = User(id=uid, phone=phone, name=name, role=role, facility_id=fac, registration_no=reg, language=lang, created_at=NOW - 60 * DAY, organisation_id=SAMPLE_ORG["id"] if role == "employer" else None)
        if role in PIN_ROLES:
            u.pin_hash, u.pin_set_at = hash_pin(get_settings().demo_pin, uid), NOW
        db.add(u)
    for pid, code, name, age, sex, phone, lang, cat, village, emp in PATIENTS:
        db.add(Patient(id=pid, code=code, name=name, age=age, sex=sex, phone=phone, language=lang, category=cat, village=village, employer_id=emp, created_at=NOW - 100 * DAY))
    db.add(Device(id="dev_kiosk_manikpur_1", label="OPD entrance tablet", facility_id="fac_phc_manikpur", bound_by="Meera Nair", bound_by_id="usr_sup1", bound_at=NOW - 20 * DAY, last_seen_at=NOW))
    db.flush()
    for code, dept, status, days in SAMPLE_WORKERS:
        pid = f"pat_w_{code.lower().replace('-', '_')}"
        db.add(Patient(id=pid, code=f"JVA-{code}", name=f"Worker {code} (sample)", age=30, sex="M", phone=None, language="or", category="normal", organisation_id=SAMPLE_ORG["id"], employee_code=code, department=dept, created_at=NOW - 100 * DAY))
        db.flush()
        if status:
            db.add(FitnessAssessment(patient_id=pid, organisation_id=SAMPLE_ORG["id"], status=status, restrictions="No work at height" if status == "fit_with_restrictions" else None, assessed_by="Occupational Health Physician (sample)", assessed_at=NOW - days * DAY))
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
            f.storage_key = storage.put(f.id, svg.encode(), "image/svg+xml", storage.folder_for("fac_phc_manikpur", "report"))
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
            enc.token, enc.token_date = None, local_day(created)
        audit.record(db, None, "CREATE", "encounter", enc.id, f"Intake captured ({s['category']}); rules engine: {enc.urgency}", p.code, enc.facility_id, ts=created)
        if enc.note and enc.note["disagreements"]:
            detail = "; ".join(f"{d['field']}: " + " vs ".join(v["value"] for v in d["values"]) for d in enc.note["disagreements"])
            audit.record(db, None, "DISAGREEMENT", "encounter", enc.id, detail, p.code, enc.facility_id, ts=created)

    db.add(Reminder(patient_id="pat_003", kind="anc_checkup", due_at=NOW + 14 * DAY, channel="sms", status="scheduled", message="ANC check-up at PHC Manikpur (30 weeks). Bring your MCP card."))

    from .routers.kiosk import create_link

    create_link(db, "fac_phc_manikpur", "OPD waiting area", None, code="MANIKPUR")
    db.commit()


def main() -> None:
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as db:
        seed(db)
    print("Seeded minimal sample data.")


if __name__ == "__main__":
    main()
