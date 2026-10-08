"""Santali (Ol Chiki) end to end through the API, offline (TODO section 9).

1. Typed: eight English complaints are put into Santali by IndicTrans2 (as a Santali speaker would type them; no
   Santali speaker on the team), entered in Santali, and the note's English and urgency are compared with the same
   complaint entered in English. The rules read the English (there is no Santali symptom word list), so a symptom the
   translation loses is a missed finding; the comparison shows how often.
2. Spoken: IndicVoices Santali clips (CC BY 4.0) through /speech/transcribe with the English translation.

The app runs in-process on a temporary database; online services are off (no Sarvam, no telephony).
Usage: python backend/scripts/santali_e2e.py <iv_sat_folder> [out=docs/evaluation/santali_e2e.json]
"""

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="jeevia-sat-")
os.environ["JEEVIA_DATABASE_URL"] = f"sqlite:///{_tmp}/sat.db"
os.environ["JEEVIA_STORAGE_DIR"] = f"{_tmp}/uploads"
os.environ["JEEVIA_LOG_LEVEL"] = "WARNING"
os.environ["JEEVIA_SEED_SCENARIOS"] = "false"
os.environ["JEEVIA_DIRECTORY_AUTOLOAD"] = "false"
os.environ["JEEVIA_RATE_LIMIT"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import Settings  # noqa: E402

Settings.model_config["env_file"] = None  # never backend/.env: no Sarvam credits, no calls
for _k in [k for k in os.environ if k.startswith(("SARVAM_", "JEEVIA_SARVAM_", "JEEVIA_TWILIO_", "JEEVIA_VONAGE_", "JEEVIA_TELEPHONY_", "JEEVIA_PUBLIC_BASE_URL", "JEEVIA_LLM_", "JEEVIA_VLM_"))]:
    del os.environ[_k]

from fastapi.testclient import TestClient  # noqa: E402

from app import language  # noqa: E402
from app.main import app  # noqa: E402
from eval_latency import API, login  # noqa: E402

COMPLAINTS = [
    "Chest pain spreading to the left arm since morning, with sweating",
    "Fever for four days with headache",
    "Loose motions six times since yesterday and vomiting",
    "Cough for three weeks with blood in the sputum",
    "My child has fever and is not able to drink",
    "Sudden weakness of the right arm and leg one hour ago",
    "I am seven months pregnant and have bleeding",
    "Mild knee pain for one month",
]


def main(clips: str, out: str = "docs/evaluation/santali_e2e.json") -> None:
    sat = language.translate(COMPLAINTS, "en", "sat")["texts"]
    res = {"typed": [], "spoken": []}
    with TestClient(app) as c:
        nurse = login(c, "9000000002")

        def note(text: str, lang: str, age: int) -> dict:
            pat = c.post(f"{API}/patients", json={"name": "Santali Test", "age": age, "sex": "F", "language": lang}, headers=nurse).json()
            con = c.post(f"{API}/consents", json={"patient_id": pat["id"], **({"mode": "self"} if age >= 18 else {"mode": "proxy", "proxy_name": "Test Parent", "proxy_relation": "Mother"}), "privacy_context": "private", "language": lang,
                                                  "scopes": ["triage"]}, headers=nurse).json()
            assert "id" in pat and "id" in con, (pat, con)
            body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "maternal" if "pregnant" in text.lower() else "normal",
                    "language": lang, "chief_complaint": text, "selected_symptoms": [],
                    "symptoms": [] if lang == "en" else [{"text": "", "original_text": text, "language": lang, "source": "text"}], "answers": [], "file_ids": [],
                    "vitals": {"pulse": 88, "bp_systolic": 124, "bp_diastolic": 80, "spo2": 98, "resp_rate": 16, "temp_f": 98.6, "avpu": "A"},
                    "consent_id": con["id"], "client_ref": f"sat_{uuid.uuid4().hex}"}
            r = c.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": "dev_kiosk_manikpur_1"})
            assert r.status_code == 200, r.text[:300]
            return r.json()

        for en, st in zip(COMPLAINTS, sat):
            age = 3 if "child" in en else 30
            a, b = note(en, "en", age), note(st, "sat", age)
            sym = ((b.get("intake") or {}).get("symptoms") or [{}])[0]
            res["typed"].append({"english": en, "santali": st, "english_in_note": sym.get("text"), "engine": sym.get("engine"),
                                 "urgency_english": a["urgency"], "urgency_santali": b["urgency"], "same": a["urgency"] == b["urgency"]})
            print(res["typed"][-1], flush=True)
        for w in sorted(Path(clips).glob("sat_0[0-4]*.wav"))[:6]:
            r = c.post(f"{API}/speech/transcribe", files={"audio": (w.name, w.read_bytes(), "audio/wav")}, data={"language": "sat", "translate": "true"}, headers=nurse)
            j = r.json() if r.status_code == 200 else {"error": r.text[:200]}
            res["spoken"].append({"file": w.name, "status": r.status_code, "heard": j.get("text"), "english": j.get("english") or j.get("translation"),
                                  "confidence": j.get("confidence")})
            print(res["spoken"][-1], flush=True)
    res["typed_same_urgency"] = sum(x["same"] for x in res["typed"])
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("same urgency", res["typed_same_urgency"], "of", len(res["typed"]))


if __name__ == "__main__":
    main(*sys.argv[1:])
