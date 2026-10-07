"""The 300-patient set (I1, §9): the same complaint must get the same colour in English, Hindi and Odia, for a man and a
woman. Ages differ only by the protocol's own age gates (child protocols below 5 and 12). Built by
scripts/make_patients300.py; measured by scripts/eval_patients300.py."""

from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from app.triage.rules import evaluate_full

DATA = yaml.safe_load((Path(__file__).parent / "data/patients300.yaml").read_text(encoding="utf-8"))
SEX = {"M": "male", "F": "female"}


def colour(p: dict) -> str:
    return evaluate_full({"symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [], **p["intake"]}, p["age"], SEX[p["sex"]])["urgency"]


def group(p: dict) -> str:
    return "under 5" if p["age"] < 5 else "5-11" if p["age"] < 12 else "12+"


def test_set_has_300_patients_in_three_languages_and_both_sexes():
    ps = DATA["patients"]
    assert len(ps) == 300
    assert {p["language"] for p in ps} == {"en", "hi", "or"} and {p["sex"] for p in ps} == {"M", "F"}
    assert sum("earlier_visits" in p for p in ps) == 30


def test_one_colour_per_vignette_whatever_the_language_or_sex():
    seen = defaultdict(set)
    for p in DATA["patients"]:
        seen[(p["vignette"], group(p))].add((colour(p), p["language"], p["sex"]))
    split = {k: v for k, v in seen.items() if len({c for c, _, _ in v}) > 1}
    assert not split, split


def test_no_red_vignette_comes_out_green():
    assert not [p["id"] for p in DATA["patients"] if p["expect"] == "red" and colour(p) == "green"]


def test_incomplete_patients_are_never_green():
    assert all(colour(p) != "green" for p in DATA["incomplete"])


@pytest.mark.parametrize("lang,text,want", [
    ("hi", "एक घंटे पहले अचानक दायां हाथ और पैर कमजोर हो गया, बोली लड़खड़ा रही है", "red"),
    ("hi", "अचानक ज़िंदगी का सबसे तेज़ सिर दर्द और उल्टी", "red"),
    ("or", "ହଠାତ ଜୀବନର ସବୁଠୁ ଭୟଙ୍କର ମୁଣ୍ଡ ବିନ୍ଧା ଓ ବାନ୍ତି", "red"),
    ("hi", "मिट्टी के तेल के स्टोव से छाती और दोनों हाथ जल गए", "red"),  # IITT major burn
    ("en", "Burns on the chest and both arms from the kerosene stove", "red"),  # major burn; a stove is not poisoning
    ("en", "Small burn on one finger from the stove", "yellow"),
    ("en", "Burning in the chest after meals for two weeks", "green"),  # heartburn is not a burn
    ("en", "Vomiting since last night, cannot keep water down", "yellow"),
    ("or", "କିରାସିନି ଷ୍ଟୋଭରୁ ଛାତି ଓ ଦୁଇ ହାତ ପୋଡ଼ିଗଲା", "red"),  # IITT major burn: both arms are 18 %
    ("hi", "एक हफ्ते से दोनों हाथों पर खुजली वाले दाने, बुखार नहीं", "green"),  # खुजली contains जल; not a burn
    ("en", "Cough for three weeks with weight loss and sweating at night", "yellow"),  # NTEP presumptive TB
    ("hi", "तीन हफ्ते से खांसी, वजन कम हो रहा है और रात को पसीना आता है", "yellow"),
])
def test_phrases_found_by_the_set(lang, text, want):
    i = {"category": "normal", "language": lang, "chief_complaint": text, "symptoms": [], "selected_symptoms": [], "answers": [],
         "severity": 2, "duration": "Today", "exam": {"done": True, "signs": [], "by": "Nurse"},
         "vitals": {"pulse": 80, "resp_rate": 16, "spo2": 98, "bp_systolic": 120, "bp_diastolic": 80, "temp_f": 98.6, "avpu": "A"}}
    assert evaluate_full(i, 40, "male")["urgency"] == want


def test_bleeding_that_stopped_is_not_bleeding():
    i = {"category": "normal", "language": "en", "chief_complaint": "Small cut on the finger while cooking, bleeding stopped", "symptoms": [],
         "selected_symptoms": [], "answers": []}
    assert evaluate_full(i, 40, "male")["findings"]["bleeding"]["value"] is not True


def test_asthma_with_spo2_below_94_is_yellow():
    i = {"category": "normal", "language": "or", "chief_complaint": "ଶ୍ୱାସ ରୋଗ ଅଛି, ରାତିରେ ଇନହେଲର ଅଧିକ ନେବାକୁ ପଡ଼ୁଛି", "symptoms": [],
         "selected_symptoms": [], "answers": [], "severity": 2, "duration": "3-7 days", "exam": {"done": True, "signs": [], "by": "Nurse"},
         "vitals": {"pulse": 80, "resp_rate": 16, "spo2": 93, "bp_systolic": 120, "bp_diastolic": 80, "temp_f": 98.6, "avpu": "A"}}
    r = evaluate_full(i, 40, "female")
    assert r["urgency"] == "yellow" and "GINA-ASTHMA-LOW-SPO2" in {h["rule_id"] for h in r["hits"]}
    i["vitals"]["spo2"] = 97
    assert evaluate_full(i, 40, "female")["urgency"] == "green"


@pytest.mark.parametrize("vignette,flag", [("Y06", "FU-HTN-STAGE2"), ("Y13", "FU-JAUNDICE"), ("Y15", "FU-HAEMATURIA")])
def test_follow_up_flags_fire_in_every_language_and_never_change_the_colour(vignette, flag):
    ps = [p for p in DATA["patients"] if p["vignette"] == vignette]
    for p in ps:
        r = evaluate_full({"symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [], **p["intake"]}, p["age"], SEX[p["sex"]])
        assert flag in {f["id"] for f in r["followups"]}, p["id"]
        assert not any(h["rule_id"].startswith("FU-") for h in r["hits"])
    assert {p["language"] for p in ps} == {"en", "hi", "or"}
