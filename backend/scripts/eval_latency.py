"""H7 latency targets, measured end to end through the API on this laptop (models loaded, as in the demo):

* text to note < 3 s: POST /encounters with a typed complaint, in English and in Odia (Odia includes translation);
* voice to transcript < 2 s: POST /speech/transcribe on FLEURS Odia clips, without and with the English translation;
* report to findings < 15 s: POST /files with a synthetic lab report image (both OCR engines, B2 checks);
* queue < 1 s: GET /queue with every encounter made above.

The app runs in-process (TestClient) on a temporary database; online services are switched off (no Sarvam, no
telephony). Warm-up calls are made first and not counted: the first call loads each model, which happens once at
start-up in the demo.

Usage: python backend/scripts/eval_latency.py <odia_clip_folder> <report_image_folder> [out=docs/evaluation/latency.json]
"""

import io
import json
import os
import statistics
import struct
import sys
import tempfile
import time
import uuid
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="jeevia-latency-")
os.environ["JEEVIA_DATABASE_URL"] = f"sqlite:///{_tmp}/latency.db"
os.environ["JEEVIA_STORAGE_DIR"] = f"{_tmp}/uploads"
os.environ["JEEVIA_LOG_LEVEL"] = "WARNING"
os.environ["JEEVIA_SEED_SCENARIOS"] = "false"
os.environ["JEEVIA_DIRECTORY_AUTOLOAD"] = "false"
os.environ["JEEVIA_RATE_LIMIT"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402

Settings.model_config["env_file"] = None  # never backend/.env: no Sarvam credits, no calls
for _k in [k for k in os.environ if k.startswith(("SARVAM_", "JEEVIA_SARVAM_", "JEEVIA_TWILIO_", "JEEVIA_VONAGE_", "JEEVIA_TELEPHONY_", "JEEVIA_PUBLIC_BASE_URL"))]:
    del os.environ[_k]

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"
TEXTS = {
    "en": ["Chest pain spreading to the left arm since morning, sweating", "Fever for 4 days with headache",
           "Loose stools 6 times since yesterday and vomiting twice", "Cough for 3 weeks with blood in sputum"],
    "or": ["ସକାଳୁ ଛାତି ଦରଦ ହେଉଛି ଓ ବାମ ହାତକୁ ଯାଉଛି", "ଚାରି ଦିନ ହେଲା ଜ୍ୱର ଓ ମୁଣ୍ଡ ବିନ୍ଧୁଛି",
           "କାଲିଠୁ ଝାଡ଼ା ଓ ବାନ୍ତି ହେଉଛି", "ତିନି ସପ୍ତାହ ହେଲା କାଶରେ ରକ୍ତ ଆସୁଛି"],
}


def login(c: TestClient, phone: str) -> dict:
    ch = c.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    r = c.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    if r["status"] == "pin_required":
        r = c.post(f"{API}/auth/pin/verify", json={"pin_token": r["pin_token"], "pin": os.environ.get("JEEVIA_DEMO_PIN", "4826")}).json()
    return {"Authorization": f"Bearer {r['tokens']['access_token']}"}


def wav_seconds(p: Path) -> float:
    """Clip length from the RIFF header; the wave module rejects the 32-bit float clips FLEURS ships."""
    b, i, rate = p.read_bytes(), 12, 0
    while i + 8 <= len(b):
        tag, size = b[i:i + 4], struct.unpack("<I", b[i + 4:i + 8])[0]
        if tag == b"fmt ":
            rate = struct.unpack("<I", b[i + 16:i + 20])[0]  # byte rate
        elif tag == b"data":
            return size / rate
        i += 8 + size + (size & 1)
    raise ValueError(f"no data chunk in {p}")


def timed(fn) -> tuple[float, object]:
    t = time.perf_counter()
    r = fn()
    return time.perf_counter() - t, r


def stats(xs: list[float], target: float) -> dict:
    xs = sorted(xs)
    return {"n": len(xs), "median_s": round(statistics.median(xs), 2), "p90_s": round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 2),
            "max_s": round(xs[-1], 2), "target_s": target, "under_target": sum(x < target for x in xs)}


