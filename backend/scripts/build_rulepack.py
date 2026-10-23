"""Write frontend/src/lib/triage/rulepack.json (the rules, word lists and negation for the offline kiosk).

Run from backend/:  python scripts/build_rulepack.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.triage import device_pack  # noqa: E402

pack = device_pack.build()
device_pack.JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
device_pack.JSON_PATH.write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"wrote {device_pack.JSON_PATH} (rulepack {pack['version']}, {sum(len(p['rules']) for p in pack['protocols'])} rules, "
      f"{device_pack.JSON_PATH.stat().st_size // 1024} KB)")
