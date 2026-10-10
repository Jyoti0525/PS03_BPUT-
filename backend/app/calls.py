"""E6 · Reminder calls for maternal and chronic follow-ups, simulated in the browser (no telephony in this build).

The assigned health worker is the first channel (D4); a call is the fallback when they cannot reach the patient.

* The agent does logistics (the check-up is due, can you come this week) and bounded collection (yes / no questions
  about danger signs), in any of the 11 languages Sarvam's voice speaks, from fixed lines in calls.yaml. It never answers with advice:
  India's Telemedicine Practice Guidelines 2020 do not let an AI platform counsel a patient.
* Every answer is read by rules, not a model: the same multilingual lexicon as intake (triage/findings.py) looks for
  danger signs anywhere in what was said, and a short-answer list reads yes / no / not sure. The lexicon covers
  English, Hindi and Odia; in other languages it reads the English translation, and an answer that cannot be translated
  counts only if it is a plain yes or no. A hedge ("less", "a little") makes any answer "not sure".
* A danger sign ends the call at once and pages a person (an alert to the medical officer and the assigned health
  worker). So does "not sure" or an answer that cannot be read twice on a danger-sign question: unknown is never normal.
* Escalation is inverted: the more serious the case, the less AI on the call. The agent may call only after a routine
  visit; if the last visit was RED or YELLOW, or the patient chose no AI, a person calls (and may use the same script).
* On a phone that is not the woman's own, or when someone else answers, nothing about health is said.
* "No" to every question from an automated voice is weak evidence: the follow-up stays open until the visit.
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import alerts as al
from . import audit
from .models import Call, Encounter, Patient, Reminder, User
from .services import aware, now
from .triage.findings import FINDINGS, _loose, scan_text

LANGS = ("en", "hi", "or", "bn", "ta", "te", "gu", "kn", "ml", "mr", "pa")  # what Sarvam's Bulbul voice speaks
LEXICON_LANGS = ("en", "hi", "or")  # danger-sign word lists in triage/findings.py
PROGRAMME = {"anc_checkup": "maternal", "chronic_checkin": "chronic", "clinical_checkin": "general"}
ENDED_BY_CALLER = ("no_answer", "hung_up")


@lru_cache
def config() -> dict:
    with open(Path(__file__).with_name("calls.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def _sources() -> dict:
    with open(Path(__file__).parent / "triage" / "rules" / "sources.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]


def red_flags(programme: str) -> set[str]:
    rf = config()["red_flags"]
    return set(rf["general"]["findings"]) | set(rf[programme]["findings"])


def sources(programme: str) -> list[dict]:
    rf = config()["red_flags"]
    ids = list(dict.fromkeys(rf[programme]["sources"] + rf["general"]["sources"]))
    return [{"id": i, "short": _sources()[i]["short"]} for i in ids]


def _question(programme: str, key: str) -> dict:
    return next(q for q in config()["scripts"][programme] if q["key"] == key)


# ── who may call ──────────────────────────────────────
def last_encounter(db: Session, patient_id: str) -> Encounter | None:
    return db.scalar(select(Encounter).where(Encounter.patient_id == patient_id).order_by(Encounter.created_at.desc()).limit(1))


def who_calls(db: Session, r: Reminder, p: Patient) -> dict:
    """agent | human | home_visit, and why. The more serious the case, the less AI on the call."""
    if r.phone_belongs_to == "none" or not p.phone:
        return {"who": "home_visit", "why": "No phone: a home visit is needed"}
    last = last_encounter(db, p.id)
    fired = {h.get("rule_id") for h in ((last.note or {}).get("rules_fired") or [])} if last else set()
    if last and last.urgency == "yellow" and fired <= {"SAFE-PROVISIONAL"}:
        return {"who": "human", "why": "The last visit was never fully assessed (UNDETERMINED): a person calls, not the agent"}
    if last and last.urgency in ("red", "yellow"):
        return {"who": "human", "why": f"The last visit was {last.urgency.upper()}: a person calls, not the agent"}
    if last and (last.intake or {}).get("ai_assist") is False:
        return {"who": "human", "why": "The patient chose no AI processing: a person calls"}
    return {"who": "agent", "why": "Routine follow-up: the agent may call, and any danger sign hands the call to a person"}


# ── what is said ──────────────────────────────────────
def gestation_now(db: Session, r: Reminder) -> int | None:
    enc = db.get(Encounter, r.encounter_id) if r.encounter_id else None
    gw = ((enc.intake or {}).get("maternal") or {}).get("gestation_weeks") if enc else None
    return gw + (now() - aware(enc.created_at)).days // 7 if gw else None


def condition_of(db: Session, r: Reminder) -> str | None:
    if r.kind != "chronic_checkin":
        return None
    enc = db.get(Encounter, r.encounter_id) if r.encounter_id else None
    return ((enc.intake or {}).get("chronic") or {}).get("condition") if enc else None


def _condition_words(condition: str | None, lang: str) -> str:
    c = (condition or "").lower()
    for k, words in config()["conditions"].items():
        if k == "default":
            continue
        if k in c or (k == "hypertension" and re.search(r"\bbp\b|blood pressure", c)) or (k == "diabetes" and "sugar" in c):
            return words[lang]
    return condition or config()["conditions"]["default"][lang]


def _ctx(db: Session, call: Call, lang: str) -> dict:
    r = db.get(Reminder, call.reminder_id)
    p = db.get(Patient, call.patient_id)
    return {"name": al.first_name(p), "facility": al.facility_name(db, call.facility_id), "date": aware(r.due_at).strftime("%d/%m"),
            "condition": _condition_words(condition_of(db, r), lang)}


def _text(db: Session, call: Call, key: str, lang: str) -> str:
    lines = config()["lines"]
    src = lines[key] if key in lines else _question(call.programme, key)
    return src[lang].format(**_ctx(db, call, lang))


def _say(db: Session, call: Call, key: str) -> None:
    call.turns = [*call.turns, {"who": "agent", "key": key, "text": _text(db, call, key, call.language),
                                "text_en": _text(db, call, key, "en"), "at": now().isoformat()}]


def plan_for(db: Session, r: Reminder, programme: str, audience: str) -> list[str]:
    if audience == "other":
        return ["neutral"]
    gw = gestation_now(db, r) if programme == "maternal" else None
    keys = []
    for q in config()["scripts"][programme]:
        need = q.get("min_gestation_weeks")
        if need and (gw is None or gw < need):
            continue  # reduced movements are asked only from 24 weeks, and not when gestation is unknown
        keys.append(q["key"])
    return keys


def asks_yes_no(call: Call) -> bool:
    if call.status != "active" or call.step >= len(call.plan):
        return False
    key = call.plan[call.step]
    return key in ("identity", "neutral", "neutral_other") or _question(call.programme, key)["kind"] in ("logistics", "danger", "note")


# ── reading an answer ─────────────────────────────────
_PUNCT = re.compile(r"[.,!?;:।॥|\"“”()\[\]{}\-–—]")


def _norm(s: str) -> str:
    return " " + " ".join(_PUNCT.sub(" ", unicodedata.normalize("NFC", s or "").lower()).split()) + " "


def read_short_answer(*texts: str) -> str | None:
    """yes | no | unsure | None, from whole words or phrases. A hedge ("କମ୍ ହଲୁଛି", moving less) or "not sure" wins over
    yes and no (पता नहीं contains नहीं); otherwise the first one said wins ("no, but…")."""
    words = config()["answers"]
    for text in texts:
        plain, loose = _norm(text), _norm(_loose(text))
        hits: dict[str, int] = {}
        for kind in ("hedge", "unsure", "no", "yes"):
            for lang, phrases in words[kind].items():
                hay = plain if lang == "en" else loose
                for ph in phrases:
                    i = hay.find(" " + (ph if lang == "en" else _loose(ph)) + " ")
                    if i >= 0:
                        hits[kind] = min(hits.get(kind, i), i)
        if "unsure" in hits or "hedge" in hits:
            return "unsure"
        if hits:
            return min(hits, key=hits.get)
    return None


def _bare_answer(text: str) -> bool:
    """The whole answer is one yes / no / not-sure phrase (so it can be read without a translation)."""
    said = _norm(_loose(text)).strip()
    return any(said == _norm(_loose(ph)).strip() for kind in config()["answers"].values() for phrases in kind.values() for ph in phrases)


def _english(said: str, lang: str) -> str | None:
    """English for an answer typed in a language the danger-sign lexicon does not cover (offline IndicTrans2)."""
    from . import language

    try:
        return language.translate_patient(said, lang)["text"]
    except Exception:  # models not installed or failed: the caller treats the answer as unreadable
        return None


def danger_signs(programme: str, *texts: str) -> list[dict]:
    """Danger signs said anywhere in the answer (negation aware), in the patient's words or the English translation."""
    out: dict[str, dict] = {}
    want = red_flags(programme)
    for text in texts:
        if not text:
            continue
        for fid, f in scan_text(text, "said on the call").items():
            if f.value is True and fid in want and fid not in out:
                out[fid] = {"finding": fid, "label": FINDINGS[fid][0], "evidence": f.evidence[0]}
    return list(out.values())


