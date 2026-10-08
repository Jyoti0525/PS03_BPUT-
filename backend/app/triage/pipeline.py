"""Triage-note builder.

Assembles the reviewer-facing TriageNote from the intake, the rules-engine result, uploaded
reports and visit history. Every value carries its source and the engine that produced it, named
truthfully. It never assigns urgency (that is rules.evaluate_full) and never states a diagnosis.
"""

import re
import uuid
from datetime import date, datetime, timezone

from .. import asr_check, regions
from .extraction import document_checks
from .findings import FINDINGS, translation_check
from .timeline import onset

# Follow-up questions keyed by findings (negation-aware), so "no chest pain" never asks about chest pain. A key may
# also be "urgency:<tier>" or "rule:<id prefix>" (a fired rule). Each role sees its own questions, at most 3 per role
# (B7): health worker → health worker; nurse → health worker + nurse; doctor and medical officer → all.
FOLLOWUPS = [
    ("urgency:red", {"tag": "Transfer", "question": "If this patient must go on, are a vehicle (108 / 102) and a bed at the receiving hospital confirmed before they leave?", "for_role": "medical_officer"}),
    ("pregnant", {"tag": "Specialist", "question": "Does she need the obstetrician at the first referral unit today, and is blood available there?", "for_role": "medical_officer"}),
    ("rule:OCC-", {"tag": "Workplace", "question": "Should the worker be kept away from the exposure until reviewed? If silicosis or another listed disease is confirmed, it is notifiable (Factories Act 1948, s.89).", "for_role": "medical_officer"}),
    ("rule:OCC-SILICA-TB", {"tag": "TB test", "question": "Has a sputum sample been sent for NAAT (CBNAAT / Truenat) under NTEP?", "for_role": "nurse"}),
    ("rule:OCC-", {"tag": "PPE", "question": "Which mask or respirator does the worker wear, and is it worn for the whole shift?", "for_role": "health_worker"}),
    ("chest_pain", {"tag": "Onset", "question": "Did the chest discomfort start at rest or during effort?", "for_role": "doctor"}),
    ("chest_pain", {"tag": "ECG", "question": "Has a 12-lead ECG been recorded since arrival?", "for_role": "nurse"}),
    ("fever", {"tag": "Fever pattern", "question": "Is the fever continuous or does it come with chills at a fixed time?", "for_role": "health_worker"}),
    ("fever", {"tag": "Rash / bleeding", "question": "Any rash, gum bleeding or black stools since the fever began?", "for_role": "nurse"}),
    ("fever", {"tag": "Contacts", "question": "Is anyone else in the same hostel, household or workplace ill with fever?", "for_role": "health_worker"}),
    ("breathless", {"tag": "Speech", "question": "Can the patient speak full sentences without pausing for breath?", "for_role": "nurse"}),
    ("headache", {"tag": "Visual change", "question": "Any flashing lights, spots or blurred vision right now?", "for_role": "nurse"}),
    ("cough", {"tag": "Duration", "question": "Has the cough lasted more than 2 weeks? Any blood in sputum?", "for_role": "health_worker"}),
    ("abdominal_pain", {"tag": "Location", "question": "Where exactly is the pain — upper, lower, right or left side?", "for_role": "doctor"}),
    ("injury", {"tag": "Mechanism", "question": "How and when did the injury happen? Any loss of consciousness?", "for_role": "nurse"}),
    ("diarrhoea", {"tag": "Hydration", "question": "How many times has the patient passed urine in the last 6 hours?", "for_role": "health_worker"}),
    ("weakness_general", {"tag": "Weakness", "question": "Is the weakness all over, or in one arm, leg or side of the face?", "for_role": "nurse"}),
    ("snake_bite", {"tag": "Envenomation", "question": "Time of bite? Any bleeding gums, drooping eyelids or difficulty swallowing?", "for_role": "doctor"}),
]



def original_words(intake: dict) -> list[dict]:
    """A3: every answer given in another language, the patient's words beside the English, marked machine translated."""
    out = []
    for e in intake.get("symptoms", []):
        if e.get("original_text") and e["original_text"].strip() != e.get("text", "").strip():
            engines = (e.get("engine") or "").split(" + ")
            out.append({"original": e["original_text"], "translated": e["text"], "language": e["language"], "source": e.get("source"),
                        "speech_engine": engines[0] if e.get("source") == "voice" and engines[0] else None,
                        "translation_engine": engines[-1] if len(engines) > 1 or e.get("source") != "voice" else None})
    return out

