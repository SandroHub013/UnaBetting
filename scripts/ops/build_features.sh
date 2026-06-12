#!/usr/bin/env bash
# scripts/ops/build_features.sh — Full feature pipeline (download -> clean -> features).

set -euo pipefail

echo "[OPS] Downloading data..."
python -m src.data.download

echo "[OPS] Cleaning data..."
python -m src.data.clean

echo "[OPS] Building features..."
python -m src.features.build_features

echo "[OPS] Build features complete."
