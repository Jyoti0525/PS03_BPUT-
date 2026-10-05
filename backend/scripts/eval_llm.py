"""Measure the note-summary model (B5) on synthetic intakes: how often its text passes the faithfulness check and the
output guard (otherwise the template is shown), why it fails, and how long it takes.

Each case goes through the real rules engine and note builder, then llm.write_summary(). Needs llama-server running
(backend/scripts/start_llm.sh) and JEEVIA_LLM_URL set.

    JEEVIA_LLM_URL=http://127.0.0.1:8031 python backend/scripts/eval_llm.py [cases|held_out] [out.json]

Second opinion on urgency (C8): how often the model's own tier matches the rules', in which direction it differs,
and how often its reason is withheld by the checks. The rules' tier is the reference here, not a clinician's.

    JEEVIA_LLM_URL=http://127.0.0.1:8031 python backend/scripts/eval_llm.py opinion [cases|held_out|all] [out.json]
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import llm  # noqa: E402
from app.triage.pipeline import build_note  # noqa: E402
from app.triage.rules import evaluate_full  # noqa: E402

CASES = Path(__file__).resolve().parents[1] / "tests" / "data" / "llm_eval_cases.yaml"


def intake_for(c: dict) -> dict:
    return {
        "category": c["category"], "language": "en", "chief_complaint": c["chief"], "symptoms": [], "selected_symptoms": [],
        "duration": c.get("duration"), "severity": c.get("severity"), "answers": [], "file_ids": [], "vitals": c.get("vitals"),
        "maternal": c.get("maternal"), "chronic": c.get("chronic"), "ai_assist": True,
    }


def main(which: str = "cases", out: str | None = None) -> None:
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))[which]
    rows = []
    for i, c in enumerate(cases, 1):
        patient = SimpleNamespace(name="[NAME]", age=c["age"], sex=c["sex"])
        intake = intake_for(c)
        triage = evaluate_full(intake, c["age"], c["sex"])
        note = build_note(intake=intake, patient=patient, triage=triage, files=[], history=[], proxy=False)
        r = llm.write_summary(note, intake, patient)
        rows.append({"case": i, "chief": c["chief"], "urgency": triage["urgency"], **r})
        mark = {"PASS": "pass", "FAIL_FELL_BACK": "FELL BACK", "UNAVAILABLE": "UNAVAILABLE"}[r["status"]]
        print(f"{i:2d} {mark:11s} {r.get('ms', 0):5d} ms  {c['chief'][:60]}")
        if r["status"] == "FAIL_FELL_BACK":
            for why in r["guard"] + r["faithfulness"]:
                print(f"      - {why}")
        if r["status"] == "UNAVAILABLE":
            sys.exit(f"Model server unavailable: {r['reason']}")
    n = len(rows)
    passed = [x for x in rows if x["status"] == "PASS"]
    ms = sorted(x["ms"] for x in rows)
    summary = {
        "model": llm.model_name(), "set": which, "cases": n, "passed": len(passed), "fell_back": n - len(passed),
        "pass_rate": round(len(passed) / n, 3), "median_ms": ms[n // 2], "max_ms": ms[-1],
        "guard_blocks": sum(1 for x in rows if x.get("guard")), "faithfulness_failures": sum(1 for x in rows if x.get("faithfulness")),
    }
    print(json.dumps(summary, indent=1))
    if out:
        Path(out).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


def opinions(which: str = "all", out: str | None = None) -> None:
    data = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    cases = data["cases"] + data["held_out"] if which == "all" else data[which]
    rows, tiers = [], ("red", "yellow", "green")
    matrix = {r: dict.fromkeys(tiers, 0) for r in tiers}
    for i, c in enumerate(cases, 1):
        patient = SimpleNamespace(name="[NAME]", age=c["age"], sex=c["sex"])
        intake = intake_for(c)
        triage = evaluate_full(intake, c["age"], c["sex"])
        note = build_note(intake=intake, patient=patient, triage=triage, files=[], history=[], proxy=False)
        r = llm.urgency_opinion(note, intake, patient)
        if r["status"] == "UNAVAILABLE":
            sys.exit(f"Model server unavailable: {r['reason_unavailable']}")
        rows.append({"case": i, "chief": c["chief"], "provisional": triage["provisional"], **r})
        if r["status"] in ("AGREE", "DISAGREE"):
            matrix[r["rules_urgency"]][r["model_urgency"]] += 1
        print(f"{i:2d} rules {r['rules_urgency']:6s} model {r.get('model_urgency', '?'):6s} {r['ms']:5d} ms  {c['chief'][:55]}")
        print(f"      {r.get('reason') or ('withheld: ' + '; '.join(r['reason_withheld']) if r.get('reason_withheld') else r.get('raw', ''))}")
    n = len(rows)
    read = [x for x in rows if x["status"] in ("AGREE", "DISAGREE")]
    ms = sorted(x["ms"] for x in rows)
    summary = {
        "model": llm.model_name(), "set": which, "cases": n, "unreadable": n - len(read),
        "agree": sum(x["status"] == "AGREE" for x in read), "agreement": round(sum(x["status"] == "AGREE" for x in read) / max(len(read), 1), 3),
        "model_higher": sum(x.get("direction") == "higher" for x in read), "model_lower": sum(x.get("direction") == "lower" for x in read),
        "model_lower_on_rules_red": matrix["red"]["yellow"] + matrix["red"]["green"],
        "model_lower_on_provisional": sum(x.get("direction") == "lower" and x["provisional"] for x in read),
        "reason_withheld": sum(bool(x.get("reason_withheld")) for x in read), "matrix_rules_by_model": matrix,
        "median_ms": ms[n // 2], "max_ms": ms[-1],
    }
    print(json.dumps(summary, indent=1))
    if out:
        Path(out).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:2] == ["opinion"]:
        opinions(*(sys.argv[2:4]))
    else:
        main(*(sys.argv[1:3]))
