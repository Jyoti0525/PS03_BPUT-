"""Triage-note builder.

Assembles the reviewer-facing TriageNote from the intake, the rules-engine result, uploaded
reports and visit history. Every value carries its source and the engine that produced it, named
truthfully. It never assigns urgency (that is rules.evaluate_full) and never states a diagnosis.
"""

import re
import uuid
from datetime import datetime, timezone

from .extraction import document_checks

# Follow-up questions keyed by findings (negation-aware), so "no chest pain" never asks about chest pain.
FOLLOWUPS = [
    ("chest_pain", {"tag": "Onset", "question": "Did the chest discomfort start at rest or during effort?", "for_role": "doctor"}),
    ("chest_pain", {"tag": "ECG", "question": "Has a 12-lead ECG been recorded since arrival?", "for_role": "nurse"}),
    ("fever", {"tag": "Fever pattern", "question": "Is the fever continuous or does it come with chills at a fixed time?", "for_role": "health_worker"}),
    ("fever", {"tag": "Rash / bleeding", "question": "Any rash, gum bleeding or black stools since the fever began?", "for_role": "nurse"}),
    ("breathless", {"tag": "Speech", "question": "Can the patient speak full sentences without pausing for breath?", "for_role": "nurse"}),
    ("headache", {"tag": "Visual change", "question": "Any flashing lights, spots or blurred vision right now?", "for_role": "nurse"}),
    ("cough", {"tag": "Duration", "question": "Has the cough lasted more than 2 weeks? Any blood in sputum?", "for_role": "health_worker"}),
    ("abdominal_pain", {"tag": "Location", "question": "Where exactly is the pain — upper, lower, right or left side?", "for_role": "doctor"}),
    ("injury", {"tag": "Mechanism", "question": "How and when did the injury happen? Any loss of consciousness?", "for_role": "nurse"}),
    ("diarrhoea", {"tag": "Hydration", "question": "How many times has the patient passed urine in the last 6 hours?", "for_role": "health_worker"}),
    ("weakness_general", {"tag": "Weakness", "question": "Is the weakness all over, or in one arm, leg or side of the face?", "for_role": "nurse"}),
    ("snake_bite", {"tag": "Envenomation", "question": "Time of bite? Any bleeding gums, drooping eyelids or difficulty swallowing?", "for_role": "doctor"}),
]


def _present(triage: dict, fid: str) -> bool:
    return (triage.get("findings") or {}).get(fid, {}).get("value") is True


def _vid() -> str:
    return "v" + uuid.uuid4().hex[:10]


