# scripts/diagnostics

One-off diagnostic & analysis scripts — kept for reference, **not** part of the
pipeline. Many document the project's leak hunts and data audits:

- `forensic_leak_check.py`, `verify_rolling_leak.py` — leakage investigations
- `data_quality_audit.py`, `feature_audit.py`, `inspect_db.py`, `check_db_dates.py` — data/feature audits
- `debug_*.py`, `djokovic_trace.py`, `clutch_test.py` — targeted debugging probes
- `strategy_analysis.py` — betting-strategy exploration
- `generate_charts.py`, `generate_pptx.py` — report/figure generators

Run from the project root, e.g. `python scripts/diagnostics/inspect_db.py`.
Active, maintained scripts live one level up in `scripts/`.
