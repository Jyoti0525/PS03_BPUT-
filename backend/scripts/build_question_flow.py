"""Write frontend/src/lib/question_flow.json from backend/app/triage/question_flow.yaml (after checking it).

Run from backend/:  python scripts/build_question_flow.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.triage import findings, question_flow  # noqa: E402

if bad := question_flow.problems(set(findings.FINDINGS)):
    sys.exit("question_flow.yaml:\n  " + "\n  ".join(bad))
question_flow.JSON_PATH.write_text(json.dumps(question_flow.load(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"wrote {question_flow.JSON_PATH} (version {question_flow.load()['version']}, {len(question_flow.load()['questions'])} questions)")
