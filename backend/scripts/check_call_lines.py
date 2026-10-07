"""Back-translate every reminder-call line (calls.yaml) to English with the offline IndicTrans2 model, beside the
English original, so a reader can spot a line whose meaning drifted. A check, not a replacement for a native speaker.

    cd backend && .venv/Scripts/python.exe scripts/check_call_lines.py [lang ...] > call_lines_check.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import calls, language  # noqa: E402

FILL = {"facility": "PHC Manikpur", "name": "Rina", "date": "01/10", "condition": "diabetes"}


def main(langs: list[str]) -> None:
    cfg = calls.config()
    items = [(f"lines.{k}", v) for k, v in cfg["lines"].items()]
    items += [(f"{p}.{q['key']}", q) for p, qs in cfg["scripts"].items() for q in qs if q["kind"] != "identity"]
    for lang in langs:
        texts = [v[lang].format(**FILL) for _, v in items]
        back = language.translate(texts, lang, "en")["texts"]
        print(f"\n=== {lang} ===")
        for (key, v), b in zip(items, back):
            print(f"{key}\n  en:   {v['en'].format(**FILL)}\n  back: {b}")


if __name__ == "__main__":
    main(sys.argv[1:] or [lang for lang in calls.LANGS if lang != "en"])
