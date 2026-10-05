"""Rules-engine tests. Each case is derived from a criterion in the cited protocol (ATP Red list,
WHO IITT age ≥12 / <12 charts, WHO IMCI 2014, ISSHP / WHO PCPNC) — not from clinician-labelled
vignettes, which this project does not have."""

import pytest

from app.triage.findings import extract, scan_text
from app.triage.rules import evaluate, evaluate_full, load_pack, load_rules, onset_hours

NORMAL_ADULT = {"pulse": 80, "resp_rate": 16, "spo2": 98, "bp_systolic": 120, "bp_diastolic": 80, "temp_f": 98.6, "avpu": "A"}
NORMAL_CHILD = {"pulse": 100, "resp_rate": 22, "spo2": 98, "temp_f": 98.6, "avpu": "A"}
EXAM = {"done": True, "signs": [], "by": "Nurse"}


def intake(**kw):
    base = {"chief_complaint": "", "symptoms": [], "selected_symptoms": [], "answers": [], "category": "normal", "vitals": {}, "severity": None, "duration": None}
    base.update(kw)
    return base


def complete(vitals=None, **kw):
    """An intake with every vital measured and the danger-sign check recorded."""
    return intake(vitals={**NORMAL_ADULT, **(vitals or {})}, exam=kw.pop("exam", EXAM), duration=kw.pop("duration", "3-7 days"), **kw)


def ids(result):
    return {h["rule_id"] for h in result["hits"]}


# ---------------------------------------------------------------- rulepack integrity

def test_rulepack_loads_with_sources_and_unique_ids():
    sources, protocols, version = load_pack()
    rules = load_rules()
    assert len(rules) >= 140
    assert len({r.id for r in rules}) == len(rules)
    assert all(r.source in sources for r in rules)
    assert {p.key for p in protocols} >= {"ATP", "IITT", "IMCI", "MATERNAL", "LOCAL"}
    assert len(version) == 10


def test_every_red_rule_is_non_downgradable():
    assert all(r.non_downgradable for r in load_rules() if r.urgency == "red")


def test_determinism():
    i = complete(chief_complaint="chest pain since this morning", duration="today")
    assert evaluate(i, 50, "M") == evaluate(i, 50, "M")


# ---------------------------------------------------------------- unknown is never normal

def test_no_vitals_is_never_green():
    r = evaluate_full(intake(chief_complaint="mild cold"), 30, "M")
    assert r["urgency"] == "yellow" and r["provisional"]
    assert "SAFE-PROVISIONAL" in ids(r)
    assert "SpO₂" in r["missing_for_green"] and "clinician danger-sign check" in r["missing_for_green"]


def test_complete_and_normal_is_green():
    r = evaluate_full(complete(chief_complaint="mild cold and runny nose"), 30, "M")
    assert r["urgency"] == "green" and not r["provisional"]
    assert ids(r) == {"TRIAGE-GREEN"}


def test_missing_danger_sign_check_holds_case_provisional():
    i = intake(chief_complaint="mild cold", vitals=NORMAL_ADULT, duration="1-2 days")
    r = evaluate_full(i, 30, "M")
    assert r["urgency"] == "yellow" and r["provisional"]
    assert r["missing_for_green"] == ["clinician danger-sign check"]


def test_pulse_over_120_with_unknown_temperature_is_unresolved_not_green():
    r = evaluate_full(intake(chief_complaint="palpitations", vitals={"pulse": 125}), 35, "F")
    assert r["urgency"] == "yellow" and r["provisional"]
    assert "ATP-C-PULSE" in {u["rule_id"] for u in r["unresolved"]}


def test_glucose_is_not_required_for_green():
    r = evaluate_full(complete(chief_complaint="mild cold"), 30, "M")
    assert "IITT-A-HYPOGLYCAEMIA" not in {u["rule_id"] for u in r["unresolved"]}


# ---------------------------------------------------------------- ATP Red criteria (age 14+)

@pytest.mark.parametrize("vitals,rule", [
    ({"resp_rate": 23}, "ATP-B-RR"),
    ({"resp_rate": 9}, "ATP-B-RR"),
    ({"spo2": 89}, "ATP-B-SPO2"),
    ({"pulse": 48}, "ATP-C-PULSE"),
    ({"bp_systolic": 221}, "ATP-C-BP-HIGH"),
    ({"bp_diastolic": 111}, "ATP-C-BP-HIGH"),
    ({"bp_systolic": 88}, "ATP-C-BP-LOW"),
    ({"bp_diastolic": 58}, "ATP-C-BP-LOW"),
    ({"pulse": 110, "bp_systolic": 100}, "ATP-C-SHOCK-INDEX"),
    ({"temp_f": 102.6}, "ATP-T-FEVER"),
    ({"avpu": "P"}, "ATP-D-SENSORIUM"),
])
def test_atp_physiological_red(vitals, rule):
    r = evaluate_full(complete(vitals, chief_complaint="feeling unwell"), 40, "M")
    assert r["urgency"] == "red" and rule in ids(r)


