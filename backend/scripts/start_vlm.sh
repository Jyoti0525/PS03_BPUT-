#!/usr/bin/env bash
# Second document-type label (app/triage/vlm.py): Qwen3-VL-4B-Instruct (Apache-2.0) on llama-server, port 8032.
# Files (2.8 GB) from huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF into models/qwen3-vl-4b/. CPU by default, so it
# does not take the GPU from the summary model; pass a layer count (e.g. 99) to put it on the GPU instead.
# Then set JEEVIA_VLM_URL=http://127.0.0.1:8032 in backend/.env.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT/models/llama.cpp"
DIR="$ROOT/models/qwen3-vl-4b"
for f in Qwen3VL-4B-Instruct-Q4_K_M.gguf mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf; do
  [ -f "$DIR/$f" ] || curl -fSL --retry 5 -C - -o "$DIR/$f" "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main/$f"
done
exec "$BIN/llama-server.exe" -m "$DIR/Qwen3VL-4B-Instruct-Q4_K_M.gguf" --mmproj "$DIR/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf" \
  --host 127.0.0.1 --port 8032 -ngl "${1:-0}" --no-mmproj-offload -c 4096 -np 1 --temp 0
