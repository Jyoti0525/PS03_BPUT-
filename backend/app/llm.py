"""Readable note summary from a small local language model, with hard checks (B5, C4).

The rules engine decides urgency and the template note holds every fact. The model only rewrites the facts as a
short handover paragraph. Its text replaces the template summary only if it passes all of these, otherwise the
template stays and the attempt is recorded (status FAIL_FELL_BACK) with the reason and the rejected text:

1. Faithfulness — every number (digits or words), unit and medicine in the output appears in the fact sheet, and
   every symptom it mentions agrees with the rules engine's findings (catches "no chest pain" → "chest pain").
2. Output guard — no condition name, diagnostic phrasing or medicine/treatment advice the facts do not contain.

Second opinion on urgency (C8): the same model, given the same fact sheet but not the rules' result, names the tier it
would pick and why. It is shown beside the rules' result and never replaces it: urgency stays with the rules engine,
and only a doctor can change it (audited override). An opinion higher than the rules adds a "take a second look"
flag; a lower one is only shown. Its reason goes through the same checks; a reason that fails is withheld.

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


def _chat(system: str, user: str, max_tokens: int) -> str:
    s = get_settings()
    if not s.llm_url:
        raise LlmUnavailable("No language model server configured")
    body = {
        "model": s.llm_model_name,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(s.llm_url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=s.llm_timeout_s) as r:  # nosec B310: http(s) URL checked in config
            out = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LlmUnavailable(f"Language model server not reachable: {e}") from e
    return re.sub(r"<think>.*?</think>", "", out["choices"][0]["message"]["content"], flags=re.S).strip()


def _complete(facts: str) -> str:
    text = _chat(SYSTEM, "Fact sheet:\n" + facts, 260)
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


# ---------------------------------------------------------------- second opinion on urgency (C8)

OPINION_SYSTEM = (
    "You are helping staff double-check a triage rules engine in an Indian public health facility. Read the fact sheet "
    "and say how soon this patient should be seen, using one of three tiers:\n"
    "RED: could be life-threatening; a doctor must see the patient now.\n"
    "YELLOW: should be seen soon, ahead of routine patients.\n"
    "GREEN: routine; can wait in the normal queue.\n"
    "If no vital signs were measured, do not choose GREEN.\n"
    "Answer in exactly two lines:\n"
    "URGENCY: RED or YELLOW or GREEN\n"
    "REASON: the facts from the sheet that decided it, as a short list separated by commas, copied as written "
    "(for example: temperature 102.4 °F, breathing 52 /min, fever for 2 days).\n"
    "The reason only lists facts. Do not explain or interpret them or say what they might mean or be caused by. Never "
    "name a disease or condition the sheet does not name, and never suggest any medicine, test or treatment. Never "
    "mention a name."
)
TIERS = ("green", "yellow", "red")


def _opinion_text(facts: str) -> str:
    return _chat(OPINION_SYSTEM, "Fact sheet:\n" + facts, 120)


def parse_opinion(text: str) -> tuple[str | None, str]:
    """(tier or None, reason) from the model's two-line answer. Anything else is unreadable, never guessed."""
    m = re.search(r"urgency\W*\s*(red|yellow|green)\b", text, re.I)
    if not m:
        named = set(re.findall(r"\b(red|yellow|green)\b", text.split("\n")[0], re.I))
        m_tier = named.pop().lower() if len(named) == 1 else None
    else:
        m_tier = m.group(1).lower()
    r = re.search(r"reason\W*\s*(.+)", text, re.I | re.S)
    return m_tier, (r.group(1).strip().split("\n")[0].strip(" *") if r else "")


def urgency_opinion(note: dict, intake: dict, patient) -> dict | None:
    """The model's own tier for this case, compared with the rules' tier. Never changes the encounter's urgency."""
    rules = (note.get("triage") or {}).get("urgency")
    if rules not in TIERS:
        return None
    facts = fact_sheet(note, intake, patient)
    t = time.perf_counter()
    try:
        text = _opinion_text(facts)
    except LlmUnavailable as e:
        return {"status": "UNAVAILABLE", "model": model_name(), "rules_urgency": rules, "reason_unavailable": str(e)}
    out = {"model": model_name(), "ms": round((time.perf_counter() - t) * 1000), "rules_urgency": rules, "guard_version": output_guard.version()}
    tier, reason = parse_opinion(text)
    if tier is None:
        return {**out, "status": "UNREADABLE", "raw": text[:300]}
    rank = TIERS.index(tier) - TIERS.index(rules)
    out |= {"status": "AGREE" if rank == 0 else "DISAGREE", "model_urgency": tier, "direction": None if rank == 0 else ("higher" if rank > 0 else "lower")}
    if reason:
        problems = faithfulness(reason, facts, (note.get("triage") or {}).get("findings") or {})
        verdict = output_guard.check(reason, facts)
        if problems or not verdict.ok:
            out["reason_withheld"] = verdict.reasons() + problems  # the tier is shown; the reason that failed the checks is not
        else:
            out["reason"] = reason
    return out


def apply(note: dict, intake: dict, patient) -> dict:
    """Note with the model's summary when it passed every check; otherwise the template note plus a record of why.
    Also adds the model's second opinion on urgency (C8) beside the rules' result."""
    if intake.get("ai_assist") is False:
        return note
    result = write_summary(note, intake, patient)
    note = dict(note)
    note["llm"] = result
    flags = [f for f in note.get("flags") or [] if f.get("code") not in ("LLM-FELL-BACK", "LLM-OFF", "AI-OPINION-HIGHER")]
    if get_settings().llm_urgency_opinion:
        if result["status"] == "UNAVAILABLE":  # same server: don't wait for a second timeout
            op = {"status": "UNAVAILABLE", "model": result["model"], "rules_urgency": (note.get("triage") or {}).get("urgency"), "reason_unavailable": result["reason"]}
        else:
            op = urgency_opinion(note, intake, patient)
        if op:
            note["llm_opinion"] = op
            if op.get("direction") == "higher":
                said = f": {op['reason']}" if op.get("reason") else ""
                flags.append({"code": "AI-OPINION-HIGHER", "label": "AI second opinion is more urgent than the rules — take a second look", "severity": "warning",
                              "reason": f"{op['model']} would choose {op['model_urgency'].upper()}{said}. Urgency stays {op['rules_urgency'].upper()} from the rules; only a doctor can change it."})
    from .triage.pipeline import processing_status

    stages = [s for s in (note.get("processing_status") or {}).get("stages", []) if s["stage"] != "AI summary"]
    if result["status"] == "PASS":
        stages.append({"stage": "AI summary", "status": "ok", "detail": result["model"]})
    elif result["status"] == "UNAVAILABLE":
        stages.append({"stage": "AI summary", "status": "fallback", "detail": f"model not available ({result['reason']}); template summary shown"})
        flags.append({"code": "LLM-OFF", "label": "AI summary not available — template summary shown", "severity": "info",
                      "reason": f"{result['reason']}. The note is complete without it; urgency always comes from the rules."})
    else:
        stages.append({"stage": "AI summary", "status": "fallback", "detail": "model output failed the checks; template summary shown"})
    note["processing_status"] = processing_status(stages)
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
