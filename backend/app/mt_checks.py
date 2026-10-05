"""Checks around machine translation of a patient's words (B2). No model here, so all of it is testable without one.

Before translation — `prepare` rewrites only what the translator is given; the patient's own words are stored and
shown unchanged, and the rules read those:
* number words before a time unit or an age become digits ("ଛପନ ବର୍ଷ" → "56 ବର୍ଷ", "दो दिन" → "2 दिन"): IndicTrans2
  rendered ଛପନ (56) as "sixty-six" but translates 56 correctly. Hindi and Odia, 1–100.
* spoken Odia words this model mistranslates every time, rewritten to the standard word it gets right
  (measured 5 Oct on real kiosk recordings): ଜର → ଜ୍ୱର (fever, otherwise dropped); ଝାଡ଼ା as loose stools → ଅତିସାର
  (otherwise "sweating"); ଝାଡ଼ାରେ → ମଳରେ ("in the stool"); ଝାଡ଼ା negated → "ମଳ ବାହାରୁ ନାହିଁ" (no stool passed).

After translation — `unsure` compares the best translation with the model's other near-equal candidates (the beam
search already produces them). If they disagree on a number or on a symptom the rules use, the translation is
flagged for the reviewer with both readings. This needs no word list, so it works for all 22 languages.
"""

import re
import unicodedata

from .triage.findings import FINDINGS, _loose, scan_text

# ---------------------------------------------------------------- number words (1–100)

HI_NUMBERS = (
    "एक दो तीन चार पांच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस "
    "इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस "
    "इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ "
    "इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी "
    "इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे सौ"
).split()
OR_NUMBERS = (
    "ଏକ ଦୁଇ ତିନି ଚାରି ପାଞ୍ଚ ଛଅ ସାତ ଆଠ ନଅ ଦଶ ଏଗାର ବାର ତେର ଚଉଦ ପନ୍ଦର ଷୋହଳ ସତର ଅଠର ଉଣେଇଶି କୋଡ଼ିଏ "
    "ଏକୋଇଶି ବାଇଶି ତେଇଶି ଚବିଶି ପଚିଶି ଛବିଶି ସତାଇଶି ଅଠାଇଶି ଅଣତିରିଶି ତିରିଶି ଏକତିରିଶି ବତିଶି ତେତିଶି ଚଉତିରିଶି ପଞ୍ଚତିରିଶି ଛତିଶି ସଇଁତିରିଶି ଅଠତିରିଶି ଅଣଚାଳିଶି ଚାଳିଶି "
    "ଏକଚାଳିଶି ବୟାଳିଶି ତେୟାଳିଶି ଚଉରାଳିଶି ପଞ୍ଚଚାଳିଶି ଛୟାଳିଶି ସତଚାଳିଶି ଅଠଚାଳିଶି ଅଣଚାଶ ପଚାଶ ଏକାବନ ବାଉନ ତେପନ ଚଉବନ ପଞ୍ଚାବନ ଛପନ ସତାବନ ଅଠାବନ ଅଣଷଠି ଷାଠିଏ "
    "ଏକଷଠି ବାଷଠି ତେଷଠି ଚଉଷଠି ପଞ୍ଚଷଠି ଛଅଷଠି ସତଷଠି ଅଠଷଠି ଅଣସ୍ତରି ସତୁରି ଏକସ୍ତରି ବାସ୍ତରି ତେସ୍ତରି ଚଉସ୍ତରି ପଞ୍ଚସ୍ତରି ଛସ୍ତରି ସତସ୍ତରି ଅଠସ୍ତରି ଅଣାଅଶୀ ଅଶୀ "
    "ଏକାଅଶୀ ବୟାଅଶୀ ତେୟାଅଶୀ ଚଉରାଅଶୀ ପଞ୍ଚାଅଶୀ ଛୟାଅଶୀ ସତାଅଶୀ ଅଠାଅଶୀ ଅଣାନବେ ନବେ ଏକାନବେ ବୟାନବେ ତେୟାନବେ ଚଉରାନବେ ପଞ୍ଚାନବେ ଛୟାନବେ ସତାନବେ ଅଠାନବେ ଅନେଶତ ଶହେ"
).split()
NUMBER_WORDS = {
    "hi": {**{_loose(w): i + 1 for i, w in enumerate(HI_NUMBERS)}, _loose("छः"): 6},
    "or": {**{_loose(w): i + 1 for i, w in enumerate(OR_NUMBERS)}, _loose("ଛ"): 6, _loose("ଷାଠିଏ"): 60, _loose("ସତୁରୀ"): 70},
}
# A number word is turned into digits only right before one of these, so "दवा दो" (give the medicine) and
# "ଦୁଇ ବାର" stay words unless they really are counts of time, age or times-per-day.
UNITS = {
    "hi": [_loose(u) for u in ("दिन", "हफ्ते", "हफ़्ते", "हफ्ता", "सप्ताह", "महीने", "महीना", "साल", "वर्ष", "बरस", "घंटे", "घंटा", "मिनट", "बार", "दफा")],
    "or": [_loose(u) for u in ("ଦିନ", "ସପ୍ତାହ", "ହପ୍ତା", "ମାସ", "ବର୍ଷ", "ବରଷ", "ଘଣ୍ଟା", "ମିନିଟ", "ଥର", "ଦିନରୁ", "ବର୍ଷର")],
}