# ── the call ──────────────────────────────────────────
class CallRefused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def start(db: Session, r: Reminder, user: User, operator: str = "agent", language: str | None = None) -> Call:
    p = db.get(Patient, r.patient_id)
    programme = PROGRAMME.get(r.kind)
    if not programme:
        raise CallRefused(422, "This follow-up type does not support reminder calls")
    if r.status not in ("missed", "call_due", "contacted"):
        raise CallRefused(409, "A call is placed only after a missed check-up")
    mode = who_calls(db, r, p)
    if mode["who"] == "home_visit":
        raise CallRefused(422, "No phone to call — this needs a home visit")
    if operator == "agent" and mode["who"] == "human":
        raise CallRefused(409, mode["why"])
    lang = language if language in LANGS else (p.language if p.language in LANGS else "en")
    audience = "patient" if programme == "chronic" or r.phone_belongs_to == "self" else "other"
    call = Call(reminder_id=r.id, patient_id=p.id, facility_id=r.facility_id, started_by=user.id, operator=operator, programme=programme,
                language=lang, audience=audience, plan=plan_for(db, r, programme, audience), turns=[], notes={})
    db.add(call)
    db.flush()
    _say(db, call, "intro" if audience == "patient" else "neutral")
    audit.record(db, user, "CREATE", "call", call.id, f"Reminder call started ({'agent, simulated' if operator == 'agent' else 'by a person'}; "
                 f"{programme}; {'patient' if audience == 'patient' else 'neutral wording, nothing about health'}; language {lang})", p.code, r.facility_id)
    return call


