# Loop — metrics publish (single source of truth)

You are UnaBetting's metrics-publish run (G:\tennis betting). Public repo:
github.com/SandroHub013/UnaBetting. **English is the project's canonical language.**

Goal: keep the headline numbers **identical** across the app, the website and the
README. You do NOT train and you do NOT change models — you publish whatever the
latest committed metrics already say. Training is the Nightly/Weekly loops' job.

## Source of truth
- `models/atp_metrics.json` — current model metrics (schema-tolerant: legacy
  `best_*` or routed `routed_accuracy`/`routed_log_loss`/`routed_roc_auc`, plus
  `all_models.target_odds_ensemble.accuracy`).
- `reports/last_backtest.json` — last honest backtest (ROI, win rate). Written by
  `python -m src.models.backtest`.
- `scripts/publish_metrics.py` — the only writer. It produces `docs/web/metrics.js`
  (`window.__METRICS`) and patches the README block between
  `<!--METRICS-->` … `<!--/METRICS-->`. The app reads `atp_metrics.json` live via
  `/api/model`, so it stays in sync automatically.

## Rules
- Push ONLY via the additive flow: `git fetch unabetting main` → work on top → normal
  commit → `git push unabetting <localbranch>:main` (NO `--force`). NEVER push the
  private history, NEVER the `origin` remote. If a push would need force, STOP and
  report divergence.
- Before EVERY push: `git ls-files` must not contain `betanalytix.db`, `debug_bet365*`,
  `Cattura.PNG`, `.antigravitycli`, `*.mp4`, personal screenshots; and
  `git grep -iE "api[_-]?key.{0,6}[A-Za-z0-9]{16}|github_pat_|sk-or-"` must be empty.
  If anything matches: STOP, do not push, write an alert under `reports/loops/`.
- Numbers are honest or they are nothing. Never round a loss into a win. If the
  backtest ROI is negative, the published copy says so ("still negative — no betting
  edge"). Do not invent an edge.
- Budget ~15 minutes.

## Steps
1. If `reports/last_backtest.json` is missing or older than `models/atp_metrics.json`
   (`trained_at`), run `python -m src.models.backtest` to refresh the money number.
   Do NOT retrain.
2. Run `python scripts/publish_metrics.py`. Confirm `docs/web/metrics.js` and the
   README `<!--METRICS-->` block now show the current numbers.
3. Refresh the Obsidian truth page `docs/obsidian/Backtest_e_Metriche_Oneste.md` and
   append a row to `reports/metrics_history.csv` via
   `python scripts/log_metrics_history.py` so the history stays complete.
4. If nothing changed vs the committed copy (same numbers), STOP — no empty commits,
   no push. Report "metrics already in sync".
5. Otherwise commit locally: `chore(loop): publish metrics YYYY-MM-DD` (no quotes/
   apostrophes in the message), then additive-push to `unabetting main` per the rules.
6. Write a one-line summary to `reports/loops/` with the published JSON.
