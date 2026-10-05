"""Readable note summary from a small local language model, with hard checks (B5, C4).

The rules engine decides urgency and the template note holds every fact. The model only rewrites the facts as a
short handover paragraph. Its text replaces the template summary only if it passes all of these, otherwise the
template stays and the attempt is recorded (status FAIL_FELL_BACK) with the reason and the rejected text:

1. Faithfulness — every number (digits or words), unit and medicine in the output appears in the fact sheet, and
   every symptom it mentions agrees with the rules engine's findings (catches "no chest pain" → "chest pain").
2. Output guard — no condition name, diagnostic phrasing or medicine/treatment advice the facts do not contain.

Engine: Qwen3-4B-Instruct-2507 (Alibaba Qwen, Apache-2.0), 4-bit GGUF, served by llama.cpp's llama-server on the
facility machine (`JEEVIA_LLM_URL`, OpenAI-compatible). No server configured or reachable → template note, and the
note says so. Patients who chose "continue without AI" never reach this module.
"""

import json
import logging
import re
import time
import urllib.error
import urllib.request

from . import output_guard
from .config import get_settings

log = logging.getLogger("jeevia.llm")

SYSTEM = (
    "You write the summary paragraph of a triage note for a nurse or doctor in an Indian public health facility. "
    "You are given a fact sheet. Rewrite it as 2 to 4 plain sentences in English: who the patient is, what they "
    "report in their own words, and the values that were measured or read from a report.\n"
    "Rules you must follow:\n"
    "- Use only the facts given. Do not add, guess or infer anything.\n"
    "- Copy every number and unit exactly as written. Do not convert or round.\n"
    "- Keep the patient's negatives exactly as given; never add a denial the fact sheet does not contain.\n"
    "- Never name a disease or condition unless the fact sheet names it, never suggest a diagnosis or cause, and never "
    "suggest any medicine, dose, test or treatment.\n"
    "- Do not list what is missing or not recorded, and do not mention rules, flags or urgency: the note shows those separately.\n"
    "- Never mention a name, and leave out placeholders in square brackets such as [NAME] or [PHONE].\n"
    "- Output only the paragraph."
)

_NUMBER_WORDS = {
    w: str(i) for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen twenty".split()
    )
} | {"thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90", "hundred": "100", "once": "1", "twice": "2", "thrice": "3"}
_UNITS = r"mmhg|mg/dl|g/dl|mmol/l|bpm|/min|°f|°c|%|kg|cm|weeks?|days?|hours?|months?|years?|minutes?|times?"


class LlmUnavailable(RuntimeError):
    pass


def model_name() -> str:
    return get_settings().llm_model_name


# ---------------------------------------------------------------- facts


def fact_sheet(note: dict, intake: dict, patient) -> str:
    """Everything the model may use, as plain lines. The checks below compare its output against this text."""
    sex = {"F": "female", "M": "male"}.get(patient.sex, "patient")
    # "normal" is the app's category name for a general visit; the model read it as "a normal check-up", which
    # understates an acute complaint (seen 5 Oct in the held-out evaluation).
    visit = {"maternal": "Pregnancy visit", "chronic": "Follow-up for a long-term condition"}.get(intake.get("category"), "General visit for a new problem")
    lines = [f"Patient: {patient.age}-year-old {sex}", f"Visit type: {visit}",
             f"Chief complaint (patient's words, in English): {intake.get('chief_complaint')}"]
    for s in intake.get("symptoms") or []:
        lines.append(f"Patient said (English rendering): {s.get('text')}")
    if intake.get("selected_symptoms"):
        lines.append("Symptoms tapped by patient: " + ", ".join(intake["selected_symptoms"]))
    for t in note.get("timeline") or []:
        if t.get("event", "").startswith("Onset"):
            lines.append(f"Onset: {t['when']} ({(t.get('certainty') or 'unknown').lower()}{', patient said: ' + t['raw'] if t.get('raw') else ''})")
    if intake.get("severity") is not None:
        lines.append(f"Self-rated severity: {intake['severity']} out of 10")
    for a in intake.get("answers") or []:
        lines.append(f"Answer to \"{a.get('question')}\": {a.get('answer')}")
    m = intake.get("maternal") or {}
    if m.get("gestation_weeks"):
        lines.append(f"Pregnant, {m['gestation_weeks']} weeks by history")
    c = intake.get("chronic") or {}
    if c.get("condition"):
        lines.append(f"Known condition: {c['condition']}; feels {c.get('feeling_vs_last', 'unsure')} compared with last visit")
    if c.get("current_medicines"):
        lines.append(f"Current medicines (as reported): {c['current_medicines']}")
    for v in note.get("vitals") or []:
        lines.append(f"Measured {v['label']}: {v['value']}{' ' + v['unit'] if v.get('unit') else ''}")
    for x in note.get("labs") or []:
        if x.get("status") == "abnormal":
            lines.append(f"Report value outside reference range: {x['label']} {x['value']}{' ' + x['unit'] if x.get('unit') else ''}")
    # Fired rules and missing items are left out: they have their own sections on the note, and rule text lists several
    # conditions at once ("fever or hypothermia, headache, or stiff neck"), which in prose reads as if the patient had all.
    return "\n".join(lines)


