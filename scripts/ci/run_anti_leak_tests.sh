#!/usr/bin/env bash
# scripts/ci/run_anti_leak_tests.sh — CI entry point for anti-leak regression tests.

set -euo pipefail

echo "[CI] Running anti-leak regression tests..."
python -m pytest tests/test_leakage.py -v --tb=short -x

echo "[CI] Running module order audit..."
python scripts/audit/check_module_order.py

echo "[CI] All anti-leak checks passed."