def _note(call: Call, **kw) -> None:
    call.notes = {**(call.notes or {}), **kw}


def _advance(db: Session, call: Call) -> None:
    call.step += 1
    call.reprompts = 0
    if call.step >= len(call.plan):
        finish(db, call, "completed")
    else:
        _say(db, call, call.plan[call.step])


def answer(db: Session, call: Call, user: User, text: str, original: str | None = None) -> Call:
    """One answer from the patient (typed, tapped, or transcribed and translated). Rules decide what happens next."""
    if call.status != "active":
        raise CallRefused(409, "This call has ended")
    key = call.plan[call.step]
    said = (original or text or "").strip()
    english = (text or "").strip()
    unread = False
    if call.language not in LEXICON_LANGS and said and english == said and not _bare_answer(said):
        # Typed in a language the danger-sign lexicon does not cover: read the English, or nothing at all
        english = _english(said, call.language) or ""
        unread = not english
    heard = None if unread else read_short_answer(said, english)
    flags = danger_signs(call.programme, said, english)
    call.turns = [*call.turns, {"who": "patient", "key": key, "text": said, "text_en": english if english and english != said else None,
                                "heard": heard, "findings": [f["finding"] for f in flags], "at": now().isoformat(),
                                **({"unread": "Could not be translated to English, so it was not read"} if unread else {})}]
    if flags:
        return finish(db, call, "danger_sign", flags, user)
    if key in ("neutral", "neutral_other"):
        _note(call, message_passed_on=heard)
        return finish(db, call, "message_left", user=user)
    if key == "identity":
        if heard == "yes":
            _advance(db, call)
        elif heard is None and call.reprompts == 0:
            call.reprompts = 1
            _say(db, call, "reprompt")
        else:  # someone else, or unclear twice: say nothing about health
            call.audience = "other"
            call.plan = [*call.plan[: call.step + 1], "neutral_other"]
            _advance(db, call)
        return call
    q = _question(call.programme, key)
    if heard is None and q["kind"] in ("logistics", "danger", "note") and call.reprompts == 0:
        call.reprompts = 1
        _say(db, call, "reprompt")
        return call
    if q["kind"] == "logistics":
        _note(call, can_come={"yes": True, "no": False}.get(heard or ""))
    elif q["kind"] == "danger":
        if heard == q["flag_on"]:
            asked = _text(db, call, key, "en")
            hit = [{"finding": f, "label": FINDINGS[f][0], "evidence": f'answered "{said}" to: {asked}'} for f in q["findings"]]
            return finish(db, call, "danger_sign", hit, user)
        if heard != ("no" if q["flag_on"] == "yes" else "yes"):
            return finish(db, call, "unclear", [{"finding": None, "label": "No clear answer to a danger-sign question",
                                                 "evidence": f'"{said}" to: {_text(db, call, key, "en")}'}], user)
    elif q["kind"] == "note":
        if heard == q["note_on"]:
            _note(call, flags=[*(call.notes or {}).get("flags", []), q["note"]])
        elif heard != ("yes" if q["note_on"] == "no" else "no"):  # not sure, partly, or unreadable
            _note(call, flags=[*(call.notes or {}).get("flags", []), f"Unclear answer about: {q['en']}"])
    elif q["kind"] == "free" and heard != "no" and said:
        _note(call, said=said if not english or english == said else f"{said} ({english})")
        if unread:  # something said freely that no one has read: a person must look at it
            return finish(db, call, "unclear", [{"finding": None, "label": "Free answer that could not be read",
                                                 "evidence": f'"{said}" (no English translation available)'}], user)
    _advance(db, call)
    return call


