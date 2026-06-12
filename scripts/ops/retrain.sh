#!/usr/bin/env bash
# scripts/ops/retrain.sh — Full retrain pipeline (features -> train -> backtest).

set -euo pipefail

echo "[OPS] Building features..."
python -m src.features.build_features

echo "[OPS] Training models..."
python -m src.models.train

echo "[OPS] Running backtest..."
python -m src.models.backtest

echo "[OPS] Retrain complete."
