"""Note-generation pipeline — interface + deterministic stub.

The production pipeline (IndicConformer/Bhashini ASR → IndicTrans2 → PaddleOCR + parrotlet layout
→ bounded BioMistral summary) is owned by the ML track and plugs in behind `build_note`. This stub
produces the same TriageNote shape from structured intake so the API and every reviewer screen
work end to end. It never assigns urgency (that is rules.evaluate) and never states a diagnosis.
"""

import re
import uuid
from datetime import datetime, timezone

from .reports import SAMPLE_REPORTS

FOLLOWUPS = [
    (r"chest", {"tag": "Onset", "question": "Did the chest discomfort start at rest or during effort?", "for_role": "doctor"}),
    (r"chest", {"tag": "ECG", "question": "Has a 12-lead ECG been recorded since arrival?", "for_role": "nurse"}),
    (r"fever|बुखार", {"tag": "Fever pattern", "question": "Is the fever continuous or does it come with chills at a fixed time?", "for_role": "health_worker"}),
    (r"fever|बुखार", {"tag": "Rash / bleeding", "question": "Any rash, gum bleeding or black stools since the fever began?", "for_role": "nurse"}),
    (r"breath|सांस", {"tag": "Speech", "question": "Can the patient speak full sentences without pausing for breath?", "for_role": "nurse"}),
    (r"headache|vision|blurred", {"tag": "Visual change", "question": "Any flashing lights, spots or blurred vision right now?", "for_role": "nurse"}),
    (r"cough", {"tag": "Duration", "question": "Has the cough lasted more than 2 weeks? Any blood in sputum?", "for_role": "health_worker"}),
    (r"abdominal|stomach|pet", {"tag": "Location", "question": "Where exactly is the pain — upper, lower, right or left side?", "for_role": "doctor"}),
    (r"burn|injury|fall", {"tag": "Mechanism", "question": "How and when did the injury happen? Any loss of consciousness?", "for_role": "nurse"}),
    (r"diarr|loose", {"tag": "Hydration", "question": "How many times has the child passed urine in the last 6 hours?", "for_role": "health_worker"}),
]


def _vid() -> str:
    return "v" + uuid.uuid4().hex[:10]


