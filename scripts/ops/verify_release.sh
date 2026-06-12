#!/usr/bin/env bash
# scripts/ops/verify_release.sh — Dry-run of release workflow locally.

set -euo pipefail

echo "[OPS] Verifying pyproject.toml..."
python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"

echo "[OPS] Building package..."
python -m build --sdist --wheel

echo "[OPS] Verifying package..."
python -m twine check dist/*

echo "[OPS] Running tests..."
python -m pytest tests/ -v --tb=short -m 'not slow'

echo "[OPS] Linting..."
ruff check src/

echo "[OPS] Security audit..."
bandit -r src/ -ll

echo "[OPS] All release checks passed."