# ---------------------------------------------------------------- checks


def _numbers(text: str) -> set[str]:
    t = text.lower()
    nums = set(re.findall(r"\d+(?:\.\d+)?", t))
    nums |= {_NUMBER_WORDS[w] for w in re.findall(r"[a-z]+", t) if w in _NUMBER_WORDS}
    return nums


def _units(text: str) -> set[str]:
    return {u.rstrip("s") for u in re.findall(rf"(?<![a-z])({_UNITS})(?![a-z])", text.lower())}


def faithfulness(output: str, facts: str, findings: dict) -> list[str]:
    """Reasons the output is not faithful to the facts (empty = faithful)."""
    from .output_guard import _compiled
    from .triage.findings import scan_text

    problems = []
    extra_numbers = _numbers(output) - _numbers(facts) - {"1"}  # "a"/"one" are too common to police
    if extra_numbers:
        problems.append(f"numbers not in the record: {', '.join(sorted(extra_numbers))}")
    extra_units = _units(output) - _units(facts)
    if extra_units:
        problems.append(f"units not in the record: {', '.join(sorted(extra_units))}")
    facts_n = output_guard.normalise(facts)
    for cat, _, rx in _compiled()[2]:
        if cat == "drug_advice":
            for m in rx.finditer(output_guard.normalise(output)):
                if m.group(0) not in facts_n and re.search(r"[a-z]{4,}", m.group(0)):
                    problems.append(f'medicine or treatment word not in the record: "{m.group(0)}"')
    for fid, f in scan_text(output, "summary").items():
        recorded = (findings.get(fid) or {}).get("value")
        if f.value is True and recorded is not True:
            problems.append(f"states {fid.replace('_', ' ')}, which the record does not")
        if f.value is False and recorded is True:
            problems.append(f"denies {fid.replace('_', ' ')}, which the record states")
    return list(dict.fromkeys(problems))


# ---------------------------------------------------------------- model call


def _complete(facts: str) -> str:
    s = get_settings()
    if not s.llm_url:
        raise LlmUnavailable("No language model server configured")
    body = {
        "model": s.llm_model_name,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Fact sheet:\n" + facts}],
        "temperature": 0,
        "max_tokens": 260,
    }
    req = urllib.request.Request(s.llm_url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=s.llm_timeout_s) as r:
            out = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LlmUnavailable(f"Language model server not reachable: {e}") from e
    text = re.sub(r"<think>.*?</think>", "", out["choices"][0]["message"]["content"], flags=re.S)
    text = re.sub(r",?\s+(named|called)\s+\[[A-Z]+\]", "", text)  # "a 58-year-old woman named [NAME]" → "a 58-year-old woman"
    return text.strip()


def write_summary(note: dict, intake: dict, patient) -> dict:
    """Return the `llm` block for the note: status, text (when it passed) and the checks that ran."""
    facts = fact_sheet(note, intake, patient)
    t = time.perf_counter()
    try:
        text = _complete(facts)
    except LlmUnavailable as e:
        return {"status": "UNAVAILABLE", "model": model_name(), "reason": str(e)}
    ms = round((time.perf_counter() - t) * 1000)
    base = {"model": model_name(), "ms": ms, "guard_version": output_guard.version()}
    problems = faithfulness(text, facts, (note.get("triage") or {}).get("findings") or {})
    verdict = output_guard.check(text, facts)
    if problems or not verdict.ok:
        return {**base, "status": "FAIL_FELL_BACK", "rejected_text": text, "faithfulness": problems, "guard": verdict.reasons()}
    return {**base, "status": "PASS", "text": text}


def apply(note: dict, intake: dict, patient) -> dict:
    """Note with the model's summary when it passed every check; otherwise the template note plus a record of why."""
    if intake.get("ai_assist") is False:
        return note
    result = write_summary(note, intake, patient)
    note = dict(note)
    note["llm"] = result
    flags = [f for f in note.get("flags") or [] if f.get("code") not in ("LLM-FELL-BACK", "LLM-OFF")]
    if result["status"] == "PASS":
        note["summary_template"] = note["summary"]
        note["summary"] = result["text"] + " Summary written from the recorded facts only; it is not a diagnosis."
        note["renderer"] = "LLM"
    else:
        note["renderer"] = "TEMPLATE"
        if result["status"] == "FAIL_FELL_BACK":
            why = "; ".join(result["guard"] + result["faithfulness"])
            flags.append({"code": "LLM-FELL-BACK", "label": "AI summary rejected — template summary shown", "severity": "info",
                          "reason": f"{result['model']} output failed the checks ({why})"})
    note["flags"] = flags
    return note