def test_atp_thresholds_are_strict():
    # Exactly at the limit is not beyond it: RR 22, SBP 220, pulse 50, SpO2 90.
    r = evaluate_full(complete({"resp_rate": 22, "bp_systolic": 220, "bp_diastolic": 100, "pulse": 50, "spo2": 90}, chief_complaint="check-up"), 40, "M")
    assert not ids(r) & {"ATP-B-RR", "ATP-C-BP-HIGH", "ATP-C-PULSE", "ATP-B-SPO2"}


def test_pulse_over_120_with_fever_is_not_the_atp_pulse_rule():
    r = evaluate_full(complete({"pulse": 125, "temp_f": 101.5}, chief_complaint="fever"), 30, "F")
    assert "ATP-C-PULSE" not in ids(r)


def test_chest_pain_within_24h_is_red_but_older_is_not_the_time_rule():
    assert "ATP-T-CHEST-PAIN" in ids(evaluate_full(complete(chief_complaint="chest pain", duration="today"), 40, "M"))
    assert "ATP-T-CHEST-PAIN" not in ids(evaluate_full(complete(chief_complaint="chest pain", duration="1-4 weeks", severity=3), 40, "M"))


def test_chest_pain_with_unknown_onset_cannot_be_green():
    r = evaluate_full(complete(chief_complaint="chest pain", duration=None, severity=3), 40, "M")
    assert r["urgency"] != "green"
    assert "ATP-T-CHEST-PAIN" in {u["rule_id"] for u in r["unresolved"]}


@pytest.mark.parametrize("text,rule", [
    ("snake bit my leg in the field", "IITT-A-SNAKE-BITE"),
    ("fell from a tree while plucking coconuts", "ATP-T-MECHANISM"),
    ("got electric shock at work", "ATP-T-MECHANISM"),
    ("vomiting blood since morning", "ATP-C-BLEEDING"),
    ("fainted at the bus stop", "ATP-T-SYNCOPE"),
    ("cannot pass urine since last night", "ATP-T-URINE"),
    ("sudden worst headache of my life", "ATP-T-HEADACHE-SUDDEN"),
    ("drank pesticide", "IITT-A-POISONING"),
    ("lips and tongue swollen after injection", "ATP-A-ANGIOEDEMA"),
])
def test_red_presentations_from_free_text(text, rule):
    r = evaluate_full(complete(chief_complaint=text, severity=3), 35, "M")
    assert r["urgency"] == "red" and rule in ids(r), ids(r)


def test_severe_pain_is_red_under_atp():
    r = evaluate_full(complete(chief_complaint="back pain", severity=8), 35, "F")
    assert "ATP-T-SEVERE-PAIN" in ids(r)


def test_scrotal_pain_rule_needs_male_sex():
    assert "ATP-T-SCROTAL" in ids(evaluate_full(complete(chief_complaint="testicular pain", severity=4), 20, "M"))
    assert "ATP-T-SCROTAL" not in ids(evaluate_full(complete(chief_complaint="groin pain", severity=4), 20, "F"))


# ---------------------------------------------------------------- IITT (ages 12+ and <12)

def test_ages_12_and_13_are_covered_by_iitt_not_atp():
    r = evaluate_full(complete({"pulse": 155}, chief_complaint="palpitations"), 13, "F")
    assert "ATP" not in {p["key"] for p in r["protocols"]} and "IITT" in {p["key"] for p in r["protocols"]}
    assert "IITT-A-HR" in ids(r)


def test_iitt_high_risk_vitals_are_yellow_with_doctor_review():
    r = evaluate_full(complete({"spo2": 91, "resp_rate": 20}, chief_complaint="cough"), 30, "M")
    hit = next(h for h in r["hits"] if h["rule_id"] == "IITT-A-V-SPO2")
    assert hit["urgency"] == "yellow" and hit["review_by"] == "doctor"


def test_iitt_meningism_two_of_four():
    r = evaluate_full(complete({"temp_f": 101}, chief_complaint="headache and stiff neck", severity=4, duration="1-2 days"), 25, "M")
    assert "IITT-A-MENINGISM" in ids(r) and r["urgency"] == "red"


