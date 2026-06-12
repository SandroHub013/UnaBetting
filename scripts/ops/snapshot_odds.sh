#!/usr/bin/env bash
# scripts/ops/snapshot_odds.sh — Snapshot current odds from the-odds-api.

set -euo pipefail

echo "[OPS] Snapshotting odds..."
python -m src.data.scraper --snapshot

echo "[OPS] Snapshot complete."