def finish(db: Session, call: Call, outcome: str, flags: list[dict] | None = None, user: User | None = None) -> Call:
    """End the call, say the closing line, and act on the outcome. A danger sign or an unclear danger-sign answer pages
    a person; a completed call marks the follow-up as contacted but never closes it."""
    closing = {"danger_sign": "end_danger", "unclear": "end_unclear", "message_left": "thanks"}.get(outcome)
    if outcome == "completed":
        closing = "end_visit" if (call.notes or {}).get("can_come") is False else "end_come"
    if closing:
        _say(db, call, closing)
    call.status, call.outcome, call.ended_at = "ended", outcome, now()
    if flags:
        call.red_flags = flags
    r = db.get(Reminder, call.reminder_id)
    p = db.get(Patient, call.patient_id)
    who = "Reminder call (agent)" if call.operator == "agent" else f"Reminder call by {user.name} ({user.role})" if user else "Reminder call"
    labels = ", ".join(f["label"].lower() for f in flags or [])
    summary = {
        "completed": "No danger sign reported. An automated call is weak evidence: the visit is still needed.",
        "danger_sign": f"Danger sign reported: {labels}. Call ended; a person was paged.",
        "unclear": "No clear answer to a danger-sign question. Call ended; a person must call.",
        "message_left": "Spoke to someone else; asked them to pass on the visit date. Nothing about health was said.",
        "no_answer": "No answer.",
        "hung_up": "The call was cut before the questions were finished.",
    }[outcome]
    if (call.notes or {}).get("flags"):
        summary += " Noted: " + "; ".join(call.notes["flags"]) + "."
    r.attempts = [*(r.attempts or []), {"at": now().isoformat(), "by": who, "outcome": "call", "call_outcome": outcome, "call_id": call.id, "note": summary}]
    if outcome in ("danger_sign", "unclear"):
        r.status = "flagged"
        title = (f"Danger sign on a reminder call: {p.name} ({labels}). Call back now." if outcome == "danger_sign"
                 else f"Reminder call unclear: {p.name}. A person must call.")
        a, _ = al._raise(db, call.facility_id, "call_escalation", r.id, "medical_officer", title, {
            "reminder_id": r.id, "call_id": call.id, "patient_code": p.code, "programme": call.programme, "reason": outcome,
            "findings": flags or [], "phone": p.phone, "phone_belongs_to": r.phone_belongs_to,
            "action": "Phone back now. The agent said nothing about what the sign may mean; the person who calls decides what to do."},
            assigned_to=r.assigned_to)
        call.alert_id = a.id
    elif outcome == "completed":
        r.status = "contacted"
        m = al._open_alert(db, r.facility_id, "missed_visit", r.id)
        if m and m.status == "open":
            m.status, m.acknowledged_by, m.acknowledged_at, m.updated_at = "acknowledged", who, now(), now()
    elif outcome == "no_answer" and r.status == "missed":
        r.status = "call_due"
    audit.record(db, user, "UPDATE", "call", call.id, f"Reminder call ended: {outcome.replace('_', ' ')}"
                 + (f" ({labels}); alert raised" if outcome == "danger_sign" else "; alert raised" if outcome == "unclear" else ""), p.code, call.facility_id)
    return call


def hang_up(db: Session, call: Call, user: User, outcome: str) -> Call:
    if call.status != "active":
        raise CallRefused(409, "This call has ended")
    if outcome not in ENDED_BY_CALLER:
        raise CallRefused(422, "Unknown outcome")
    return finish(db, call, outcome, user=user)
