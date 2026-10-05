"""Download the offline speech, translation and note-summary models into <repo>/models (git-ignored).

The AI4Bharat repos on Hugging Face are gated: accept the terms on each model page once, then log in
with a read token (`hf auth login`) before running this.

    python backend/scripts/fetch_models.py

Each repo ships its weights twice (pytorch_model.bin and model.safetensors); only one copy is fetched.
"""

import sys
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

MODELS = [
    "ai4bharat/indictrans2-indic-en-dist-200M",  # Indic → English (notes for the doctor)
    "ai4bharat/indictrans2-en-indic-dist-200M",  # English → Indic (advice back to the patient)
    "ai4bharat/indic-conformer-600m-multilingual",  # speech recognition, 22 languages
]
WEIGHTS = ("pytorch_model.bin", "model.safetensors")
# Note summary model (B5): Qwen3-4B-Instruct-2507 (Apache-2.0), 4-bit GGUF quantised by Unsloth, ~2.5 GB.
# It runs in llama.cpp's llama-server (scripts/start_llm.sh fetches the pinned Windows CUDA build).
LLM = ("unsloth/Qwen3-4B-Instruct-2507-GGUF", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "qwen3-4b-instruct-2507")

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
    repo, file, folder = LLM
    print(f"- {repo} ({file})", flush=True)
    hf_hub_download(repo, file, local_dir=root / folder)
    print("Next: python backend/scripts/quantize_asr.py  (8-bit speech model the app uses by default)")


if __name__ == "__main__":
    sys.exit(main())