def _status(kind: str, n: float) -> str:
    if kind == "sys":
        return "abnormal" if n >= 160 or n < 90 else "borderline" if n >= 140 else "normal"
    if kind == "spo2":
        return "abnormal" if n < 90 else "borderline" if n <= 94 else "normal"
    if kind == "pulse":
        return "abnormal" if n > 120 or n < 50 else "borderline" if n > 100 else "normal"
    if kind == "temp":
        return "abnormal" if n >= 103 else "borderline" if n >= 100 else "normal"
    if kind == "rr":
        return "abnormal" if n >= 30 else "borderline" if n > 20 else "normal"
    if kind == "glucose":
        return "abnormal" if n > 300 or n < 70 else "borderline" if n > 140 else "normal"
    return "normal"


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def build_note(*, intake: dict, patient, hits: list[dict], files: list, history: list, proxy: bool) -> dict:
    v = {k: x for k, x in (intake.get("vitals") or {}).items() if x is not None}
    flags, vitals, labs, disagreements, missing = [], [], [], [], []
    voice = next((s for s in intake.get("symptoms", []) if s.get("source") == "voice"), None)

    def vsrc(label: str) -> dict:
        if voice and label in voice["text"].lower():
            return {"kind": "transcript", "engine": "IndicConformer ASR", "transcript_excerpt": voice["text"], "original_excerpt": voice["original_text"]}
        return {"kind": "manual", "engine": "Nurse entry at kiosk"}

    if v.get("bp_systolic") and v.get("bp_diastolic"):
        vitals.append({"id": _vid(), "label": "Blood pressure", "value": f"{_fmt(v['bp_systolic'])}/{_fmt(v['bp_diastolic'])}", "unit": "mmHg", "status": _status("sys", v["bp_systolic"]), "needs_check": False, "source": vsrc("bp")})
    if v.get("pulse"):
        vitals.append({"id": _vid(), "label": "Pulse", "value": _fmt(v["pulse"]), "unit": "bpm", "status": _status("pulse", v["pulse"]), "needs_check": False, "source": {"kind": "sensor", "engine": "Pulse oximeter"}})
    if v.get("spo2"):
        vitals.append({"id": _vid(), "label": "SpO₂", "value": _fmt(v["spo2"]), "unit": "%", "status": _status("spo2", v["spo2"]), "needs_check": v["spo2"] < 90, "source": {"kind": "sensor", "engine": "Pulse oximeter"}})
    if v.get("temp_f"):
        vitals.append({"id": _vid(), "label": "Temperature", "value": _fmt(v["temp_f"]), "unit": "°F", "status": _status("temp", v["temp_f"]), "needs_check": False, "source": {"kind": "sensor", "engine": "IR thermometer"}})
    if v.get("resp_rate"):
        vitals.append({"id": _vid(), "label": "Resp. rate", "value": _fmt(v["resp_rate"]), "unit": "/min", "status": _status("rr", v["resp_rate"]), "needs_check": False, "source": {"kind": "manual", "engine": "Nurse count"}})
    if v.get("glucose"):
        vitals.append({"id": _vid(), "label": "Glucose (POC)", "value": _fmt(v["glucose"]), "unit": "mg/dL", "status": _status("glucose", v["glucose"]), "needs_check": False, "source": {"kind": "sensor", "engine": "Glucometer"}})

    for f in files:
        if f.kind != "report":
            continue
        sample = SAMPLE_REPORTS.get(f.sample_key or "")
        if not sample:
            missing.append(f'Uploaded report "{f.filename}" is awaiting OCR — review the image directly')
            continue
        for i, row in enumerate(sample["rows"]):
            ev = {
                "id": _vid(),
                "label": row["test"],
                "value": row["value"],
                "unit": row["unit"] or None,
                "reference": row["ref"],
                "status": row["status"],
                "needs_check": False,
                "source": {
                    "kind": "image_crop",
                    "engine": "PaddleOCR + parrotlet layout (handwriting)" if sample.get("handwritten") else "PaddleOCR + parrotlet layout",
                    "file_id": f.id,
                    "bbox": f.boxes[i] if f.boxes and i < len(f.boxes) else None,
                    "crop_text": f"{row['test']}  {row['value']} {row['unit']}",
                },
            }
            if row.get("field") == "bp" and v.get("bp_systolic") and v.get("bp_diastolic"):
                kiosk = f"{_fmt(v['bp_systolic'])}/{_fmt(v['bp_diastolic'])}"
                if kiosk != row["value"]:
                    ev["needs_check"] = True
                    for x in vitals:
                        if x["label"] == "Blood pressure":
                            x["needs_check"] = True
                    disagreements.append({"field": "Blood pressure", "values": [{"engine": "Kiosk reading", "value": f"{kiosk} mmHg"}, {"engine": "OCR from card", "value": f"{row['value']} mmHg"}], "action": "Needs checking — re-measure during examination"})
            if row.get("field") == "glucose" and v.get("glucose") and abs(v["glucose"] - float(row["value"])) > 40:
                ev["needs_check"] = True
                disagreements.append({"field": "Blood glucose", "values": [{"engine": "Glucometer today", "value": f"{_fmt(v['glucose'])} mg/dL"}, {"engine": "OCR from slip", "value": f"{row['value']} mg/dL"}], "action": "Needs checking — confirm date of the lab slip"})
            labs.append(ev)

    for h in hits:
        if h["urgency"] == "green":
            continue
        flags.append({"code": h["rule_id"], "label": h["description"], "severity": "critical" if h["urgency"] == "red" else "warning", "reason": f"{h['protocol']} rule {h['rule_id']} matched on intake data"})
    for d in disagreements:
        flags.append({"code": "DISAGREE", "label": f"{d['field']}: sources disagree", "severity": "warning", "reason": d["action"]})
    if voice and not voice.get("confirmed_by_readback"):
        flags.append({"code": "ASR-UNCONFIRMED", "label": "Voice transcript not confirmed by read-back", "severity": "warning", "reason": "Patient skipped the spoken confirmation step"})
    if proxy:
        flags.append({"code": "PROXY", "label": "History given by a proxy", "severity": "info", "reason": "Consent and history captured from a family member or caregiver"})
    if intake.get("captured_offline"):
        flags.append({"code": "OFFLINE", "label": "Captured offline, synced later", "severity": "info", "reason": "Wait time is counted from the original capture time"})

    cat = intake.get("category")
    if not v.get("bp_systolic"):
        missing.append("Blood pressure not recorded")
    if not v.get("pulse") and not v.get("spo2"):
        missing.append("Pulse / SpO₂ not recorded")
    if not intake.get("duration"):
        missing.append("Duration of complaint not stated")
    if cat == "maternal" and not (intake.get("maternal") or {}).get("gestation_weeks"):
        missing.append("Gestational age not recorded")
    if cat == "chronic" and not (intake.get("chronic") or {}).get("current_medicines"):
        missing.append("Current medicines and adherence not recorded")
    if cat == "chronic" and not any(f.kind == "report" for f in files):
        missing.append("No recent lab report for chronic follow-up")

    text = " ".join([intake.get("chief_complaint", ""), *[s["text"] for s in intake.get("symptoms", [])], *intake.get("selected_symptoms", [])]).lower()
    followup = []
    for pat, q in FOLLOWUPS:
        if re.search(pat, text) and len(followup) < 5:
            followup.append(q)
    if not followup:
        followup.append({"tag": "Context", "question": "Anything else that changed recently — food, work, travel or medicines?", "for_role": "health_worker"})

    timeline = []
    for e in [e for e in history if e.intake][:3]:
        timeline.append({"when": e.created_at.strftime("%d/%m/%Y"), "event": f"Previous visit: {e.chief_complaint}"})
    if (intake.get("chronic") or {}).get("last_checkup"):
        timeline.append({"when": intake["chronic"]["last_checkup"], "event": f"Last {intake['chronic']['condition']} check-up"})
    if intake.get("duration"):
        timeline.append({"when": f"{intake['duration']} ago", "event": f"Onset: {intake['chief_complaint']}"})
    src = intake["symptoms"][0]["source"] if intake.get("symptoms") else "text"
    timeline.append({"when": "Today", "event": f"Intake at kiosk ({intake.get('language', 'en').upper()}, {src})"})

    trend = []
    ordered = list(reversed(history))
    bp_hist = [(e.intake.get("vitals") or {}).get("bp_systolic") for e in ordered]
    bp_hist = [x for x in bp_hist if x]
    if v.get("bp_systolic") and bp_hist:
        pts = [{"label": f"Visit {i + 1}", "value": x} for i, x in enumerate(bp_hist)] + [{"label": "Today", "value": v["bp_systolic"]}]
        d = pts[-1]["value"] - pts[0]["value"]
        trend.append({"parameter": "Systolic BP (mmHg)", "points": pts, "direction": "worse" if d > 8 else "better" if d < -8 else "stable"})
    g_hist = [x for x in [(e.intake.get("vitals") or {}).get("glucose") for e in ordered] if x]
    if v.get("glucose") and g_hist:
        pts = [{"label": f"Visit {i + 1}", "value": x} for i, x in enumerate(g_hist)] + [{"label": "Today", "value": v["glucose"]}]
        d = pts[-1]["value"] - pts[0]["value"]
        trend.append({"parameter": "Glucose (mg/dL)", "points": pts, "direction": "worse" if d > 20 else "better" if d < -20 else "stable"})

    sex = {"F": "female", "M": "male"}.get(patient.sex, "patient")
    parts = [
        f"{patient.age}-year-old {sex}, {'general' if cat == 'normal' else cat} visit.",
        f"Chief complaint: {intake['chief_complaint']}{' for ' + intake['duration'] if intake.get('duration') else ''}.",
    ]
    if intake.get("selected_symptoms"):
        parts.append(f"Also reports: {', '.join(intake['selected_symptoms'])}.")
    if intake.get("severity") is not None:
        parts.append(f"Self-rated severity {intake['severity']}/10.")
    if (intake.get("maternal") or {}).get("gestation_weeks"):
        parts.append(f"Pregnant, {intake['maternal']['gestation_weeks']} weeks by history.")
    if intake.get("chronic"):
        parts.append(f"Known {intake['chronic']['condition']}; patient feels {intake['chronic'].get('feeling_vs_last', 'unsure')} compared with last visit.")
    abn = [x for x in labs if x["status"] == "abnormal"]
    if abn:
        parts.append("Uploaded report shows " + ", ".join(f"{x['label']} {x['value']}{' ' + x['unit'] if x['unit'] else ''}" for x in abn) + " outside reference range.")
    parts.append("Summary organises patient-provided information only; it is not a diagnosis.")

    return {
        "summary": " ".join(parts),
        "flags": flags,
        "rules_fired": hits,
        "vitals": vitals,
        "labs": labs,
        "timeline": timeline,
        "missing_info": missing,
        "followup_questions": followup,
        "trend": trend,
        "disagreements": disagreements,
        "transcript": {"original": voice["original_text"], "translated": voice["text"], "language": voice["language"]} if voice else None,
        "generated_by": "stub-pipeline (rules v1 + template summariser)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def infer_specialist(intake: dict, age: int) -> str:
    t = " ".join([intake.get("chief_complaint", ""), *[s["text"] for s in intake.get("symptoms", [])]]).lower()
    if age < 12:
        return "paeds"
    if intake.get("category") == "maternal":
        return "obgyn"
    for pat, key in [(r"chest", "cardio"), (r"breath|copd|asthma", "pulmo"), (r"diabet|sugar|thirst", "endo"), (r"burn", "burns"), (r"fracture|fall", "ortho")]:
        if re.search(pat, t):
            return key
    return "genmed"
