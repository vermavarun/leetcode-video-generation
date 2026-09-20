#!/usr/bin/env bash
# Convenience wrapper: creates the venv on first run, then runs the pipeline.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3.12}"

if [[ ! -d .venv ]]; then
  echo "==> Creating virtualenv (.venv)"
  "$PYTHON" -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

if [[ ! -f models/piper/en_US-lessac-medium.onnx ]]; then
  echo "==> Downloading models (one time)"
  ./.venv/bin/python scripts/setup_models.py
fi

exec ./.venv/bin/python -m lcvideo.cli "$@"
