"""When did it start? Onset with a certainty label (B4).

Every onset shown to the reviewer carries one label and the patient's raw words:

* STATED   — an explicit time from the patient: "3 days", "since yesterday", "ଚାରି ଦିନ ହେଲା", or a tapped duration.
* INFERRED — worked out from something else (a dated record), never from a guess.
* VAGUE    — a time the patient could not pin down: "few days", "for a long time", "since Diwali", "कई दिन से".
             A festival or season is looked up in the facility's regional calendar (app/regions.py) and the
             approximate date or window is shown beside the patient's words; it stays VAGUE and `days` stays empty,
             so the rules never use it.
* UNKNOWN  — nothing said.

When the patient's words and the tapped answer disagree ("3 days" said, "1–4 weeks" tapped), the note asks staff to
check instead of picking one. Deterministic phrase lists, English, Hindi (Devanagari and romanised) and Odia.
"""

import re
from datetime import date

from .. import regions
from ..privacy import _norm as ascii_digits

NUM = {
    "a": 1, "an": 1, "one": 1, "two": 2, "couple of": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "saat": 7, "aath": 8, "das": 10,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ଏକ": 1, "ଦୁଇ": 2, "ତିନି": 3, "ଚାରି": 4, "ପାଞ୍ଚ": 5, "ଛଅ": 6, "ସାତ": 7, "ଆଠ": 8, "ନଅ": 9, "ଦଶ": 10,
}
UNIT_DAYS = {
    "hour": 1 / 24, "hours": 1 / 24, "hrs": 1 / 24, "day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30, "year": 365, "years": 365,
    "ghante": 1 / 24, "din": 1, "hafte": 7, "hafta": 7, "mahine": 30, "mahina": 30, "saal": 365,
    "घंटे": 1 / 24, "घंटा": 1 / 24, "दिन": 1, "दिनों": 1, "हफ्ते": 7, "हफ़्ते": 7, "हफ्ता": 7, "सप्ताह": 7, "महीने": 30, "महीना": 30, "साल": 365,
    "ଘଣ୍ଟା": 1 / 24, "ଦିନ": 1, "ସପ୍ତାହ": 7, "ମାସ": 30, "ବର୍ଷ": 365,
}
_num = "|".join(sorted(map(re.escape, NUM), key=len, reverse=True))
_unit = "|".join(sorted(map(re.escape, UNIT_DAYS), key=len, reverse=True))
EXPLICIT = re.compile(rf"(?<![\w])(\d+(?:\.\d+)?|{_num})\s*({_unit})(?![a-z])", re.I)
RELATIVE = [  # (pattern, days)
    (r"\b(since |from )?(this morning|today morning|morning)\b|आज सुबह|ଆଜି ସକାଳ", 0),
    (r"\btoday\b|\baaj\b|आज से|ଆଜିଠାରୁ|ଆଜିଠୁ", 0),
    (r"\b(since |from )?(last night|yesterday night)\b|कल रात|ଗତ ରାତି|କାଲି ରାତି", 1),
    (r"\b(since |from )?yesterday\b|\bkal se\b|कल से|ଗତକାଲି|କାଲିଠାରୁ|କାଲିଠୁ", 1),
    (r"\b(since |from )?last week\b|पिछले हफ्ते|ଗତ ସପ୍ତାହ", 7),
    (r"\b(since |from )?last month\b|पिछले महीने|ଗତ ମାସ", 30),
]
VAGUE = re.compile(
    r"\b(few|some|several|many) (days|weeks|months)\b|\ba (long )?while\b|\blong time\b|\bfor ages\b|\bever since\b|\bsince childhood\b|\bon and off\b"
    r"|\bsince (the |my |her |his )?(marriage|wedding|delivery|puja|pooja|festival|festivals|tyohar)\b"
    r"|\b(kuch|kai|bahut|kaafi) (din|samay|time)\b"
    r"|कुछ दिन|कई दिन|काफी समय|काफ़ी समय|बहुत दिन|बहुत समय|शादी से|त्योहार से|त्यौहार से|पूजा से"
    r"|କିଛି ଦିନ|ଅନେକ ଦିନ|ବହୁତ ଦିନ|ବହୁ ଦିନ|ବହୁତ ସମୟ|ପର୍ବ ପରଠାରୁ|ପୂଜା ପରଠାରୁ|ପୂଜାଠାରୁ",
    re.I,
)
# Festivals and seasons ("since Diwali", "ରଜଠାରୁ", "after the rains") come from the regional calendar (F5).

