"""B9: two speech engines on the same recording. The offline IndicConformer writes the transcript; Sarvam Saaras
(online) hears the same audio. Where they disagree on a number, on a symptom, or on most of the words, the note
says so and shows both, because one of them misheard the patient and nobody can tell which without asking.

Both transcripts are first brought to one spelling (the lexicon's loose form: ଜ୍ୱର/ଜର, ी/ि …), punctuation dropped,
native digits and Hindi/Odia number words turned into digits, so a spelling or "ଦୁଇ"/"2" difference is not a
disagreement. What is left is compared three ways:
* numbers: a different count, age or reading is always a disagreement;
* symptoms: the intake lexicon (English, Hindi, Odia) read on each; a symptom one engine heard and the other did not,
  or heard as denied, is always a disagreement;
* overall: character agreement below AGREEMENT_MIN (measured on FLEURS, docs/EVALUATION.md) is a disagreement.
"""

import re
import unicodedata

from .mt_checks import NUMBER_WORDS, UNITS
from .triage.findings import FINDINGS, _loose, scan_text

# Below this share of matching characters the two transcripts are treated as different sentences. Set from the
# engine-vs-engine spread on FLEURS Odia (docs/EVALUATION.md, B9): clean read speech stays above it.
AGREEMENT_MIN = 0.80

_PUNCT = re.compile(r"[।॥,!?;:'\"()\[\]{}\-–—“”‘’|/]|(?<!\d)\.|\.(?!\d)")
_NATIVE_DIGITS = str.maketrans("०१२३४५६७८९୦୧୨୩୪୫୬୭୮୯", "01234567890123456789")
_NUM = re.compile(r"\d+(?:\.\d+)?")
# Spoken numbers as speech recognition writes them: "ଶହେ ଆଠ" (108), "ଉଣେଇଶ ହଜାର ପାଞ୍ଚଶହ" (19500), "ଅଠରଟି" (18 + the
# counting suffix). One engine writes words, the other digits; both become digits here.
_SCALES = {"hi": {"सौ": 100, "हजार": 1000, "हज़ार": 1000, "लाख": 100000},
           "or": {"ଶହ": 100, "ଶହେ": 100, "ହଜାର": 1000, "ଲକ୍ଷ": 100000}}
_SUFFIXES = {"or": ("ଟି", "ଟା", "ଜଣ", "ରେ", "ରୁ", "ର", "ଥର"), "hi": ("वां", "वें", "वीं")}


def _number_tables(lang: str) -> tuple[dict, dict, tuple]:
    words = dict(NUMBER_WORDS.get(lang, {}))
    for w, n in list(words.items()):  # spoken spellings drop the final vowel sign: ଉଣେଇଶି / ଉଣେଇଶ, କୋଡ଼ିଏ / କୋଡ଼ି
        if len(w) > 2 and unicodedata.category(w[-1]) in ("Mn", "Mc"):
            words.setdefault(w[:-1], n)
    scales = {_loose(k): v for k, v in _SCALES.get(lang, {}).items()}
    return words, scales, tuple(_loose(s) for s in _SUFFIXES.get(lang, ()))


def _number_parts(tok: str, words: dict, scales: dict, suffixes: tuple) -> list | None:
    """A loose token as number parts ([5, ('scale', 100)] for ପାଞ୍ଚଶହ), or None if it is not a number."""
    for suf in ("", *suffixes):
        t = tok[: -len(suf)] if suf and tok.endswith(suf) else (tok if not suf else None)
        if not t:
            continue
        if t in scales:  # before the number words: सौ / ଶହେ alone is "hundred" (एक सौ चालीस = 140)
            return [("scale", scales[t])]
        if t in words:
            return [words[t]]
        if re.fullmatch(r"\d+(?:\.\d+)?", t):  # digits with a counting suffix: 14ଟି
            return [("digits", t)]
        for s, v in scales.items():  # a number word joined to its scale: ପାଞ୍ଚଶହ
            if t.endswith(s) and t[: -len(s)] in words:
                return [words[t[: -len(s)]], ("scale", v)]
    for suf in ("", *suffixes):  # nothing exact: a number word with a vowel sign slipped (ସତୋରୀ for ସତୁରି, 70)
        t = tok[: -len(suf)] if suf and tok.endswith(suf) else (tok if not suf else None)
        if t and (n := _near_number(t, words)) is not None:
            return [n]
    return None


