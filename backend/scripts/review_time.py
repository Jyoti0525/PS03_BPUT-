"""Review time per case from the audit trail (app/review_time.py). Run after a timed review session.

A session: a clinician who has not seen the cases opens each one in the review screen, reads it, and confirms or
overrides it, as at the facility. Run from backend/ against the same database:
    python scripts/review_time.py [facility_id] [out=docs/evaluation/review_time.json]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal  # noqa: E402
from app.review_time import review_times  # noqa: E402

if __name__ == "__main__":
    a = sys.argv[1:]
    with SessionLocal() as db:
        res = review_times(db, a[0] if a and a[0] != "-" else None)
    Path(a[1] if len(a) > 1 else "docs/evaluation/review_time.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "per_case"}, indent=1))
