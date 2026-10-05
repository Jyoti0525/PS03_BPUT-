"""Download the offline speech and translation models into <repo>/models (git-ignored).

The AI4Bharat repos on Hugging Face are gated: accept the terms on each model page once, then log in
with a read token (`hf auth login`) before running this.

    python backend/scripts/fetch_models.py

Each repo ships its weights twice (pytorch_model.bin and model.safetensors); only one copy is fetched.
"""

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

MODELS = [
    "ai4bharat/indictrans2-indic-en-dist-200M",  # Indic → English (notes for the doctor)
    "ai4bharat/indictrans2-en-indic-dist-200M",  # English → Indic (advice back to the patient)
    "ai4bharat/indic-conformer-600m-multilingual",  # speech recognition, 22 languages
]
WEIGHTS = ("pytorch_model.bin", "model.safetensors")

root = Path(__file__).resolve().parents[2] / "models"


def main() -> None:
    for repo in MODELS:
        dest = root / repo.split("/")[1]
        have = [w for w in WEIGHTS if (dest / w).exists()]
        # Keep whichever copy is already on disk; otherwise take safetensors only.
        skip = list(WEIGHTS) if have else ["pytorch_model.bin"]
        print(f"- {repo}", flush=True)
        snapshot_download(repo, local_dir=dest, ignore_patterns=skip)
        print(f"  done: {dest}", flush=True)
    print("Next: python backend/scripts/quantize_asr.py  (8-bit speech model the app uses by default)")


if __name__ == "__main__":
    sys.exit(main())
