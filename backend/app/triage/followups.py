"""Follow-up questions the note asks staff to put to the patient, and what their answers mean to the rules.

The nurse (or doctor) records the answer in the note. An answer that maps to a finding below is fed back to the
rules engine exactly like a kiosk answer, so a "yes" to a danger question can raise urgency; every other answer is kept
in the history as the patient's words, read by people only. Nothing here is inferred by a model.
"""

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

YES_NO = ["Yes", "No", "Not sure"]
# Questions whose answer is a choice other than yes / no.
OPTIONS = {
    "chest_pain:onset": ["At rest", "During effort", "Not sure"],
    "weakness_general:weakness": ["All over", "One arm, leg or side of the face", "Not sure"],
    "fever:fever_pattern": ["Continuous", "With chills at a fixed time", "Not sure"],
}
# Answer -> findings, only where the answer settles the finding without doubt. "Not sure" never sets anything.
ANSWER_FINDINGS: dict[str, dict[str, dict[str, bool]]] = {
    "breathless:speech": {"Yes": {"incomplete_sentences": False}, "No": {"incomplete_sentences": True}},
    "headache:visual_change": {"Yes": {"visual_disturbance": True}, "No": {"visual_disturbance": False}},
    "weakness_general:weakness": {"One arm, leg or side of the face": {"one_sided_weakness": True}, "All over": {"one_sided_weakness": False}},
    "fever:fever_pattern": {"With chills at a fixed time": {"chills": True}},
}


def question_id(key: str, q: dict) -> str:
    return f"{key}:{q['tag']}".lower().replace(" / ", "_").replace(" ", "_")


def options_for(qid: str) -> list[str]:
    return OPTIONS.get(qid, YES_NO)


BY_ID = {question_id(k, q): q for k, q in FOLLOWUPS}
CONTEXT_ID = "context"


def answered_ids(intake: dict) -> set[str]:
    return {a["qid"] for a in intake.get("staff_answers") or []}


def answer_findings(intake: dict) -> list[tuple[str, bool, str]]:
    """(finding, value, evidence) from the answers staff recorded. Evidence starts "answer to" so the history lists it."""
    out = []
    for a in intake.get("staff_answers") or []:
        for fid, val in ANSWER_FINDINGS.get(a["qid"], {}).get(a["answer"], {}).items():
            out.append((fid, val, f'answer to "{a["question"]}" (asked by {a["by"]}): {a["answer"]}'))
    return out
