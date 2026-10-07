"""Kannada review sheet for a native speaker: English, Kannada, the Kannada read back into English by IndicTrans2.

Rows whose read-back shares few words with the English are marked "Check first".
Run from backend/:  python scripts/kn_review_sheet.py  →  docs/translation_review_kn.csv
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import language  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend/src/lib/i18n/phrases/kn.ts"
OUT = ROOT / "docs/translation_review_kn.csv"
LINE = re.compile(r'^\s*("(?:[^"\\]|\\.)*")\s*:\s*("(?:[^"\\]|\\.)*"),?\s*$')


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def main():
    pairs = [(json.loads(m[1]), json.loads(m[2])) for line in SRC.read_text(encoding="utf-8").splitlines() if (m := LINE.match(line))]
    back: list[str] = []
    for i in range(0, len(pairs), 16):
        back += language.translate([kn for _, kn in pairs[i : i + 16]], "kn", "en")["texts"]
        print(f"{min(i + 16, len(pairs))}/{len(pairs)}", flush=True)
    rows = []
    for (en, kn), bt in zip(pairs, back):
        a, b = words(en), words(bt)
        overlap = len(a & b) / len(a) if a else 1.0
        rows.append((overlap, en, kn, bt))
    rows.sort(key=lambda r: r[0])
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "Check first", "English", "Kannada", "Kannada read back by machine", "Kannada OK? (Y/N)", "Kannada correction"])
        for i, (ov, en, kn, bt) in enumerate(rows, 1):
            w.writerow([i, "YES" if ov < 0.4 else "", en, kn, bt, "", ""])
    print(len(rows), "rows,", sum(r[0] < 0.4 for r in rows), "to check first →", OUT)


if __name__ == "__main__":
    main()