def _digits(text: str, lang: str) -> tuple[str, list[dict]]:
    words, units = NUMBER_WORDS.get(lang), UNITS.get(lang)
    if not words:
        return text, []
    toks = text.split(" ")
    changes = []
    for i, tok in enumerate(toks[:-1]):
        n = words.get(_loose(tok))
        if n and any(_loose(toks[i + 1]).startswith(u) for u in units):
            changes.append({"from": tok, "to": str(n), "why": "number word written as digits"})
            toks[i] = str(n)
    return " ".join(toks), changes


# ---------------------------------------------------------------- spoken Odia the translator gets wrong

_NUKTA = "଼?"
_JHADA = f"ଝାଡ{_NUKTA}ା"
_NEG = r"(?:ହୋଇନି|ହେଉନି|ହେଉ ନାହିଁ|ହୋଇ ନାହିଁ|ହଉନି|ନାହିଁ)"
REWRITES = {
    "or": [
        (re.compile(r"(?<!\S)ଜର(?=\s|$|[,.?!।])"), "ଜ୍ୱର", "spoken spelling of fever"),
        (re.compile(rf"{_JHADA}ବାନ୍ତି"), "ଅତିସାର ଓ ବାନ୍ତି", "loose stools and vomiting"),
        (re.compile(rf"{_JHADA}ରେ"), "ମଳରେ", "in the stool"),
        (re.compile(rf"{_JHADA}(\s+(?:ବି\s+)?){_NEG}"), r"ମଳ\1ବାହାରୁ ନାହିଁ", "no stool passed"),
        (re.compile(rf"(?<!\S){_JHADA}(?=\s|$|[,.?!।])"), "ଅତିସାର", "loose stools"),
    ],
}


def prepare(text: str, lang: str) -> tuple[str, list[dict]]:
    """What the translator is given for `text`, and each change made (shown to the reviewer)."""
    out = unicodedata.normalize("NFC", text or "")
    out, changes = _digits(out, lang)
    for rx, repl, why in REWRITES.get(lang, []):
        for m in list(rx.finditer(out)):
            changes.append({"from": m.group(0).strip(), "to": rx.sub(repl, m.group(0)).strip(), "why": why})
        out = rx.sub(repl, out)
    return out, changes


# ---------------------------------------------------------------- after translation

_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_EN_NUM = re.compile(r"\b(\d+(?:\.\d+)?)\b|\b(" + "|".join(_TENS) + r")(?:[- ](" + "|".join(_ONES[1:10]) + r"))?\b|\b(" + "|".join(_ONES) + r"|hundred)\b", re.I)


def english_numbers(text: str) -> list[float]:
    """Numbers in English text, written as digits or words ("sixty-six" → 66), in order."""
    out = []
    for m in _EN_NUM.finditer(text or ""):
        if m.group(1):
            out.append(float(m.group(1)))
        elif m.group(2):
            out.append(_TENS[m.group(2).lower()] + (_ONES.index(m.group(3).lower()) if m.group(3) else 0))
        else:
            w = m.group(4).lower()
            out.append(100 if w == "hundred" else _ONES.index(w))
    return out


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else str(n)


MARGIN = 0.1  # candidates within this of the best average log-probability count as "near-equal"


def unsure(source: str, best: str, alternatives: list[tuple[str, float]]) -> list[str]:
    """Where the translation is not settled: digits in the source missing from the English, and numbers or symptoms
    on which the near-equal candidates disagree with the best one. Plain-language notes for the reviewer."""
    notes = []
    best_nums = english_numbers(best)
    for d in re.findall(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", source or "")):
        if float(d) not in best_nums:
            notes.append(f"the patient's words have {d}, the translation does not")
    if not alternatives:
        return notes
    top = alternatives[0][1]
    near = [t for t, s in alternatives[1:] if s >= top - MARGIN]
    best_found = {f for f, x in scan_text(best, "").items() if x.value is True}
    seen_nums, seen_found = set(), set()
    for alt in near:
        nums = english_numbers(alt)
        if sorted(nums) != sorted(best_nums):
            key = tuple(sorted(set(nums) - set(best_nums)))
            if key and key not in seen_nums:
                seen_nums.add(key)
                notes.append(f"number unclear: {', '.join(_fmt(n) for n in sorted(set(best_nums) - set(nums))) or '—'} or {', '.join(_fmt(n) for n in key)}")
        found = {f for f, x in scan_text(alt, "").items() if x.value is True}
        for f in sorted((found ^ best_found) - {"pain"} - seen_found):
            seen_found.add(f)
            notes.append(f"{'may also mean' if f in found else 'unsure of'}: {FINDINGS[f][0].lower()}")
    return notes