def _skeleton(word: str) -> str:
    return "".join(c for c in word if unicodedata.category(c) not in ("Mn", "Mc"))


def _near_number(t: str, words: dict) -> int | None:
    """The number a long word means when its consonants are a number word's and one vowel sign differs (ଏକଚାଳସ, 41;
    ଊଣାଇଶ, 19; ସତୋରୀ: ସତୁରି 70, not ସତର 17). Two slips are not allowed: ବିସ୍ତାର ("expanse") is not ବାସ୍ତରି (72)."""
    if len(t) < 5:
        return None
    sk = _skeleton(t)
    near = sorted((_edits(t, w), n) for w, n in words.items() if _skeleton(w) == sk)
    if not near or near[0][0] > 1:
        return None
    best = {n for d, n in near if d == near[0][0]}
    return best.pop() if len(best) == 1 else None


def _spoken_numbers(tokens: list[str], lang: str) -> list[str]:
    words, scales, suffixes = _number_tables(lang)
    out, total, cur, open_ = [], 0, 0, False

    def close():
        nonlocal total, cur, open_
        if open_:
            out.append(str(total + cur))
        total, cur, open_ = 0, 0, False

    for tok in tokens:
        parts = _number_parts(tok, words, scales, suffixes) if words else None
        if parts is None:
            close()
            out.append(tok)
            continue
        if isinstance(parts[0], tuple) and parts[0][0] == "digits":
            close()
            out.append(parts[0][1])
            continue
        for p in parts:
            if isinstance(p, tuple):
                if p[1] >= 1000:
                    total, cur = total + (cur or 1) * p[1], 0
                else:
                    cur = (cur or 1) * p[1]
            else:
                if open_ and (cur % 100 or (cur == 0 and total == 0)):  # "ଦୁଇ ତିନି" is two numbers, "ଶହେ ଆଠ" one
                    close()
                cur += p
            open_ = True
    close()
    return out


def _split_number_unit(tok: str, lang: str) -> list[str]:
    """ଚାରିଦିନ → ଚାରି ଦିନ: a number word written joined to its unit, as one engine does and the other does not."""
    words = NUMBER_WORDS.get(lang, {})
    for unit in UNITS.get(lang, []):
        i = tok.find(unit, 1)
        if i > 0 and tok[:i] in words:
            return [tok[:i], tok[i:]]
    return [tok]


def normalise(text: str, lang: str) -> str:
    text = unicodedata.normalize("NFC", text or "").translate(_NATIVE_DIGITS)
    text = _PUNCT.sub(" ", re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", text))  # 19,500 → 19500
    return " ".join(_spoken_numbers([p for w in text.split() for p in _split_number_unit(_loose(w), lang)], lang))


def _edits(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def agreement(a: str, b: str) -> float:
    """Share of matching characters (1 − character edit distance / longer length), spaces ignored."""
    a, b = a.replace(" ", ""), b.replace(" ", "")
    if not a and not b:
        return 1.0
    return 1 - _edits(a, b) / max(len(a), len(b))


def _findings(text: str) -> dict[str, bool]:
    return {f: x.value for f, x in scan_text(text, "").items() if x.value is not None}


def compare(first: str, second: str, lang: str, first_engine: str, second_engine: str) -> dict:
    a, b = normalise(first, lang), normalise(second, lang)
    score = agreement(a, b)
    differences = []
    na, nb = sorted(set(_NUM.findall(a))), sorted(set(_NUM.findall(b)))
    if na != nb:
        differences.append(f"numbers: {', '.join(na) or 'none'} ({first_engine}) vs {', '.join(nb) or 'none'} ({second_engine})")
    fa, fb = _findings(first), _findings(second)
    for f in sorted(set(fa) | set(fb)):
        if fa.get(f) == fb.get(f):
            continue
        name = FINDINGS[f][0].lower()
        if fa.get(f) is True and fb.get(f) is not True:
            differences.append(f"{name}: heard by {first_engine} only")
        elif fb.get(f) is True and fa.get(f) is not True:
            differences.append(f"{name}: heard by {second_engine} only")
    if score < AGREEMENT_MIN:
        differences.append(f"only {round(score * 100)}% of the words match")
    return {"engine": second_engine, "text": second, "agreement": round(score, 3), "differences": differences,
            "disagree": bool(differences)}
