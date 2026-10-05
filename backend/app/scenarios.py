"""Demo scenarios for the Wednesday features, added on top of the minimal seed. Synthetic people only.

* Campus (D3): a campus health centre with four fevers from Hostel Block C in the last two days. One more fever from
  Block C, entered live at its kiosk link (code CAMPUS01), raises the cluster alert to the campus medical officer.
* Maternal follow-up (D4): Sunita's check-up at PHC Manikpur was due three days ago; she is assigned to ASHA Kamla
  Devi and her number is her husband's phone, so any reminder is worded without mentioning pregnancy.
* Capacity (C3): PHC Manikpur has two RED cases and two doctors on duty. Marking one doctor off duty from the front
  desk raises the capacity alert to the medical officer.
* Occupational (D2): Kalinga Steel Works workers screened today in three departments (6 crusher, 6 furnace, 5
  stores); the crusher workers were also screened last year, so FEV1 is compared with their own earlier value.

Run once (idempotent): python -m app.scenarios. The server also runs it at start-up when JEEVIA_SEED_SCENARIOS is true.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import audit
from .config import get_settings
from .models import Consent, Device, Encounter, Facility, Organisation, Patient, Reminder, User
from .security import hash_pin
from .services import create_encounter, local_day

MARKER = "fac_campus_demo"
NORMAL = {"bp_systolic": 118, "bp_diastolic": 76, "pulse": 84, "spo2": 98, "resp_rate": 16, "temp_f": 98.6, "avpu": "A"}


def _consent(db, p: Patient, lang: str, when: datetime) -> Consent:
    c = Consent(patient_id=p.id, mode="self", privacy_context="private", language=lang, scopes=["triage", "share_with_treating_team"],
                captured_by="Demo scenario", captured_at=when)
    db.add(c)
    db.flush()
    return c


def _visit(db, p: Patient, facility: str, when: datetime, chief: str, *, lang="en", vitals=None, closed=False, exam=True, **extra) -> Encounter:
    c = _consent(db, p, lang, when)
    intake = {"patient_id": p.id, "facility_id": facility, "category": extra.pop("category", "normal"), "language": lang, "chief_complaint": chief,
              "symptoms": [{"text": chief, "original_text": chief, "language": "en", "source": "text"}], "selected_symptoms": [], "answers": [],
              "file_ids": [], "vitals": vitals, "consent_id": c.id, "client_ref": f"scn_{uuid.uuid4().hex[:10]}", "captured_offline": False,
              "captured_at": None, **({"exam": {"done": True, "signs": [], "by": "Demo nurse", "at": when.isoformat()}} if exam else {}), **extra}
    e = create_encounter(db, intake, p, when)
    if closed:
        e.status, e.reviewed_by, e.reviewed_at = "closed", "Demo clinician", when
        e.token, e.token_date = None, local_day(when)
    audit.record(db, None, "CREATE", "encounter", e.id, f"Demo scenario intake; rules engine: {e.urgency}", p.code, facility, ts=when)
    return e


def _patient(db, code: str, name: str, age: int, sex: str, **kw) -> Patient:
    p = db.scalar(select(Patient).where(Patient.code == code))
    if p:
        return p
    p = Patient(code=code, name=name, age=age, sex=sex, language=kw.pop("language", "en"), **kw)
    db.add(p)
    db.flush()
    return p


def _user(db, uid: str, phone: str, name: str, role: str, facility: str, reg: str | None, lang: str = "en") -> None:
    if db.get(User, uid) or db.scalar(select(User.id).where(User.phone == phone)):
        return
    u = User(id=uid, phone=phone, name=name, role=role, facility_id=facility, registration_no=reg, language=lang)
    u.pin_hash, u.pin_set_at = hash_pin(get_settings().demo_pin, uid), datetime.now(timezone.utc)
    db.add(u)


def scenarios(db) -> bool:
    """Add the demo scenarios once. Returns False when they are already there or the base seed is missing."""
    if db.get(Facility, MARKER) or not db.get(Facility, "fac_phc_manikpur") or not db.get(Organisation, "org_kalinganagar"):
        return False
    now = datetime.now(timezone.utc)
    h, d = timedelta(hours=1), timedelta(days=1)

    # ── D3 campus ──
    db.add(Organisation(id="org_campus_demo", name="Sample Technical University (campus)", kind="campus", state="Odisha", district="Khordha", verified=False))
    db.flush()
    db.add(Facility(id=MARKER, name="Campus Health Centre (sample)", type="campus", district="Khordha", state="Odisha", languages=["or", "hi", "en"],
                    specialists=[{"key": "genmed", "label": "General Medicine", "available": True, "schedule": "Daily 8–8"}],
                    referral_destination="District Headquarters Hospital, Khordha", beds_total=4, beds_occupied=0, offline_mode=False,
                    capabilities={"lab": True, "xray": False, "ecg": True, "oxygen": True, "ambulance": True, "pharmacy": True},
                    source="organisation", organisation_id="org_campus_demo"))
    db.flush()
    _user(db, "usr_mo_campus", "9000000008", "Dr. Sneha Mohanty (Campus Medical Officer)", "medical_officer", MARKER, "OMC-30418")
    _user(db, "usr_nurse_campus", "9000000009", "Pratima Behera (Staff Nurse)", "nurse", MARKER, "ONC-11872", "or")
    db.add(Device(id="dev_kiosk_campus_1", label="Campus clinic tablet", facility_id=MARKER, bound_by="Demo scenario", bound_at=now - 5 * d, last_seen_at=now))
    db.flush()
    from .routers.kiosk import create_link

    create_link(db, MARKER, "Campus clinic waiting room", None, code="CAMPUS01")
    students = [("C", 40, 101.8), ("C", 30, 100.9), ("C", 20, 102.2), ("C", 6, 100.6), ("A", 26, 99.0), ("A", 9, 101.0)]
    for i, (block, ago, temp) in enumerate(students):
        p = _patient(db, f"JVA-S{101 + i}", f"Student {101 + i} (sample)", 19 + i % 4, "M" if i % 2 else "F")
        _visit(db, p, MARKER, now - ago * h, "Fever with body ache", vitals={**NORMAL, "temp_f": temp},
               closed=ago > 12, cluster_key=f"Hostel Block {block}", duration="1-2 days", severity=4)
    p = _patient(db, "JVA-S120", "Student 120 (sample)", 21, "M")
    _visit(db, p, MARKER, now - 9 * d, "Fever since yesterday", vitals={**NORMAL, "temp_f": 100.8}, closed=True, cluster_key="Hostel Block C")

    # ── D4 maternal missed visit ──
    sunita = _patient(db, "JVA-P201", "Sunita Kewat", 23, "F", phone="9811000001", language="hi", category="maternal", village="Bhanpur")
    e = _visit(db, sunita, "fac_phc_manikpur", now - 31 * d, "Routine antenatal visit", lang="hi", vitals=NORMAL, closed=True, category="maternal",
               maternal={"gestation_weeks": 24, "anc_visits": 2, "next_checkup": (now - 3 * d).date().isoformat(), "reminder_channel": "voice",
                         "phone_belongs_to": "husband", "assigned_worker_id": "usr_hw1"})
    db.add(Reminder(patient_id=sunita.id, kind="anc_checkup", due_at=now - 3 * d, channel="voice", status="scheduled", facility_id="fac_phc_manikpur",
                    assigned_to="usr_hw1", phone_belongs_to="husband", encounter_id=e.id,
                    message=f"Namaste. This is PHC Manikpur. Please ask Sunita to visit PHC Manikpur on {(now - 3 * d).strftime('%d %b')}."))

    # ── C3 a second RED at PHC Manikpur (with two doctors on duty, one off duty tips it over) ──
    ramesh = _patient(db, "JVA-P202", "Ramesh Yadav", 35, "M", language="hi", village="Bhanpur")
    _visit(db, ramesh, "fac_phc_manikpur", now - 15 * timedelta(minutes=1), "Snake bite on the foot one hour ago, gums bleeding", lang="hi",
           vitals={**NORMAL, "pulse": 112, "bp_systolic": 102, "bp_diastolic": 64}, exam=False, duration="1 hour", severity=7)

    # ── D2 workplace screening at Kalinga Steel Works ──
    _user(db, "usr_doc_ksw", "9000000010", "Dr. Bikash Sahoo (Occupational Health Physician)", "doctor", "fac_kalinganagar", "OMC-27741")
    crusher = [  # code, years, cough weeks, last year's FEV1, today's FEV1, PPE worn, complaint
        ("KSW-2101", 9, 10, 3.4, 3.2, "sometimes", "Cough for more than two months"),
        ("KSW-2102", 12, 3, 3.3, 3.2, "always", "Cough for three weeks, losing weight"),
        ("KSW-2103", 6, None, 3.6, 2.9, "always", "Annual screening, feels well"),
        ("KSW-2104", 3, None, 3.8, 3.7, "never", "Annual screening"),
        ("KSW-2105", 7, None, 3.5, 3.4, "sometimes", "Annual screening"),
        ("KSW-2106", 2, None, 4.0, 3.9, "always", "Annual screening"),
    ]
    for code, yrs, cough, fev_then, fev_now, ppe, chief in crusher:
        p = _patient(db, f"JVA-{code}", f"Worker {code} (sample)", 28 + yrs, "M", language="or", organisation_id="org_kalinganagar", employee_code=code, department="Crusher")
        _visit(db, p, "fac_kalinganagar", now - 330 * d, "Annual screening", vitals=NORMAL, closed=True,
               occupational={"exposures": ["silica"], "years_exposed": yrs - 1, "fev1_l": fev_then, "ppe_issued": True, "ppe_used": "always"})
        _visit(db, p, "fac_kalinganagar", now - (2 + len(code) % 3) * h, chief, vitals=NORMAL, duration="more than a month" if cough else None,
               occupational={"exposures": ["silica"], "years_exposed": yrs, "cough_weeks": cough, "fev1_l": fev_now, "fvc_l": round(fev_now * 1.25, 1),
                             "breathless_vs_last": "same", "ppe_issued": True, "ppe_used": ppe})
    furnace = [p for p in db.scalars(select(Patient).where(Patient.organisation_id == "org_kalinganagar", Patient.department == "Furnace"))]
    for i in range(len(furnace), 6):
        furnace.append(_patient(db, f"JVA-KSW-31{i:02d}", f"Worker KSW-31{i:02d} (sample)", 33, "M", language="or", organisation_id="org_kalinganagar",
                                employee_code=f"KSW-31{i:02d}", department="Furnace"))
    for i, p in enumerate(furnace):
        _visit(db, p, "fac_kalinganagar", now - 5 * h, "Annual screening", vitals=NORMAL, closed=True,
               occupational={"exposures": ["heat", "noise"], "years_exposed": 4 + i, "breathless_vs_last": "same", "ppe_issued": True, "ppe_used": "always" if i % 3 else "sometimes"})
    for i in range(5):
        p = _patient(db, f"JVA-KSW-41{i:02d}", f"Worker KSW-41{i:02d} (sample)", 30 + i, "M", language="or", organisation_id="org_kalinganagar",
                     employee_code=f"KSW-41{i:02d}", department="Stores")
        _visit(db, p, "fac_kalinganagar", now - 6 * h, "Annual screening", vitals=NORMAL, closed=True,
               occupational={"exposures": ["noise"], "years_exposed": 2 + i, "breathless_vs_last": "same", "ppe_issued": True, "ppe_used": "always"})

    audit.record(db, None, "CONFIG", "system", None, "Demo scenarios added: campus fevers, missed maternal visit, second RED, workplace screening (synthetic)")
    db.commit()
    return True


def main() -> None:
    from .db import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        print("Demo scenarios added." if scenarios(db) else "Demo scenarios already present (or base seed missing).")


if __name__ == "__main__":
    main()
