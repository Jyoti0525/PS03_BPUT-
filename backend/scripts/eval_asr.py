"""Measure offline speech recognition on public read-speech clips with human transcripts.

Data: Google FLEURS (CC-BY-4.0), e.g. the Odia dev split, as <dir>/dev.tsv + <dir>/*.wav. Reports word and
character error rate (WER / CER) after light normalisation (punctuation removed, whitespace collapsed),
plus speed, and translates each transcript to English so a reader can judge meaning, not only spelling.

    python backend/scripts/eval_asr.py models/eval/fleurs_or or
"""

import csv
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import language  # noqa: E402

PUNCT = re.compile(r"[।॥.,!?;:'\"()\[\]{}\-–—“”‘’|]")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return " ".join(PUNCT.sub(" ", s).split())


def edits(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def main(folder: str, lang: str) -> None:
    root = Path(folder)
    refs = {}
    with open(root / "dev.tsv", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            refs[row[1]] = row[2]  # file name → raw transcription
    clips = sorted(p for p in root.glob("*.wav") if p.name in refs)
    language._conformer()  # load once; timings below are per clip
    try:
        import psutil

        proc = psutil.Process()
    except ImportError:
        proc = None
    w_err = w_tot = c_err = c_tot = 0
    audio_s = taken_s = 0.0
    rows, rejected = [], []
    for p in clips:
        t = time.perf_counter()
        try:
            out = language.transcribe(p.read_bytes(), lang)
        except language.AudioRejected as e:  # the app refuses it too (e.g. under the minimum length); counted, not scored
            rejected.append({"file": p.name, "why": str(e)})
            continue
        taken_s += time.perf_counter() - t
        audio_s += out["seconds_audio"]
        ref, hyp = norm(refs[p.name]), norm(out["text"])
        we, ce = edits(ref.split(), hyp.split()), edits(list(ref.replace(" ", "")), list(hyp.replace(" ", "")))
        w_err, w_tot, c_err, c_tot = w_err + we, w_tot + len(ref.split()), c_err + ce, c_tot + len(ref.replace(" ", ""))
        rows.append({"file": p.name, "reference": refs[p.name], "heard": out["text"], "wer": round(we / max(1, len(ref.split())), 3), "confidence": out.get("confidence")})
        print(f"{p.name} {out['seconds_audio']:.1f}s audio, {time.perf_counter() - t:.1f}s, wer {rows[-1]['wer']}", file=sys.stderr, flush=True)
    # Process memory with only the speech model loaded (translation below loads more).
    mem = proc.memory_info() if proc else None
    english = []
    for r in rows:  # one at a time: a sentence the translator cannot end shows up here, not as a stalled batch
        t = time.perf_counter()
        english += language.translate([r["heard"]], lang, "en")["texts"]
        print(f"translated {r['file']} in {time.perf_counter() - t:.1f}s", file=sys.stderr, flush=True)
    for r, e in zip(rows, english):
        r["english"] = e
    summary = {
        "engine": language.asr_engine_name(), "decoding": language.get_settings().asr_decoding, "language": lang,
        "clips": len(rows), "rejected_by_app": rejected, "audio_seconds": round(audio_s, 1),
        "wer": round(w_err / max(1, w_tot), 3), "cer": round(c_err / max(1, c_tot), 3),
        "real_time_factor": round(taken_s / max(1e-9, audio_s), 3),
        "process_private_gb": round(getattr(mem, "private", mem.vms) / 2**30, 2) if mem else None,
        "process_peak_working_set_gb": round(getattr(mem, "peak_wset", mem.rss) / 2**30, 2) if mem else None,
        "model": language.get_settings().asr_model,
    }
    (root / "results.json").write_text(json.dumps({"summary": summary, "clips": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "or")
