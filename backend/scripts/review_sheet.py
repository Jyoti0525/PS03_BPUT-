"""Native-speaker review sheet for Odia or Hindi (TODO §2): one CSV with every line a speaker must check.

Sections: number words 1–100 (mt_checks.py), spoken-spelling rewrites (Odia), symptom word lists (findings.py), and
every screen phrase added or changed since commit ebe00c4, with the machine read-back into English. Phrases whose
read-back shares few words with the English come first.

Run from backend/:  python scripts/review_sheet.py or   →  docs/review_or.csv
"""

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import language, mt_checks  # noqa: E402
from app.triage import findings  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SINCE = "ebe00c4"
LINE = re.compile(r'^\s*("(?:[^"\\]|\\.)*")\s*:\s*("(?:[^"\\]|\\.)*"),?\s*$')
NAME = {"or": "Odia", "hi": "Hindi"}


def phrases(text: str) -> dict[str, str]:
    return {json.loads(m[1]): json.loads(m[2]) for line in text.splitlines() if (m := LINE.match(line))}


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def main(lang: str) -> None:
    rows: list[list] = []
    numbers = mt_checks.OR_NUMBERS if lang == "or" else mt_checks.HI_NUMBERS
    rows += [["Number word", str(i), w, "", ""] for i, w in enumerate(numbers, 1)]
    for pat, to, why in mt_checks.REWRITES.get(lang, []):
        rows.append(["Spoken spelling rewrite", why, f"{pat.pattern}  →  {to}", "", ""])
    for key, by_lang in findings.LEXICON.items():
        if by_lang.get(lang):
            rows.append(["Symptom words", key, " | ".join(by_lang[lang]), "", ""])

    path = f"frontend/src/lib/i18n/phrases/{lang}.ts"
    old = phrases(subprocess.run(["git", "show", f"{SINCE}:{path}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout)
    new = phrases((ROOT / path).read_text(encoding="utf-8"))
    changed = [(en, tr) for en, tr in new.items() if old.get(en) != tr]
    back: list[str] = []
    for i in range(0, len(changed), 16):
        back += language.translate([t for _, t in changed[i : i + 16]], lang, "en")["texts"]
        print(f"read back {min(i + 16, len(changed))}/{len(changed)}", flush=True)
    scored = sorted(((len(words(en) & words(bt)) / len(words(en)) if words(en) else 1.0, en, tr, bt) for (en, tr), bt in zip(changed, back)), key=lambda r: r[0])
    rows += [["Screen phrase" + (" (check first)" if ov < 0.4 else ""), en, tr, bt] + ["", ""] for ov, en, tr, bt in scored]

    out = ROOT / f"docs/review_{lang}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "Section", "English / meaning", NAME[lang], "Machine read-back (phrases)", f"{NAME[lang]} OK? (Y/N)", "Correction"])
        for i, r in enumerate(rows, 1):
            r = r if len(r) == 6 else r[:3] + [""] + r[3:]
            w.writerow([i, *r])
    print(len(rows), "rows,", len(changed), "phrases →", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "or")