def _for(duration: str | None) -> str:
    """" for 3–7 days", " since today", " (started in the last few hours)"."""
    if not duration:
        return ""
    d = duration.strip()
    if d.lower() == "today":
        return " since today"
    if d.lower().startswith("in the last"):
        return f" (started {d.lower()})"
    return f" for {d.lower() if d[0].isupper() and not d[:2].isupper() else d}"


def _present(triage: dict, fid: str) -> bool:
    return (triage.get("findings") or {}).get(fid, {}).get("value") is True


def _asks(triage: dict, key: str) -> bool:
    if key.startswith("urgency:"):
        return triage.get("urgency") == key.split(":", 1)[1]
    if key.startswith("rule:"):
        return any(h["rule_id"].startswith(key.split(":", 1)[1]) for h in triage.get("hits") or [])
    return _present(triage, key)


PER_ROLE = 3
ROLE_SEES = {"health_worker": {"health_worker"}, "nurse": {"health_worker", "nurse"}}  # doctor and medical officer see all


def questions_for(questions: list[dict], role: str) -> list[dict]:
    """The follow-up questions a viewer of this role is shown."""
    sees = ROLE_SEES.get(role)
    return [q for q in questions if sees is None or q.get("for_role") in sees]


def ppe_gap(occ: dict) -> str | None:
    """Why the worker's protection looks incomplete, or None. A workplace finding about the employer, not a symptom."""
    if not occ.get("exposures") or occ["exposures"] == ["heat"]:
        return None
    if occ.get("ppe_issued") is False:
        return "No protective equipment issued for this exposure"
    if occ.get("ppe_used") in ("sometimes", "never"):
        return f"Protective equipment issued but worn {occ['ppe_used']}"
    return None


def processing_status(stages: list[dict]) -> dict:
    """H5: `degraded` when any stage failed, fell back or is unsure; the stages say which and why."""
    return {"overall": "ok" if all(s["status"] == "ok" for s in stages) else "degraded", "stages": stages}


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


def heard_differently(s: dict) -> dict | None:
    """B9: the two speech engines' transcripts of one recording, compared again here (not taken from the browser)."""
    h = s.get("second_hearing")
    if s.get("source") != "voice" or not isinstance(h, dict) or not h.get("text"):
        return None
    first = (s.get("engine") or "First speech engine").split(" + ")[0]
    chk = asr_check.compare(s.get("original_text") or "", h["text"], s.get("language") or "en", first, h.get("engine") or "Second speech engine")
    if not chk["disagree"]:
        return None

    def said(words: str, english: str | None) -> str:
        return f'"{words}"' + (f' (English: "{english}")' if english and english != words else "")

    return {"field": "Voice transcript", "values": [{"engine": first, "value": said(s.get("original_text") or "", s.get("text"))},
                                                   {"engine": chk["engine"], "value": said(h["text"], h.get("translation"))}],
            "action": f"Two speech engines heard different words ({'; '.join(chk['differences'])}) — ask the patient which is right"}


def heard_unsure(s: dict) -> float | None:
    """The per-language threshold: a voice entry heard with less confidence is not taken into the history; the health
    worker asks the patient instead. Checked here against the server's threshold, not the browser's word. Returns
    the threshold it fell below, or None."""
    from .. import language

    c = s.get("confidence")
    if s.get("source") != "voice" or c is None:
        return None
    floor = language.min_confidence(s.get("language") or "en")
    return floor if c < floor else None