def test_school_age_child_uses_iitt_paediatric_bands():
    # 8-year-old, RR 34: high-risk for the 5–12 band (≥30) → yellow; no IMCI (over 5), no ATP.
    r = evaluate_full(complete({**NORMAL_CHILD, "resp_rate": 34}, chief_complaint="cough"), 8, "M")
    assert not {p["key"] for p in r["protocols"]} & {"ATP", "IMCI"}
    assert "IITT-P-V-RR-5-12" in ids(r) and r["urgency"] == "yellow"


def test_child_does_not_need_blood_pressure_for_green():
    r = evaluate_full(intake(chief_complaint="mild cold", vitals=NORMAL_CHILD, exam=EXAM, duration="1-2 days"), 8, "F")
    assert r["urgency"] == "green"


def test_paediatric_trauma_and_newborn():
    assert "IITT-P-HIGH-RISK-TRAUMA" in ids(evaluate_full(complete(NORMAL_CHILD, chief_complaint="fell from the roof"), 9, "M"))
    assert "IITT-P-NEWBORN" in ids(evaluate_full(complete(NORMAL_CHILD, chief_complaint="not feeding well", age_days=5), 0, "F"))


def test_infant_with_unknown_exact_age_is_unresolved():
    r = evaluate_full(complete(NORMAL_CHILD, chief_complaint="mild cold"), 0, "F")
    assert "IITT-P-NEWBORN" in {u["rule_id"] for u in r["unresolved"]}
    assert r["urgency"] != "green"


# ---------------------------------------------------------------- IMCI (under 5)

def test_imci_danger_sign_only_under_five():
    r = evaluate_full(intake(chief_complaint="fever and fits"), 3, "M")
    assert r["urgency"] == "red" and "IMCI-DANGER-SIGN" in ids(r)
    adult = evaluate_full(intake(chief_complaint="fever"), 30, "M")
    assert not any(h["protocol"] == "IMCI" for h in adult["hits"])


def test_imci_fast_breathing_by_age():
    assert "IMCI-FAST-BREATHING-CHILD" in ids(evaluate_full(complete({**NORMAL_CHILD, "resp_rate": 42}, chief_complaint="cough"), 3, "F"))
    assert "IMCI-FAST-BREATHING-INFANT" in ids(evaluate_full(complete({**NORMAL_CHILD, "resp_rate": 52}, chief_complaint="cough", age_months=6), 0, "F"))
    assert "IMCI-FAST-BREATHING-INFANT" not in ids(evaluate_full(complete({**NORMAL_CHILD, "resp_rate": 45}, chief_complaint="cough", age_months=6), 0, "F"))


def test_kiosk_answer_unable_to_drink_is_danger_sign():
    i = intake(chief_complaint="fever", answers=[{"qid": "child_danger", "question": "Is the child able to drink?", "answer": "No — unable to drink"}])
    assert "IMCI-DANGER-SIGN" in ids(evaluate_full(i, 2, "M"))


# ---------------------------------------------------------------- pregnancy

def test_preeclampsia_features_red_only_in_pregnancy():
    v = {"bp_systolic": 148, "bp_diastolic": 96}
    preg = evaluate_full(complete(v, category="maternal", chief_complaint="headache", severity=4), 26, "F")
    assert preg["urgency"] == "red" and "MAT-PE-FEATURES" in ids(preg)
    other = evaluate_full(complete(v, chief_complaint="headache", severity=4), 26, "F")
    assert "MAT-PE-FEATURES" not in ids(other)


def test_severe_hypertension_in_pregnancy():
    r = evaluate_full(complete({"bp_systolic": 162, "bp_diastolic": 100}, category="maternal", chief_complaint="routine ANC check"), 24, "F")
    assert "MAT-BP-SEVERE" in ids(r) and r["urgency"] == "red"


def test_pregnancy_reported_in_text_routes_maternal_rules():
    r = evaluate_full(complete({"bp_systolic": 142, "bp_diastolic": 92}, chief_complaint="I am pregnant, feet swelling"), 27, "F")
    assert "MATERNAL" in {p["key"] for p in r["protocols"]} and "MAT-HYPERTENSION" in ids(r)


def test_bleeding_in_pregnancy_visit_is_vaginal_bleeding():
    r = evaluate_full(intake(category="maternal", chief_complaint="bleeding since morning"), 22, "F")
    assert "MAT-VAGINAL-BLEEDING" in ids(r)


# ---------------------------------------------------------------- language, negation, evidence

