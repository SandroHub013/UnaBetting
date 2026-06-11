# Nightly loop — maintenance & model refresh

You are UnaBetting's automated nightly run (G:\tennis betting). Execute these steps
IN ORDER. Be conservative: if a step fails, note it and continue when possible; do not
improvise structural fixes (that's the weekly loop's job).

## Hard rules
- NEVER push to remote. Local commits only, on the current branch.
- NEVER call the-odds-api or other paid/quota services.
- Do NOT edit the EXPERIMENTS.md queue (only the weekly loop may).
- Any inference outside train.py MUST use train medians + scaler + randomized
  perspective (see docs/obsidian/Backtest_e_Metriche_Oneste.md).
- Budget: if you exceed ~30 minutes, wrap up with a commit of what's done.

## Steps
1. **Repo state**: `git status --short`. If there are uncommitted changes that aren't
   yours, do NOT touch them; work around them.
2. **Data**: `python update_data.py --check`. If it reports new data:
   `python update_data.py` (git pull Sackmann/TML + tennis-data.co.uk odds + feature
   rebuild — ~20 min). If no new data, skip to step 5.
3. **Retrain**: `python -m src.models.train` (only if features were rebuilt in step 2).
4. **Log metrics**: `python scripts/log_metrics_history.py`.
5. **Honest backtest**: `python -m src.models.backtest`. Note ROI and win rate.
6. **Regression guard**: compare the last two rows of `reports/metrics_history.csv`.
   If accuracy drops >1 point or log loss rises >0.01: add a note under an `## Alerts`
   section in EXPERIMENTS.md (create it if missing) with the date and numbers — that's
   the only case where you may touch that file.
7. **Obsidian**: if current metrics changed, update the table in
   `docs/obsidian/Backtest_e_Metriche_Oneste.md` and the Status in
   `docs/obsidian/Index.md`.
8. **Commit**: `git add` the touched files + commit
   `chore(loop): nightly maintenance YYYY-MM-DD — <short outcome>`.
   If nothing changed, do NOT commit; finish with "no updates".
