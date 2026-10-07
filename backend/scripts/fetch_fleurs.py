"""Fetch a small FLEURS dev sample (Google, CC-BY-4.0) for the speech evaluation: the first N clips of one language.

    python backend/scripts/fetch_fleurs.py hi_in models/eval/fleurs_hi 25

Writes <out>/dev.tsv (the rows kept) and <out>/*.wav. Read speech with human transcripts; no patient data.
"""

import sys
import tarfile
from pathlib import Path

from huggingface_hub import hf_hub_download


def main(config: str, out: str, n: int = 25) -> None:
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    tsv = Path(hf_hub_download("google/fleurs", f"data/{config}/dev.tsv", repo_type="dataset"))
    rows = [line for line in tsv.read_text(encoding="utf-8").splitlines() if line.strip()][:n]
    want = {r.split("\t")[1] for r in rows}
    tar = hf_hub_download("google/fleurs", f"data/{config}/audio/dev.tar.gz", repo_type="dataset")
    with tarfile.open(tar) as t:
        for m in t:
            name = Path(m.name).name
            if m.isfile() and name in want:
                (dest / name).write_bytes(t.extractfile(m).read())
    (dest / "dev.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(config, len(list(dest.glob("*.wav"))), "clips in", dest)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 25)