def test_negation_english_and_hindi():
    assert scan_text("no chest pain, just cough", "t")["chest_pain"].value is False
    assert scan_text("सीने में दर्द नहीं है", "t")["chest_pain"].value is False
    assert scan_text("seene me dard nahi hai", "t")["chest_pain"].value is False


def test_negation_does_not_cross_and():
    assert scan_text("i can not breathe properly and chest pain", "t")["chest_pain"].value is True


def test_hindi_and_odia_terms():
    assert scan_text("सीने में दर्द हो रहा है", "t")["chest_pain"].value is True
    assert scan_text("ଜ୍ୱର ଅଛି", "t")["fever"].value is True
    assert scan_text("ସାପ କାମୁଡ଼ି ଦେଲା", "t")["snake_bite"].value is True


def test_occupational_fit_is_not_a_seizure():
    assert "seizure" not in scan_text("worker is fit for duty", "t")


def test_affirmed_mention_beats_denial():
    f = extract(intake(chief_complaint="no fever yesterday", selected_symptoms=["Fever"]))
    assert f["fever"].value is True


def test_hits_carry_evidence_and_source():
    r = evaluate_full(complete({"spo2": 87}, chief_complaint="breathless"), 60, "M")
    hit = next(h for h in r["hits"] if h["rule_id"] == "ATP-B-SPO2")
    assert hit["evidence"] == ["SpO₂ 87 %"] and "AIIMS" in hit["source"] and hit["non_downgradable"]


def test_clinician_signs_raise_urgency():
    r = evaluate_full(complete(chief_complaint="cough", exam={"done": True, "signs": ["stridor"], "by": "Nurse"}), 30, "M")
    assert "ATP-A-STRIDOR" in ids(r) and r["urgency"] == "red"


def test_onset_parsing():
    assert onset_hours({"duration": "today"}) == (0, 24)
    assert onset_hours({"duration": "6 hours"}) == (6, 6)
    assert onset_hours({"answers": [{"qid": "dur", "answer": "3–7 days"}]}) == (72, 168)
    assert onset_hours({"duration": None}) is None


def test_kiosk_follow_up_answers_resolve_red_criteria():
    i = complete(chief_complaint="breathless", duration="today",
                 answers=[{"qid": "dur", "question": "Since when?", "answer": "In the last few hours"}])
    assert "ATP-T-BREATHLESS" in ids(evaluate_full(i, 40, "F"))
    j = complete(chief_complaint="injured", severity=3, answers=[{"qid": "mechanism", "question": "How?", "answer": "Fall from a height (tree, roof, ladder)"}])
    assert "ATP-T-MECHANISM" in ids(evaluate_full(j, 40, "M"))
    k = complete(chief_complaint="headache", severity=3, answers=[{"qid": "sudden_head", "question": "Sudden?", "answer": "Sudden — within minutes"}])
    r = evaluate_full(k, 40, "M")
    assert "ATP-T-HEADACHE-SUDDEN" in ids(r) and "ATP-T-ABDO-SUDDEN" not in ids(r)
    m = complete(chief_complaint="dizzy", answers=[{"qid": "conscious", "question": "Awake?", "answer": "Not responding"}])
    assert "IITT-A-UNRESPONSIVE" in ids(evaluate_full(m, 40, "M"))


def test_report_values_feed_rules():
    r = evaluate_full(complete(chief_complaint="weakness", lab_values={"potassium": 5.9}), 60, "M")
    assert "ATP-T-OUTSIDE-EVAL" in ids(r) and "Report: potassium 5.9" in next(h for h in r["hits"] if h["rule_id"] == "ATP-T-OUTSIDE-EVAL")["evidence"]
    preg = complete({"bp_systolic": 144, "bp_diastolic": 92}, category="maternal", chief_complaint="ANC visit", lab_values={"urine_albumin": 2})
    assert "LAB-PE-PROTEINURIA" in ids(evaluate_full(preg, 25, "F"))
    assert "LAB-SEVERE-ANAEMIA" in ids(evaluate_full(complete(chief_complaint="tired", lab_values={"haemoglobin": 7.4}), 30, "F"))


@pytest.mark.parametrize(
    "text, crush",
    [
        ("Breathless when walking, works in a stone-crushing unit", False),  # occupation (seen 5 Oct in the LLM evaluation)
        ("Operates the stone crusher, cough for a month", False),
        ("Hand got crushed in the machine", True),
        ("Crush injury to the left foot", True),
        ("Trapped under a fallen wall for an hour", True),
    ],
)
def test_crush_injury_needs_injury_wording(text, crush):
    from app.triage.findings import scan_text

    assert (scan_text(text, "t").get("crush_injury") is not None and scan_text(text, "t")["crush_injury"].value) is crush
