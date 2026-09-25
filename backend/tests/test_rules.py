from app.triage.rules import evaluate, load_rules


def intake(**kw):
    base = {"chief_complaint": "", "symptoms": [], "selected_symptoms": [], "answers": [], "category": "normal", "vitals": {}, "severity": None, "duration": None}
    base.update(kw)
    return base


def test_rules_load_and_are_unique():
    rules = load_rules()
    assert len(rules) >= 25
    assert len({r.id for r in rules}) == len(rules)


def test_chest_pain_with_radiation_is_red():
    u, hits = evaluate(intake(chief_complaint="Chest pain going to left arm"), 45)
    assert u == "red"
    assert "ATP-CARD-01" in {h["rule_id"] for h in hits}


def test_low_spo2_is_red_and_borderline_yellow():
    assert evaluate(intake(vitals={"spo2": 88}), 60)[0] == "red"
    assert evaluate(intake(vitals={"spo2": 92}), 60)[0] == "yellow"


def test_imci_danger_sign_only_under_five():
    u, hits = evaluate(intake(chief_complaint="fever and fits"), 3)
    assert u == "red" and "IMCI-DANGER-01" in {h["rule_id"] for h in hits}
    _, adult_hits = evaluate(intake(chief_complaint="fever"), 30)
    assert "IMCI-FEVER-01" not in {h["rule_id"] for h in adult_hits}


def test_preeclampsia_red_flag_requires_maternal_category():
    v = {"bp_systolic": 148, "bp_diastolic": 96}
    assert evaluate(intake(category="maternal", chief_complaint="headache", vitals=v), 26)[0] == "red"
    assert evaluate(intake(category="normal", chief_complaint="headache", vitals=v), 26)[0] == "green"


def test_routine_default_and_determinism():
    a = evaluate(intake(chief_complaint="mild cold"), 30)
    b = evaluate(intake(chief_complaint="mild cold"), 30)
    assert a == b
    assert a[0] == "green" and a[1][0]["rule_id"] == "ATP-ROUT-00"


def test_answers_feed_rules():
    u, _ = evaluate(intake(chief_complaint="chest pain", answers=[{"answer": "Yes — spreads to arm / jaw"}]), 50)
    assert u == "red"
