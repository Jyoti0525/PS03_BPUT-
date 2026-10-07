"""G7 bias table: errors by language, sex and age band.

1. Speech: word error rate by speaker sex, per language, from the FLEURS clips already scored
   (docs/evaluation/asr_<lang>_fleurs_dev25_ctc_int8_conf.json; sex from FLEURS dev.tsv). FLEURS has no speaker age.
2. Rules: a counterfactual check on the 50 synthetic cases (tests/data/llm_eval_cases.yaml). Each non-maternal case is
   re-run with only the sex flipped, and each adult case with only the age moved into every adult band. The urgency
   should not change unless a rule is meant to depend on it (age gates of a protocol); every change is listed.
3. Second opinion (C8): agreement with the rules by sex and age band, from docs/evaluation/llm_opinion_all.json.

    python backend/scripts/eval_bias.py   →  docs/evaluation/bias.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.triage.rules import evaluate_full  # noqa: E402
from eval_llm import intake_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BANDS = [("under 12", 0, 11), ("12–17", 12, 17), ("18–39", 18, 39), ("40–59", 40, 59), ("60+", 60, 200)]
ADULT_AGES = {"18–39": 30, "40–59": 50, "60+": 70}


def band(age: int) -> str:
    return next(b for b, lo, hi in BANDS if lo <= age <= hi)


def speech() -> dict:
    out = {}
    for lang in ("or", "hi", "kn"):
        sex = {}
        for line in (ROOT / f"models/eval/fleurs_{lang}/dev.tsv").read_text(encoding="utf-8").splitlines():
            f = line.split("\t")
            if len(f) > 6:
                sex[f[1]] = f[6].lower()
        clips = json.loads((ROOT / f"docs/evaluation/asr_{lang}_fleurs_dev25_ctc_int8_conf.json").read_text(encoding="utf-8"))["clips"]
        acc = defaultdict(lambda: [0.0, 0, 0])  # word errors, reference words, clips
        for c in clips:
            n = len(c["reference"].split())
            a = acc[sex.get(c["file"], "unknown")]
            a[0] += c["wer"] * n
            a[1] += n
            a[2] += 1
        out[lang] = {s: {"clips": a[2], "words": a[1], "wer": round(100 * a[0] / a[1], 1)} for s, a in sorted(acc.items())}
    return out


def rules() -> dict:
    data = yaml.safe_load((ROOT / "backend/tests/data/llm_eval_cases.yaml").read_text(encoding="utf-8"))
    cases = data["cases"] + data["held_out"]
    sex_runs, sex_changes, age_runs, age_changes = 0, [], 0, []
    for i, c in enumerate(cases, 1):
        intake = intake_for(c)
        base = evaluate_full(intake, c["age"], c["sex"])["urgency"]
        if c["category"] != "maternal":
            other = "M" if c["sex"] == "F" else "F"
            u = evaluate_full(intake, c["age"], other)["urgency"]
            sex_runs += 1
            if u != base:
                sex_changes.append({"case": i, "chief": c["chief"], "sex": f"{c['sex']}→{other}", "from": base, "to": u})
        if c["age"] >= 18:
            for b, age in ADULT_AGES.items():
                if b == band(c["age"]):
                    continue
                r = evaluate_full(intake, age, c["sex"])
                age_runs += 1
                if r["urgency"] != base:
                    age_changes.append({"case": i, "chief": c["chief"], "age": f"{c['age']}→{age}", "from": base, "to": r["urgency"],
                                        "rules": sorted({h["rule_id"] for h in r["hits"]})})
    return {"cases": len(cases), "sex_flips": sex_runs, "sex_changes": sex_changes, "age_moves": age_runs, "age_changes": age_changes}


def opinion() -> dict:
    p = ROOT / "docs/evaluation/llm_opinion_all.json"
    data = yaml.safe_load((ROOT / "backend/tests/data/llm_eval_cases.yaml").read_text(encoding="utf-8"))
    cases = data["cases"] + data["held_out"]
    rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        c = cases[r["case"] - 1]
        agree = r["model_urgency"] == r["rules_urgency"]
        for key in (f"sex {c['sex']}", f"age {band(c['age'])}"):
            by[key][0] += agree
            by[key][1] += 1
    return {k: {"agree": a, "of": n} for k, (a, n) in sorted(by.items())}


if __name__ == "__main__":
    res = {"speech_wer_by_sex": speech(), "rules_counterfactual": rules(), "opinion_agreement": opinion()}
    (ROOT / "docs/evaluation/bias.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
