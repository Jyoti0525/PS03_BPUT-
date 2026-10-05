#!/usr/bin/env bash
# Start the note-summary model (B5) on the demo laptop: llama.cpp llama-server on 127.0.0.1:8031, all layers on the
# GPU (RTX 3050, 4 GB). Then start the backend with JEEVIA_LLM_URL=http://127.0.0.1:8031.
# Fetches the pinned llama.cpp Windows CUDA 12.4 build into models/llama.cpp the first time.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT/models/llama.cpp"
MODEL="$ROOT/models/qwen3-4b-instruct-2507/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
TAG=b11424
if [ ! -x "$BIN/llama-server.exe" ]; then
  mkdir -p "$BIN" && cd "$BIN"
  U=https://github.com/ggml-org/llama.cpp/releases/download/$TAG
  curl -fSL --retry 5 -C - -o llama.zip "$U/llama-$TAG-bin-win-cuda-12.4-x64.zip"
  curl -fSL --retry 5 -C - -o cudart.zip "$U/cudart-llama-bin-win-cuda-12.4-x64.zip"
  unzip -qo llama.zip && unzip -qo cudart.zip && rm llama.zip cudart.zip && echo "$TAG" > VERSION
fi
[ -f "$MODEL" ] || { echo "Model missing: run python backend/scripts/fetch_models.py" >&2; exit 1; }
# -ngl 99: every layer on the GPU; -c 4096: a note's fact sheet plus answer fits easily; one request at a time.
exec "$BIN/llama-server.exe" -m "$MODEL" --host 127.0.0.1 --port 8031 -ngl 99 -c 4096 -np 1 --temp 0
