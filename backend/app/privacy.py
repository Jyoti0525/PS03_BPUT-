"""Anonymisation of free text before it is stored (G3).

Patients and health workers type or speak identifiers into free-text answers ("my name is Sita, call 98765 43210").
Those words would otherwise sit in the intake, the note, exports and every later model input. `scrub()` replaces:

* phone numbers (Indian mobile, +91 / 0 prefixes, landlines with an STD code)  → [PHONE]
* Aadhaar numbers (12 digits)                                                   → [AADHAAR]
* ABHA numbers (14 digits) and ABHA addresses (name@abdm / @sbx)                → [ABHA]
* e-mail addresses                                                              → [EMAIL]
* names: the patient's and the proxy's registered names, and whatever follows
  "my name is" in English, Hindi, Odia and Kannada                              → [NAME]

Digits in Indic scripts (୯୮୭… / ९८७…) are matched like ASCII digits. Clinical numbers are left alone: a value needs
10+ digits in phone-like groups before it is treated as an identifier, so "BP 150 95" or "98 97 96" never match.

Limits (stated, not hidden): names said without an introduction phrase and not on the registration are not
found, and numbers spoken as words ("nine eight seven…") are not recognised. The reviewer sees which kinds were
removed (note flag PII-REDACTED) and the audit log records counts only, never the removed values.
"""

import re
import unicodedata

PLACEHOLDER = {"name": "[NAME]", "phone": "[PHONE]", "aadhaar": "[AADHAAR]", "abha": "[ABHA]", "email": "[EMAIL]"}

# Indic decimal digits → ASCII, one character for one character so spans stay aligned with the original text.
_DIGITS = {}
for zero in (0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x1C50, 0x06F0, 0x0660):
    for i in range(10):
        _DIGITS[zero + i] = str(i)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ABHA_ADDRESS = re.compile(r"[\w.]{3,}@(?:abdm|sbx)\b", re.I)
# A run of digit groups joined by single spaces or hyphens: first group 2+ digits, every later group 3+ digits,
# so lists of small clinical values ("120 80", "98 97 96") never join into one long number.
_NUMBER = re.compile(r"(?<![\w.])(\+?\d{2,}(?:[ -]\d{3,})*)(?!\w|\.\d)")

# Words after which a name follows. Only the 1–2 words directly after are taken, stopping at a verb/particle.
_NAME_INTRO = re.compile(
    r"(?:\bmy name is|\bmy name's|\bname is|\bmera naam|\bmeraa naam|मेरा नाम|मेरी नाम|मोरा नाम|हमार नाम|हमारा नाम|"
    r"ମୋ ନାମ|ମୋର ନାମ|ମୋ ନାଁ|ମୋର ନାଁ|ମୋ ନାଆଁ|ମୋର ନାଆଁ|ನನ್ನ ಹೆಸರು|ನನ್ನ ಹೆಸರ್)\s*[:\-]?\s*",
    re.I,
)
_NAME_STOP = {
    "is", "and", "i", "am", "my", "me", "from", "age", "aged", "years", "year", "have", "has", "with", "the", "a", "an",
    "है", "हैं", "हूँ", "हूं", "और", "मैं", "मेरी", "मेरा", "मुझे", "मुझको", "मेरे", "उम्र", "साल",
    "ଅଟେ", "ଅଛି", "ଓ", "ଏବଂ", "ମୁଁ", "ମୋର", "ମୋ", "ମୋତେ", "ବୟସ", "ବର୍ଷ",
    "ಆಗಿದೆ", "ಮತ್ತು", "ನಾನು", "ನನ್ನ", "ನನಗೆ", "ವಯಸ್ಸು", "ವರ್ಷ",
}
# Registered-name words that are also everyday clinical words are not scrubbed on their own.
_COMMON_WORDS = {"asha", "anm", "devi", "kumar", "kumari", "bai", "ben", "bhai", "das", "sri", "shri", "smt", "mr", "mrs", "md", "late"}