def main(clips: str, reports: str, out: str = "docs/evaluation/latency.json") -> None:
    res = {}
    with TestClient(app) as c:
        nurse = login(c, "9000000002")
        dev = f"lat-{uuid.uuid4().hex[:12]}"  # intakes must come from a device bound to the facility
        assert c.post(f"{API}/devices", json={"label": "Latency test", "device_id": dev}, headers=nurse).status_code == 200
        nurse["X-Device-Id"] = dev

        def encounter(text: str, lang: str):
            pat = c.post(f"{API}/patients", json={"name": "Latency Test", "age": 40, "sex": "M", "language": lang}, headers=nurse).json()
            con = c.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": lang,
                                                  "scopes": ["triage"]}, headers=nurse).json()
            body = {"patient_id": pat["id"], "facility_id": "fac_phc_manikpur", "category": "normal", "language": lang, "chief_complaint": text,
                    "symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": [], "vitals": {"pulse": 88, "bp_systolic": 130},
                    "consent_id": con["id"], "client_ref": f"lat_{uuid.uuid4().hex}"}
            dt, r = timed(lambda: c.post(f"{API}/encounters", json=body, headers=nurse))
            assert r.status_code == 200, r.text[:300]
            last["id"] = r.json()["id"]
            return dt

        last: dict = {}

        def summary_ready(text: str, lang: str):
            """Seconds from submitting the intake until the language model's summary is saved on the note (it runs in the
            background, so the rules note and urgency are already shown before this)."""
            t = time.perf_counter()
            encounter(text, lang)
            while time.perf_counter() - t < 90:
                note = c.get(f"{API}/encounters/{last['id']}", headers=nurse).json().get("note") or {}
                if note.get("llm"):
                    return time.perf_counter() - t, note["llm"].get("status")
                time.sleep(0.25)
            return time.perf_counter() - t, "timeout"

        encounter(TEXTS["en"][0], "en"), encounter(TEXTS["or"][0], "or")  # warm-up
        for lang in ("en", "or"):
            res[f"text_to_note_{lang}"] = stats([encounter(t, lang) for _ in range(3) for t in TEXTS[lang]], 3.0)
            print(lang, res[f"text_to_note_{lang}"], flush=True)
        if os.environ.get("JEEVIA_LLM_URL"):
            got = [summary_ready(t, lang) for lang in ("en", "or") for t in TEXTS[lang]]
            res["intake_to_ai_summary"] = {**stats([g[0] for g in got], 15.0), "status": [g[1] for g in got],
                                           "note": "background; the rules note and urgency are shown first"}
            print("summary", res["intake_to_ai_summary"], flush=True)

        wavs = sorted(Path(clips).glob("*.wav"))
        secs = []
        for w in wavs:
            secs.append(wav_seconds(w))

        def speech(w: Path, translate: bool):
            dt, r = timed(lambda: c.post(f"{API}/speech/transcribe", files={"audio": (w.name, w.read_bytes(), "audio/wav")},
                                         data={"language": "or", "translate": str(translate).lower()}, headers=nurse))
            assert r.status_code == 200, r.text[:300]
            return dt

        speech(wavs[0], True)  # warm-up
        for translate in (False, True):
            key = "voice_to_transcript" + ("_and_english" if translate else "")
            times = [speech(w, translate) for w in wavs]
            res[key] = {**stats(times, 2.0), "audio_s_median": round(statistics.median(secs), 1),
                        "per_clip": [{"audio_s": round(a, 1), "s": round(t, 2)} for a, t in zip(secs, times)]}
            print(key, {k: v for k, v in res[key].items() if k != "per_clip"}, flush=True)

        imgs = sorted(Path(reports).rglob("*.png"))[:8] + sorted(Path(reports).rglob("*.jpg"))[:8]

        def report(p: Path):
            mime = "image/png" if p.suffix == ".png" else "image/jpeg"
            dt, r = timed(lambda: c.post(f"{API}/files", files={"file": (p.name, io.BytesIO(p.read_bytes()), mime)}, data={"kind": "report"}, headers=nurse))
            assert r.status_code == 200, r.text[:300]
            return dt

        report(imgs[0])  # warm-up
        res["report_to_findings"] = stats([report(p) for p in imgs], 15.0)
        print("report", res["report_to_findings"], flush=True)

        queue = []
        for _ in range(10):
            dt, r = timed(lambda: c.get(f"{API}/queue", params={"facility_id": "fac_phc_manikpur"}, headers=nurse))
            assert r.status_code == 200, r.text[:300]
            queue.append(dt)
        res["queue"] = {**stats(queue, 1.0), "entries": len(r.json())}
        print("queue", res["queue"], flush=True)
    res["machine"] = "Dell G15, i5-12500H, 16 GB RAM; speech and report reading on the CPU, summary model on the laptop GPU" if os.environ.get("JEEVIA_LLM_URL") else "Dell G15, i5-12500H, 16 GB RAM, CPU only"
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:])
