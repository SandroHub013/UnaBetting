---
name: deploy
description: Publish the current honest metrics to README, website and app (this project's only "deploy").
---

There is no server deployment. "Deploy" means publishing the latest honest numbers
from the single source of truth:

1. Fresh artifacts first: `python -m src.models.train` then
   `python -m src.models.backtest` (they write `models/atp_metrics.json` and
   `reports/last_backtest.json`).
2. `python scripts/publish_metrics.py` — rewrites `docs/web/metrics.js` and the
   README `<!--METRICS-->` block from those files.
3. `python scripts/log_metrics_history.py` — appends the snapshot to
   `reports/metrics_history.csv`.
4. Commit with a `docs` or `web` scope.

Rules: never publish numbers that didn't come from a retrain you actually ran —
a merged experiment is not a verified one (EXPERIMENTS.md, 2026-06-12 lesson).
The website is GitHub Pages off this repo; the desktop app reads
`atp_metrics.json` live via `/api/model`, so it needs no extra publish step.