def _clinical(word: str) -> bool:
    """True if the triage lexicon reads this word as a finding: such a word is never removed as a name."""
    from .triage.findings import scan_text

    return bool(scan_text(word, "name-check"))


def _norm(text: str) -> str:
    return text.translate(_DIGITS)


def _classify(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    n = len(digits)
    groups = [len(g) for g in re.split(r"[ -]", raw.lstrip("+"))]
    if n == 14:
        return "abha"
    if n == 12:
        if raw.startswith("+") or (digits.startswith("91") and digits[2] in "6789" and groups != [4, 4, 4]):
            return "phone"
        return "aadhaar"
    if n == 10 and digits[0] in "6789":
        return "phone"
    if n == 11 and digits[0] == "0":  # 0 + mobile, or STD code + landline
        return "phone"
    if n == 13 and digits.startswith("910"):
        return "phone"
    return None


def _name_terms(names: list[str]) -> list[str]:
    terms = set()
    for full in names:
        full = " ".join((full or "").split())
        if len(full) < 3:
            continue
        terms.add(full)
        for w in re.split(r"[\s.]+", full):
            if len(w) >= 3 and w.lower() not in _COMMON_WORDS and not _clinical(w):
                terms.add(w)
    return sorted(terms, key=len, reverse=True)  # longest first: "Sita Devi" before "Sita"


def _is_word(c: str) -> bool:
    return c.isalnum() or unicodedata.category(c).startswith("M")  # Indic vowel signs are marks, not letters


def scrub(text: str | None, names: list[str] | None = None, *, numbers_only: bool = False) -> tuple[str | None, dict[str, int]]:
    """Return (text with identifiers replaced, {kind: count}). `names` are known names to remove (patient, proxy)."""
    if not text:
        return text, {}
    found: dict[str, int] = {}
    spans: list[tuple[int, int, str]] = []
    norm = _norm(text)

    def add(a: int, b: int, kind: str) -> None:
        if any(a < y and x < b for x, y, _ in spans):
            return
        spans.append((a, b, kind))
        found[kind] = found.get(kind, 0) + 1

    for m in _EMAIL.finditer(norm):
        add(m.start(), m.end(), "abha" if _ABHA_ADDRESS.fullmatch(m.group()) else "email")
    for m in _ABHA_ADDRESS.finditer(norm):
        add(m.start(), m.end(), "abha")
    for m in _NUMBER.finditer(norm):
        if kind := _classify(m.group(1)):
            add(m.start(1), m.end(1), kind)

    if not numbers_only:
        for m in _NAME_INTRO.finditer(norm):
            i, taken, end, prev = m.end(), 0, None, 0
            for w in re.finditer(r"[^\s,.;:!?।]+", norm[i:]):
                if norm[i + prev : i + w.start()].strip(" "):  # punctuation ends the name
                    break
                prev = w.end()
                if w.group().lower() in _NAME_STOP or taken == 2 or w.group().startswith("[") or _clinical(w.group()):
                    break
                end, taken = i + w.end(), taken + 1
            if end:
                add(m.end(), end, "name")
        low = norm.lower()
        for term in _name_terms(names or []):
            t = term.lower()
            start = 0
            while (k := low.find(t, start)) != -1:
                b = k + len(t)
                if (k == 0 or not _is_word(low[k - 1])) and (b == len(low) or not _is_word(low[b])):
                    add(k, b, "name")
                start = b

    if not spans:
        return text, {}
    out, last = [], 0
    for a, b, kind in sorted(spans):
        out.append(text[last:a])
        out.append(PLACEHOLDER[kind])
        last = b
    out.append(text[last:])
    return "".join(out), found


def _merge(total: dict[str, int], part: dict[str, int]) -> None:
    for k, v in part.items():
        total[k] = total.get(k, 0) + v


def anonymise_intake(intake: dict, names: list[str]) -> tuple[dict, dict[str, int]]:
    """Scrub every patient-provided free-text field of an intake (as a JSON dict). Returns (intake, counts)."""
    out = dict(intake)
    total: dict[str, int] = {}

    def s(v):
        new, c = scrub(v, names)
        _merge(total, c)
        return new

    for key in ("chief_complaint", "duration"):
        if isinstance(out.get(key), str):
            out[key] = s(out[key])
    symptoms = []
    for x in out.get("symptoms") or []:
        original = s(x.get("original_text"))
        same = x.get("text") == x.get("original_text")  # not yet translated: one string, counted once
        symptoms.append({**x, "original_text": original, "text": original if same else s(x.get("text"))})
    out["symptoms"] = symptoms
    out["answers"] = [{**a, "answer": s(a.get("answer"))} for a in out.get("answers") or []]
    out["selected_symptoms"] = [s(x) for x in out.get("selected_symptoms") or []]
    if isinstance(out.get("chronic"), dict) and out["chronic"].get("current_medicines"):
        out["chronic"] = {**out["chronic"], "current_medicines": s(out["chronic"]["current_medicines"])}
    return out, total


def describe(counts: dict[str, int]) -> str:
    """'1 name, 2 phone numbers' — for the reviewer flag and the audit log (never the values)."""
    label = {"name": ("name", "names"), "phone": ("phone number", "phone numbers"), "aadhaar": ("Aadhaar number", "Aadhaar numbers"),
             "abha": ("ABHA ID", "ABHA IDs"), "email": ("e-mail address", "e-mail addresses")}
    return ", ".join(f"{n} {label[k][n != 1]}" for k, n in sorted(counts.items()) if n)


# ---------------------------------------------------------------- de-identified cohort view

K_MIN = 5  # a count of 1–4 is shown as "fewer than 5" so a small group cannot be singled out
AGE_BANDS = [(0, 4, "0–4"), (5, 13, "5–13"), (14, 17, "14–17"), (18, 39, "18–39"), (40, 59, "40–59"), (60, 200, "60+")]
REMOVED_FIELDS = ["name", "patient ID", "phone", "village", "exact age", "exact date and time", "free text", "token"]


def age_band(age: int) -> str:
    return next(label for lo, hi, label in AGE_BANDS if lo <= age <= hi)


def cohort(rows: list[dict], days: int) -> dict:
    """Aggregate encounters into counts that identify nobody.

    `rows` hold only what the view may use: week, age, sex, category, urgency and the ids of findings present.
    Every count below K_MIN is suppressed (None) — zero is shown, since "nobody" reveals no one."""
    from collections import Counter

    from .triage.findings import FINDINGS

    suppressed = 0

    def table(counter: Counter, keys: list[str]) -> list[dict]:
        nonlocal suppressed
        out = []
        for k in keys:
            n = counter.get(k, 0)
            hide = 0 < n < K_MIN
            suppressed += hide
            out.append({"key": k, "count": None if hide else n})
        return out

    bands = [b for _, _, b in AGE_BANDS]
    weeks = sorted({r["week"] for r in rows})
    finding_counts = Counter(f for r in rows for f in set(r["findings"]))
    top = [f for f, _ in finding_counts.most_common(15)]
    cross = Counter((r["urgency"], age_band(r["age"])) for r in rows)
    return {
        "days": days,
        "k_min": K_MIN,
        "total": len(rows) if len(rows) >= K_MIN or not rows else None,
        "by_week": table(Counter(r["week"] for r in rows), weeks),
        "by_age_band": table(Counter(age_band(r["age"]) for r in rows), bands),
        "by_sex": table(Counter(r["sex"] for r in rows), ["F", "M", "O"]),
        "by_category": table(Counter(r["category"] for r in rows), ["normal", "maternal", "chronic"]),
        "by_urgency": table(Counter(r["urgency"] for r in rows), ["red", "yellow", "green"]),
        "urgency_by_age_band": [{"urgency": u, "cells": table(Counter({b: cross.get((u, b), 0) for b in bands}), bands)} for u in ("red", "yellow", "green")],
        "findings": [{**c, "label": FINDINGS.get(c["key"], (c["key"],))[0]} for c in table(finding_counts, top)],
        "suppressed_cells": suppressed,
        "removed_fields": REMOVED_FIELDS,
    }
