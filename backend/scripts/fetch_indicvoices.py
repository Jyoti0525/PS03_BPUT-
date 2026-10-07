"""Fetch 25 validation clips of IndicVoices (AI4Bharat, CC-BY-4.0) for the languages FLEURS does not have.

The dataset is gated: accept its terms once at https://huggingface.co/datasets/ai4bharat/IndicVoices with the account
`huggingface-cli login` uses. Only the first row group of the validation file is read (HTTP range requests), not the
~300 MB file. Writes <out>/dev.tsv in FLEURS's layout (id, file, transcript) and the clips, for eval_asr.py:

    python backend/scripts/fetch_indicvoices.py brx models/eval/iv_brx 25
    python backend/scripts/eval_asr.py models/eval/iv_brx brx

Read and spontaneous speech with human transcripts; no patient data. Requires pyarrow (evaluation only).
"""

import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import HfFileSystem

FOLDER = {"brx": "bodo", "doi": "dogri", "ks": "kashmiri", "kok": "konkani", "mai": "maithili", "mni": "manipuri",
          "sa": "sanskrit", "sat": "santali"}


def main(lang: str, out: str, n: int = 25) -> None:
    f = pq.ParquetFile(HfFileSystem().open(f"datasets/ai4bharat/IndicVoices/{FOLDER[lang]}/valid-00000-of-00001.parquet"))
    names = f.schema_arrow.names
    audio = next(c for c in names if "audio" in c)
    text = next(c for c in ("text", "normalized", "transcript", "verbatim") if c in names)
    rows, g = [], 0
    while len(rows) < n and g < f.metadata.num_row_groups:
        rows += f.read_row_group(g, columns=[audio, text]).to_pylist()
        g += 1
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    lines = []
    usable = [r for r in rows if r[text] and r[audio] and r[audio].get("bytes")][:n]
    for i, r in enumerate(usable):
        name = f"{lang}_{i:03d}.wav"  # the decoder reads the format from the bytes, not the name
        (dest / name).write_bytes(r[audio]["bytes"])
        lines.append(f"{i}\t{name}\t{' '.join(r[text].split())}")
    (dest / "dev.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(lang, len(lines), "clips in", dest)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 25)
