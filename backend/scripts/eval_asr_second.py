"""B9: measure a second speech engine on the same FLEURS clips as the offline engine, and how far the two engines'
transcripts are from each other, to set the disagreement threshold (app/asr_check.py).

Engines: "sarvam" (Saaras v3, online; needs SARVAM_API_KEY in backend/.env, one request a clip) or "indicwhisper"
(AI4Bharat Vistaar, offline; JEEVIA_ASR_SECOND_INT8=false for the fp32 model, default 8-bit).
Reads the offline engine's per-clip results (eval_asr.py's output) so IndicConformer need not be loaded again.

    python backend/scripts/eval_asr_second.py models/eval/fleurs_or or docs/evaluation/asr_or_fleurs_dev25_ctc_int8.json [sarvam|indicwhisper]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import asr_check, sarvam, whisper_asr  # noqa: E402
from app.config import get_settings  # noqa: E402
from scripts.eval_asr import edits, norm  # noqa: E402


def _memory_gb() -> dict:
    """Resident and peak memory of this process (peak: Windows only), measured after the clips are heard."""
    try:
        import psutil
    except ImportError:
        return {}
    m = psutil.Process().memory_info()
    return {"resident_gb": round(m.rss / 2**30, 2), **({"peak_gb": round(m.peak_wset / 2**30, 2)} if hasattr(m, "peak_wset") else {})}


def main(folder: str, lang: str, offline_json: str, engine: str = "sarvam") -> None:
    root = Path(folder)
    offline = {c["file"]: c for c in json.loads(Path(offline_json).read_text(encoding="utf-8"))["clips"]}
    if engine == "sarvam":
        if not sarvam.enabled():
            sys.exit("SARVAM_API_KEY is not set")
        name_, hear, tag = sarvam.STT_ENGINE, lambda b, n: sarvam.transcribe(b, lang, n)["text"], "sarvam"
    elif engine == "indicwhisper":
        if not whisper_asr.available(lang):
            sys.exit(f"IndicWhisper for '{lang}' is not downloaded (models/indicwhisper)")
        int8 = get_settings().asr_second_int8
        name_, hear, tag = whisper_asr.ENGINE, lambda b, n: whisper_asr.transcribe(b, lang)["text"], f"indicwhisper_{'int8' if int8 else 'fp32'}"
        t = time.perf_counter()
        whisper_asr._model(lang)
        load_s = round(time.perf_counter() - t, 1)
    else:
        sys.exit(f"unknown engine {engine}")
    w_err = w_tot = c_err = c_tot = 0
    rows, secs = [], []
    for name, off in sorted(offline.items()):
        t = time.perf_counter()
        heard = hear((root / name).read_bytes(), name)
        secs.append(time.perf_counter() - t)
        ref, hyp = norm(off["reference"]), norm(heard)
        we, ce = edits(ref.split(), hyp.split()), edits(list(ref.replace(" ", "")), list(hyp.replace(" ", "")))
        w_err, w_tot, c_err, c_tot = w_err + we, w_tot + len(ref.split()), c_err + ce, c_tot + len(ref.replace(" ", ""))
        cmp = asr_check.compare(off["heard"], heard, lang, "IndicConformer", name_)
        # Which engine was nearer the human transcript, in the comparison's own normal form
        r = asr_check.normalise(off["reference"], lang)
        near = {e: asr_check.agreement(r, asr_check.normalise(t_, lang)) for e, t_ in (("offline", off["heard"]), ("second", heard))}
        rows.append({"file": name, "reference": off["reference"], "offline": off["heard"], "second": heard,
                     "second_wer": round(we / max(1, len(ref.split())), 3), "offline_wer": off["wer"],
                     "engines_agreement": cmp["agreement"], "differences": cmp["differences"],
                     "reference_agreement": {k: round(v, 3) for k, v in near.items()}})
        print(name, rows[-1]["second_wer"], round(secs[-1], 1), flush=True)
    ag = sorted(r["engines_agreement"] for r in rows)
    summary = {
        "engine": name_, "language": lang, "clips": len(rows),
        "second_wer": round(w_err / max(1, w_tot), 3), "second_cer": round(c_err / max(1, c_tot), 3),
        "engines_agreement": {"min": ag[0], "median": ag[len(ag) // 2], "max": ag[-1]} if ag else None,
        "flagged_at_threshold": sum(1 for r in rows if r["differences"]), "threshold": asr_check.AGREEMENT_MIN,
        "seconds_per_clip": round(sum(secs) / len(secs), 1) if secs else None,
    }
    if engine == "indicwhisper":
        summary |= {"load_seconds": load_s, "memory": _memory_gb()}
    out = Path(offline_json).with_name(f"asr_{lang}_fleurs_dev{len(rows)}_{tag}.json")
    out.write_text(json.dumps({"summary": summary, "clips": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"per clip: {out}")


def rescore(result_json: str, lang: str, second_engine: str) -> None:
    """Compare saved transcripts again after a change to app/asr_check.py, without hearing the clips again."""
    f = Path(result_json)
    d = json.loads(f.read_text(encoding="utf-8"))
    for c in d["clips"]:
        heard = c.get("second", c.get("sarvam"))
        cmp = asr_check.compare(c["offline"], heard, lang, "IndicConformer", second_engine)
        c["engines_agreement"], c["differences"] = cmp["agreement"], cmp["differences"]
    ag = sorted(c["engines_agreement"] for c in d["clips"])
    d["summary"] |= {"engines_agreement": {"min": ag[0], "median": ag[len(ag) // 2], "max": ag[-1]},
                     "flagged_at_threshold": sum(1 for c in d["clips"] if c["differences"]), "threshold": asr_check.AGREEMENT_MIN}
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f.name, json.dumps(d["summary"]))


if __name__ == "__main__":
    if sys.argv[1] == "rescore":  # rescore <result.json> <lang> <engine name>
        rescore(*sys.argv[2:5])
    else:
        main(*sys.argv[1:5])