def _status(kind: str, n: float) -> str:
    """Display colour for an adult vital: 'abnormal' at an ATP Red threshold, 'borderline' at an IITT
    high-risk limit or common clinical cut-off. Urgency itself always comes from the rules engine."""
    if kind == "sys":
        return "abnormal" if n > 220 or n < 90 else "borderline" if n >= 140 else "normal"
    if kind == "spo2":
        return "abnormal" if n < 90 else "borderline" if n < 94 else "normal"
    if kind == "pulse":
        return "abnormal" if n > 120 or n < 50 else "borderline" if n > 100 or n < 60 else "normal"
    if kind == "temp":
        return "abnormal" if n > 102.2 else "borderline" if n >= 100.4 or n < 96.8 else "normal"
    if kind == "rr":
        return "abnormal" if n > 22 or n < 10 else "borderline" if n > 20 else "normal"
    if kind == "glucose":
        return "abnormal" if n > 300 or n < 70 else "borderline" if n > 140 else "normal"
    return "normal"


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def build_note(*, intake: dict, patient, triage: dict, files: list, history: list, proxy: bool) -> dict:
    hits = triage["hits"]
    v = {k: x for k, x in (intake.get("vitals") or {}).items() if x is not None}
    flags, vitals, labs, disagreements, missing = [], [], [], [], []
    voice = next((s for s in intake.get("symptoms", []) if s.get("source") == "voice"), None)

    def vsrc(label: str) -> dict:
        if voice and label in voice["text"].lower():
            return {"kind": "transcript", "engine": voice.get("engine") or "Browser speech recognition", "transcript_excerpt": voice["text"], "original_excerpt": voice["original_text"]}
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
    if intake_avpu := (intake.get("vitals") or {}).get("avpu"):
        label = {"A": "Alert", "V": "Responds to voice", "P": "Responds to pain", "U": "Unresponsive"}.get(intake_avpu, intake_avpu)
        vitals.append({"id": _vid(), "label": "AVPU", "value": label, "unit": None, "status": "normal" if intake_avpu == "A" else "abnormal", "needs_check": False, "source": {"kind": "manual", "engine": "Clinician assessment"}})
    if v.get("glucose"):
        vitals.append({"id": _vid(), "label": "Glucose (POC)", "value": _fmt(v["glucose"]), "unit": "mg/dL", "status": _status("glucose", v["glucose"]), "needs_check": False, "source": {"kind": "sensor", "engine": "Glucometer"}})

    pregnant = (triage.get("findings") or {}).get("pregnant", {}).get("value") is True
    for f in files:
        if f.kind != "report":
            continue
        ex = f.extraction
        if not ex:
            missing.append(f'Uploaded report "{f.filename}" was not read — review the image directly')
            continue
        doc_warns = list(ex.get("warnings", [])) + document_checks(ex.get("meta") or {}, patient.name)
        for w in dict.fromkeys(doc_warns):
            flags.append({"code": "DOC-CHECK", "label": f'"{f.filename}": {w}', "severity": "warning", "reason": f"Document check on {ex['engine']}"})
        for row in ex.get("rows", []):
            ev = {
                "id": _vid(),
                "label": row["test"],
                "value": row["value"],
                "unit": row["unit"] or None,
                "reference": row.get("reference"),
                "status": row["status"],
                "needs_check": row["needs_check"],
                "checks": row.get("checks", []),
                "loinc": row.get("loinc"),
                "source": {
                    "kind": "image_crop",
                    "engine": ex["engine"],
                    "file_id": f.id,
                    "bbox": row.get("bbox"),
                    "crop_text": row.get("crop_text"),
                    "confidence": row.get("ocr_confidence"),
                },
            }
            if row["test_key"] == "haemoglobin" and pregnant and row.get("value_num") and row["value_num"] < 11:
                ev["status"] = "abnormal"
            if row["test_key"] == "bp" and v.get("bp_systolic") and v.get("bp_diastolic"):
                kiosk = f"{_fmt(v['bp_systolic'])}/{_fmt(v['bp_diastolic'])}"
                s_, d_ = row["values"]["systolic"], row["values"]["diastolic"]
                if abs(s_ - v["bp_systolic"]) > 10 or abs(d_ - v["bp_diastolic"]) > 10:
                    ev["needs_check"] = True
                    for x in vitals:
                        if x["label"] == "Blood pressure":
                            x["needs_check"] = True
                    disagreements.append({"field": "Blood pressure", "values": [{"engine": "Measured today", "value": f"{kiosk} mmHg"}, {"engine": f"Read from {f.filename}", "value": f"{row['value']} mmHg"}], "action": "Needs checking — re-measure during examination"})
            if row["test_key"].startswith("glucose") and v.get("glucose") and row.get("value_num") and abs(v["glucose"] - row["value_num"]) > 40:
                ev["needs_check"] = True
                disagreements.append({"field": "Blood glucose", "values": [{"engine": "Glucometer today", "value": f"{_fmt(v['glucose'])} mg/dL"}, {"engine": f"Read from {f.filename}", "value": f"{row['value']} mg/dL"}], "action": "Needs checking — confirm the date of the lab slip"})
            labs.append(ev)

    for h in hits:
        if h["urgency"] == "green":
            continue
        why = "; ".join(h.get("evidence") or []) or "matched on intake data"
        flags.append({"code": h["rule_id"], "label": h["description"], "severity": "critical" if h["urgency"] == "red" else "warning",
                      "reason": f"{why} — {h.get('source', h['protocol'])}", "non_downgradable": h.get("non_downgradable", False)})
    for d in disagreements:
        flags.append({"code": "DISAGREE", "label": f"{d['field']}: sources disagree", "severity": "warning", "reason": d["action"]})
    if voice and not voice.get("confirmed_by_readback"):
        flags.append({"code": "ASR-UNCONFIRMED", "label": "Voice transcript not confirmed by read-back", "severity": "warning", "reason": "Patient skipped the spoken confirmation step"})
    machine = [x for x in intake.get("symptoms", []) if x.get("original_text") and x.get("text") != x.get("original_text")]
    if machine:
        langs = ", ".join(sorted({x.get("language", "") for x in machine}))
        flags.append({"code": "MT-CHECK", "label": "Machine-translated history — check against the patient's own words", "severity": "info",
                      "reason": f"English rendered by {machine[0].get('engine') or 'machine translation'} from {langs}; rules also read the original-language text"})
    if proxy:
        flags.append({"code": "PROXY", "label": "History given by a proxy", "severity": "info", "reason": "Consent and history captured from a family member or caregiver"})
    if intake.get("captured_offline"):
        flags.append({"code": "OFFLINE", "label": "Captured offline, synced later", "severity": "info", "reason": "Wait time is counted from the original capture time"})

    cat = intake.get("category")
    for m in triage.get("missing_for_green", []):
        missing.append(f"{m[0].upper()}{m[1:]} not recorded — needed before the case can be routine")
    asks = sorted({n for u in triage.get("unresolved", []) if u["urgency"] == "red" for n in u["needs"] if not n.startswith("danger-sign")})
    for n in asks:
        if not any(n.lower() in x.lower() for x in missing):
            missing.append(f"Ask / measure: {n} (a RED rule depends on it)")
    if not intake.get("duration") and not any(a.get("qid") == "dur" for a in intake.get("answers", [])):
        missing.append("Duration of complaint not stated")
    if cat == "maternal" and not (intake.get("maternal") or {}).get("gestation_weeks"):
        missing.append("Gestational age not recorded")
    if cat == "chronic" and not (intake.get("chronic") or {}).get("current_medicines"):
        missing.append("Current medicines and adherence not recorded")
    if cat == "chronic" and not any(f.kind == "report" for f in files):
        missing.append("No recent lab report for chronic follow-up")

    followup = []
    for fid, q in FOLLOWUPS:
        if _present(triage, fid) and len(followup) < 5:
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
        "triage": {
            "provisional": triage["provisional"],
            "protocols": triage["protocols"],
            "unresolved": [{"rule_id": u["rule_id"], "urgency": u["urgency"], "description": u["description"], "needs": u["needs"]} for u in triage["unresolved"]],
            "missing_for_green": triage["missing_for_green"],
            "findings": triage["findings"],
            "rulepack_version": triage["rulepack_version"],
        },
        "vitals": vitals,
        "labs": labs,
        "timeline": timeline,
        "missing_info": missing,
        "followup_questions": followup,
        "trend": trend,
        "disagreements": disagreements,
        "transcript": {"original": voice["original_text"], "translated": voice["text"], "language": voice["language"]} if voice else None,
        "generated_by": f"rules engine (rulepack {triage['rulepack_version']}) + template summariser",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def infer_specialist(intake: dict, age: int, triage: dict | None = None) -> str:
    """Suggested specialist for the referral prompt — from negation-aware findings, never raw keywords."""
    if age < 12:
        return "paeds"
    if intake.get("category") == "maternal" or (triage and _present(triage, "pregnant")):
        return "obgyn"
    t = triage or {}
    for fids, key in [(("chest_pain",), "cardio"), (("breathless", "wheeze", "haemoptysis"), "pulmo"), (("burn",), "burns"),
                      (("limb_deformity", "fall_from_height"), "ortho")]:
        if any(_present(t, f) for f in fids):
            return key
    text = intake.get("chief_complaint", "").lower()
    if re.search(r"diabet|sugar", text) or (intake.get("chronic") or {}).get("condition", "").lower().startswith("diab"):
        return "endo"
    return "genmed"