def build_note(*, intake: dict, patient, triage: dict, files: list, history: list, proxy: bool, calendar=None, on=None) -> dict:
    """`calendar` is the facility's regional calendar (F5) and `on` the visit date: a festival or season onset then
    shows the date or window it points to."""
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
    # What each upload is (B10) and what was hidden before storage (G3). Photos of the problem are never interpreted.
    documents, meds_pending = [], []
    confirmed = {m["name"] for m in intake.get("medications_confirmed") or []} | set(intake.get("medications_rejected") or [])
    for f in files:
        ex = f.extraction or {}
        documents.append({"file_id": f.id, "filename": f.filename, "kind": f.kind, "doc_type": ex.get("doc_type"), "redaction": ex.get("redaction"),
                          "read": bool(ex) and ex.get("engine") not in (None, "none")})
        for m in ex.get("medicines") or []:
            if m["name"] not in confirmed and all(x["name"] != m["name"] for x in meds_pending):
                meds_pending.append({**m, "file_id": f.id, "filename": f.filename})
    stages = []  # H5: what ran on this case, and what fell back or failed
    for f in files:
        if f.kind != "report":
            continue
        ex = f.extraction
        if not ex or ex.get("engine") in (None, "none"):
            why = next((w for w in reversed((ex or {}).get("warnings") or []) if "OCR" in w or "read" in w), "no reading was stored")
            stages.append({"stage": "Report reading", "status": "failed", "detail": f'"{f.filename}": {why}'})
        else:
            stages.append({"stage": "Report reading", "status": "ok", "detail": f'"{f.filename}": {ex["engine"]}'})
        if not ex:
            missing.append(f'Uploaded report "{f.filename}" was not read — review the image directly')
            continue
        strip = (ex.get("doc_type") or {}).get("type") == "medicine_strip"  # no report date or patient name on a strip
        doc_warns = list(ex.get("warnings", [])) + ([] if strip else document_checks(ex.get("meta") or {}, patient.name))
        for w in dict.fromkeys(doc_warns):
            flags.append({"code": "DOC-CHECK", "label": f'"{f.filename}": {w}', "severity": "warning", "reason": f"Document check on {ex['engine']}"})
        for c in (ex.get("consistency") or {}).get("failed", []):  # B2: the report's own numbers do not add up
            flags.append({"code": "LAB-SUM", "label": f'"{f.filename}": {c["text"]}', "severity": "warning",
                          "reason": "Arithmetic check on the values printed in the report — check each against the image crop"})
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
                    "engine": row.get("engine") or ex["engine"],
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
        sc = ex.get("second_check") or {}
        for d in sc.get("disagreements", []):  # B9: two OCR engines read the report differently
            disagreements.append({"field": f'{d["test"]}{" reference range" if d["what"] == "range" else ""} on "{f.filename}"',
                                  "values": [{"engine": ex["engine"], "value": d["first"]}, {"engine": sc["engine"], "value": d["second"]}],
                                  "action": "Two OCR engines read the report differently — check against the image crop"
                                            + (". Until then the rules use the reading further from normal" if d["what"] == "value" else "")})

    for h in hits:
        if h["urgency"] == "green":
            continue
        why = "; ".join(h.get("evidence") or []) or "matched on intake data"
        flags.append({"code": h["rule_id"], "label": h["description"], "severity": "critical" if h["urgency"] == "red" else "warning",
                      "reason": f"{why} — {h.get('source', h['protocol'])}", "non_downgradable": h.get("non_downgradable", False)})
    for f in triage.get("followups", []):  # never changes the colour
        why = "; ".join(f["evidence"]) or "matched on intake data"
        flags.append({"code": f["id"], "label": f"Follow-up: {f['description']}", "severity": "info", "reason": f"{why} — {f['source']}"})
    for s in intake.get("symptoms", []):
        if d := heard_differently(s):
            disagreements.append(d)
        if (floor := heard_unsure(s)) is not None:
            english = f' (machine English: "{s["text"]}")' if s.get("text") and s["text"] != s.get("original_text") else ""
            flags.append({"code": "ASR-LOW-CONF", "label": "Voice heard with low confidence — ask the patient", "severity": "warning",
                          "reason": f'Speech engine confidence {round(s["confidence"] * 100)} % is below the {round(floor * 100)} % set for '
                                    f'{(s.get("language") or "en").upper()}; not used in the history. The patient said: "{s.get("original_text")}"{english}. '
                                    "The rules still read it, so a possible danger sign is not lost."})
    for d in disagreements:
        flags.append({"code": "DISAGREE", "label": f"{d['field']}: sources disagree", "severity": "warning", "reason": d["action"]})
    if voice and not voice.get("confirmed_by_readback"):
        flags.append({"code": "ASR-UNCONFIRMED", "label": "Voice transcript not confirmed by read-back", "severity": "warning", "reason": "Patient skipped the spoken confirmation step"})
    machine = [x for x in intake.get("symptoms", []) if x.get("original_text") and x.get("text") != x.get("original_text")]
    if machine:
        langs = ", ".join(sorted({x.get("language", "") for x in machine}))
        problems, rewrites = [], []
        for x in machine:
            notes = list(x.get("mt_unsure") or [])
            if chk := translation_check(x):
                notes += [f"translation leaves out {FINDINGS[f][0].lower()}" for f in chk["missed"]]
                notes += [f"translation says {FINDINGS[f][0].lower()}, the patient's words do not" for f in chk["added"]]
            if notes:
                problems.append(f'"{x["original_text"]}" → "{x["text"]}": {"; ".join(notes)}')
            rewrites += [f'{r["from"]} → {r["to"]}' for r in x.get("mt_rewrites") or []]
        base = f"English rendered by {machine[0].get('engine') or 'machine translation'} from {langs}; rules also read the original-language text"
        if rewrites:
            base += f"; given to the translator in standard form: {', '.join(dict.fromkeys(rewrites))}"
        stages.append({"stage": "Translation", "status": "unsure" if problems else "ok", "detail": machine[0].get("engine") or "machine translation"})
        if problems:
            flags.append({"code": "MT-CHECK", "label": "Translation may be wrong — check with the patient", "severity": "warning", "reason": " | ".join(problems) + f" — {base}"})
        else:
            flags.append({"code": "MT-CHECK", "label": "Machine-translated history — check against the patient's own words", "severity": "info", "reason": base})
    if voice:
        stages.append({"stage": "Speech recognition", "status": "ok" if voice.get("confirmed_by_readback") else "unconfirmed", "detail": voice.get("engine") or "Browser speech recognition"})
    if bad := [s for s in stages if s["status"] == "failed"]:
        flags.append({"code": "STAGE-DEGRADED", "label": "Part of the automatic processing failed — check the source directly", "severity": "warning",
                      "reason": " | ".join(f'{s["stage"]}: {s["detail"]}' for s in bad)})
    if meds_pending:
        flags.append({"code": "MEDS-UNCONFIRMED", "label": f"{len(meds_pending)} medicine name(s) read from a strip or prescription — awaiting confirmation", "severity": "warning",
                      "reason": "Read by OCR and matched to the PMBJP generic list; not part of the record until a nurse or doctor confirms each one"})
    if intake.get("ai_assist") is False:
        flags.append({"code": "NO-AI", "label": "Patient chose to continue without AI", "severity": "info",
                      "reason": "No speech recognition, translation or report reading ran; the note is the fixed template and urgency comes from the rules alone"})
    if intake.get("redactions"):
        from ..privacy import describe

        flags.append({"code": "PII-REDACTED", "label": "Identifiers removed from the patient's free text", "severity": "info",
                      "reason": f"{describe(intake['redactions'])} replaced with placeholders before storage; identity is on the registration record"})
    if proxy:
        flags.append({"code": "PROXY", "label": "History given by a proxy", "severity": "info", "reason": "Consent and history captured from a family member or caregiver"})
    occ = intake.get("occupational") or {}
    if gap := ppe_gap(occ):
        flags.append({"code": "PPE-GAP", "label": "Workplace finding: protective equipment gap", "severity": "warning",
                      "reason": f"{gap} (worker's answer). Not a symptom and not part of urgency; counted in the employer's department rates without names"})
    if occ.get("exposures"):
        if occ.get("years_exposed") is None:
            missing.append("Years of workplace exposure not recorded")
        if occ.get("breathless_vs_last") in (None, "unsure"):
            missing.append("Breathing compared with the last screening not recorded")
        if any(x in occ["exposures"] for x in ("silica", "coal_dust", "cotton_dust", "asbestos", "other_dust")) and not occ.get("fev1_l"):
            missing.append("Spirometry (FEV1) not recorded for a dust-exposed worker")
    if intake.get("captured_offline"):
        flags.append({"code": "OFFLINE", "label": "Captured offline, synced later", "severity": "info", "reason": "Wait time is counted from the original capture time"})

    cat = intake.get("category")
    for m in triage.get("missing_for_green", []):
        missing.append(f"{m[0].upper()}{m[1:]} not recorded — needed before the case can be routine")
    asks = sorted({n for u in triage.get("unresolved", []) if u["urgency"] == "red" for n in u["needs"] if not n.startswith("danger-sign")})
    for n in asks:
        if not any(n.lower() in x.lower() for x in missing):
            missing.append(f"Ask / measure: {n} (a RED rule depends on it)")
    began = onset(intake, calendar, on)
    if began["certainty"] == "UNKNOWN":
        missing.append("Duration of complaint not stated")
    elif began["check"]:
        missing.append(began["check"])
    if cat == "maternal" and not (intake.get("maternal") or {}).get("gestation_weeks"):
        missing.append("Gestational age not recorded")
    if cat == "chronic" and not (intake.get("chronic") or {}).get("current_medicines"):
        missing.append("Current medicines and adherence not recorded")
    if cat == "chronic" and not any(f.kind == "report" for f in files):
        missing.append("No recent lab report for chronic follow-up")

    followup, per_role = [], {}
    for key, q in FOLLOWUPS:
        if _asks(triage, key) and per_role.get(q["for_role"], 0) < PER_ROLE and q not in followup:
            followup.append(q)
            per_role[q["for_role"]] = per_role.get(q["for_role"], 0) + 1
    if not per_role.get("health_worker"):
        followup.append({"tag": "Context", "question": "Anything else that changed recently — food, work, travel or medicines?", "for_role": "health_worker"})

    timeline = []
    # Each entry says how sure it is (B4): RECORDED (a dated record here), STATED, INFERRED, VAGUE or UNKNOWN.
    for e in [e for e in history if e.intake][:3]:
        timeline.append({"when": e.created_at.strftime("%d/%m/%Y"), "event": f"Previous visit: {e.chief_complaint}", "certainty": "RECORDED", "raw": None})
    if (intake.get("chronic") or {}).get("last_checkup"):
        timeline.append({"when": intake["chronic"]["last_checkup"], "event": f"Last {intake['chronic']['condition']} check-up", "certainty": "STATED", "raw": "as told by the patient"})
    # One onset per thing the patient said, each from that sentence's own words: "fever and cough for two days" and
    # "headache for a long time" are two onsets, and the time from one must not be shown against the other.
    onsets = []
    for s in intake.get("symptoms") or []:
        if heard_unsure(s) is not None:
            continue
        o = onset({"symptoms": [s]}, calendar, on)
        if o["certainty"] != "UNKNOWN":
            onsets.append((o, s.get("text") or s.get("original_text")))
    if not onsets or str(began["raw"] or "").startswith("tapped"):
        onsets.insert(0, (began, intake["chief_complaint"]))
    onsets.sort(key=lambda r: (r[0]["days"] is not None, -(r[0]["days"] or 0)))  # unclear first, then earliest
    for o, what in onsets:
        row = {"when": o["when"], "event": f"Onset: {what}", "certainty": o["certainty"], "raw": o["raw"]}
        if (a := o.get("approx")) and a.get("found"):
            row["basis"] = f"{a['label']} {regions.fmt_range(date.fromisoformat(a['start']), date.fromisoformat(a['end']))} · " + (
                f"{a['region']} calendar" if a.get("region") else "national calendar")
        timeline.append(row)
    src = intake["symptoms"][0]["source"] if intake.get("symptoms") else "text"
    spoken = list(dict.fromkeys(s.get("language") or "en" for s in intake.get("symptoms") or [])) or [intake.get("language", "en")]
    timeline.append({"when": "Today", "event": f"Intake at kiosk ({', '.join(x.upper() for x in spoken)}, {src})", "certainty": "RECORDED", "raw": None})

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
        f"Chief complaint: {intake['chief_complaint']}{_for(intake.get('duration'))}.",
        *([f"Onset vague: \"{began['raw']}\"."] if began["certainty"] == "VAGUE" else []),
    ]
    if also := [x for x in intake.get("selected_symptoms") or [] if x.lower() not in intake["chief_complaint"].lower()]:
        parts.append(f"Also reports: {', '.join(also)}.")
    if intake.get("severity") is not None:
        parts.append(f"Self-rated severity {intake['severity']}/10.")
    if (intake.get("maternal") or {}).get("gestation_weeks"):
        parts.append(f"Pregnant, {intake['maternal']['gestation_weeks']} weeks by history.")
    if intake.get("chronic"):
        parts.append(f"Known {intake['chronic']['condition']}; patient feels {intake['chronic'].get('feeling_vs_last', 'unsure')} compared with last visit.")
    if occ.get("exposures"):
        from .rules import EXPOSURE_LABEL

        yrs = f" for {occ['years_exposed']:g} years" if occ.get("years_exposed") is not None else ""
        parts.append(f"Works with {', '.join(EXPOSURE_LABEL.get(x, x) for x in occ['exposures'])}{yrs}.")
        if occ.get("breathless_vs_last") in ("better", "same", "worse"):
            parts.append(f"Breathing {occ['breathless_vs_last']} than at the last screening, by the worker's account.")
        if occ.get("fev1_l"):
            base = f" (earliest recorded {occ['fev1_baseline_l']:g} L)" if occ.get("fev1_baseline_l") else ""
            parts.append(f"FEV1 {occ['fev1_l']:g} L{', FVC ' + format(occ['fvc_l'], 'g') + ' L' if occ.get('fvc_l') else ''}{base}.")
    hx = clinical_history(intake, triage)
    if hx["positives"]:
        parts.append("On questioning: " + "; ".join(hx["positives"]) + ".")
    if hx["negatives"]:
        parts.append("Denies: " + "; ".join(hx["negatives"]) + ".")
    parts.append(f"Allergies: {hx['allergies']}.")
    if hx["medicines"]:
        parts.append("Regular medicines: " + "; ".join(hx["medicines"]) + ".")
    if hx["past"]:
        parts.append("Past history: " + "; ".join(hx["past"]) + ".")
    off = [x for x in vitals if x["status"] == "abnormal"]
    if off:
        parts.append("Abnormal vitals: " + ", ".join(f"{x['label']} {x['value']}{' ' + x['unit'] if x['unit'] else ''}" for x in off) + ".")
    if hx["allergies"] == "not asked":
        missing.append("Medicine allergies not recorded — ask before prescribing")
    abn = [x for x in labs if x["status"] == "abnormal"]
    if abn:
        parts.append("Uploaded report shows " + ", ".join(f"{x['label']} {x['value']}{' ' + x['unit'] if x['unit'] else ''}" for x in abn) + " outside reference range.")
    parts.append("Summary organises patient-provided information only; it is not a diagnosis.")

    rule_codes = {h["rule_id"] for h in hits} | {f["id"] for f in triage.get("followups", [])} | {"PPE-GAP"}
    for f in flags:  # the reviewer reads clinical warnings first; notices about how the data was captured come after
        f["group"] = "clinical" if f["code"] in rule_codes else "data"

    return {
        "summary": " ".join(parts),
        "history": hx,
        "flags": flags,
        "rules_fired": hits,
        "triage": {
            "urgency": triage["urgency"],  # the rules' tier as computed; an override changes the encounter, not this
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
        "documents": documents,
        "medications_pending": meds_pending,
        "medications": list(intake.get("medications_confirmed") or []),
        "transcript": {"original": voice["original_text"], "translated": voice["text"], "language": voice["language"]} if voice else None,
        "original_words": original_words(intake),
        "generated_by": f"rules engine (rulepack {triage['rulepack_version']}) + template summariser",
        "renderer": "TEMPLATE",
        "processing_status": processing_status(stages),
        "ai_assist": intake.get("ai_assist", True),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# Findings that are history, not complaint: shown under Allergies / Past history, not as "on questioning".
PAST = ("diabetes_known", "hypertension_known", "heart_disease_known", "tb_history", "asthma", "anticoagulated", "chemo_recent", "immunisation_incomplete", "adherence_poor")


def clinical_history(intake: dict, triage: dict) -> dict:
    """What a doctor reads before the complaint details: positives and pertinent negatives from the kiosk's closed
    questions, allergies, regular medicines and past history. Only answers the patient gave; nothing inferred."""
    fnd = triage.get("findings") or {}
    asked = lambda f: any(e.startswith("answer to") for e in (fnd.get(f) or {}).get("evidence") or [])  # noqa: E731
    pos = [fnd[k]["label"].lower() if not fnd[k]["label"][:2].isupper() else fnd[k]["label"] for k in fnd if fnd[k]["value"] is True and asked(k) and k not in PAST and k != "allergy_drug"]
    neg = [fnd[k]["label"].lower() if not fnd[k]["label"][:2].isupper() else fnd[k]["label"] for k in fnd if fnd[k]["value"] is False and asked(k) and k not in PAST and k != "allergy_drug"]
    a = (fnd.get("allergy_drug") or {}).get("value")
    allergies = "reports a medicine allergy — confirm which medicine" if a is True else "no known medicine allergy" if a is False else "not asked"
    meds = [f"{m['name']}{' ' + m['strength'] if m.get('strength') else ''} (confirmed)" for m in intake.get("medications_confirmed") or []]
    if (c := (intake.get("chronic") or {})).get("current_medicines"):
        meds.append(f"{c['current_medicines']} (as told)")
    ans = {x.get("qid"): x.get("answer") or "" for x in intake.get("answers") or []}
    if ans.get("regular_meds", "").startswith("Yes — other"):
        meds.append("takes other medicines daily — names not given")
    past = [fnd[k]["label"] for k in PAST if (fnd.get(k) or {}).get("value") is True]
    if c.get("condition"):
        past.insert(0, f"Known {c['condition']}")
    if ans.get("long_illness") == "Other":
        past.append("Another long-term illness — ask which")
    return {"positives": pos, "negatives": neg, "allergies": allergies, "medicines": meds, "past": list(dict.fromkeys(past))}


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