# Tapped answers (kiosk catalogue) → day range
TAPPED = {"today": (0, 0), "1-2 days": (1, 2), "3-7 days": (3, 7), "1-4 weeks": (7, 28), "more than a month": (30, 10_000)}


def _days(phrase_num: str, unit: str) -> float:
    n = float(phrase_num) if re.fullmatch(r"\d+(\.\d+)?", phrase_num) else NUM[phrase_num.lower()]
    return n * UNIT_DAYS[unit.lower() if unit.isascii() else unit]


def _when(days: float) -> str:
    if days < 1:
        return "Today"
    if days < 14:
        return f"{round(days)} day{'s' if round(days) != 1 else ''} ago"
    if days < 28:
        return f"{round(days / 7)} weeks ago"
    months = round(days / 30)
    return f"{months} month{'s' if months != 1 else ''} ago"


def _is_onset(t: str, m: re.Match) -> bool:
    """Not an onset: "3 times a day", "every 4 hours", "32 weeks pregnant", "2 years old", "aged 40 years"."""
    before, after = t[: m.start()].lower()[-12:], t[m.end():].lower()[:14]
    if re.search(r"(times|twice|once|thrice|per|every|aged?|baar)\s*$", before):
        return False
    return not re.match(r"\s*(pregnan|of pregnancy|gestation|old\b|of age|ki umar|की उम्र|ଗର୍ଭ)", after)


def _texts(intake: dict) -> list[str]:
    out = [intake.get("chief_complaint") or ""]
    for s in intake.get("symptoms") or []:
        out += [s.get("original_text") or "", s.get("text") or ""]
    out += [a.get("answer") or "" for a in intake.get("answers") or [] if a.get("qid") != "dur"]
    return [ascii_digits(t) for t in out if t]


def onset(intake: dict, cal: "regions.Calendar | None" = None, on: date | None = None) -> dict:
    """{'when', 'certainty', 'raw', 'days', 'check'} for the current complaint. `check` is set when sources disagree.

    `cal` is the facility's regional calendar and `on` the visit date; with both, a festival or season onset also
    carries `approx` (the date or window it points to)."""
    cal = cal or regions.for_facility(None)
    said = vague = dated = None
    for t in _texts(intake):
        if not said and (m := next((x for x in EXPLICIT.finditer(t) if _is_onset(t, x)), None)):
            said = (m.group(0), _days(m.group(1), m.group(2)))
        if not said:
            for pat, d in RELATIVE:
                if m := re.search(pat, t, re.I):
                    said = (m.group(0).strip(), d)
                    break
        if not vague and (hit := cal.match(t)):
            vague, dated = hit[0], hit
        if not vague and (m := VAGUE.search(t)):
            vague = m.group(0)
    tapped = intake.get("duration") or next((a.get("answer") for a in intake.get("answers") or [] if a.get("qid") == "dur"), None)
    rng = TAPPED.get((tapped or "").strip().lower())

    if said:
        raw, days = said
        check = None
        if rng and not (rng[0] - 1 <= days <= rng[1] + 1):
            check = f'Patient said "{raw}" but tapped "{tapped}" — ask again'
        return {"when": _when(days), "certainty": "STATED", "raw": raw, "days": round(days, 4), "check": check}
    if tapped:
        out = {"when": "Today" if tapped.lower() == "today" else f"{tapped} ago", "certainty": "STATED", "raw": f"tapped: {tapped}", "days": None, "check": None}
        if vague:
            out["raw"] += f'; also said "{vague}"'
        return out
    if vague:
        out = {"when": "Not clear", "certainty": "VAGUE", "raw": vague, "days": None, "check": f'Onset given only as "{vague}" — ask for an approximate date'}
        if dated and on:
            out["approx"] = cal.resolve(dated[1], dated[2], on)
            out["when"], out["check"] = cal.describe(vague, out["approx"])
        return out
    return {"when": "Not stated", "certainty": "UNKNOWN", "raw": None, "days": None, "check": None}
