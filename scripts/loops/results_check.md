# Daily loop — results feedback (Sofascore)

You are UnaBetting's daily results-check run (G:\tennis betting). Goal: compare the
live-scan predictions against real match outcomes.

## Rules
- NEVER push to remote. NEVER use paid APIs (Sofascore via curl is free).
- Budget ~10 minutes.

## Steps
1. `python scripts/check_results.py --days 4` — fetch outcomes from Sofascore and update
   `reports/results_feedback.csv`.
2. Read the printed summary. If the live-feedback rolling accuracy diverges by more than
   8 points from the offline reference (66.3%) with at least 30 verified matches, add an
   alert under the `## Alerts` section of EXPERIMENTS.md with date and numbers.
3. If there are newly verified matches, update the "live feedback" row in the metrics
   table of `docs/obsidian/Backtest_e_Metriche_Oneste.md` (create it if missing:
   "Live feedback (Sofascore) | X/Y correct (Z%)").
4. Commit: `chore(loop): results check YYYY-MM-DD — <n> verified, <acc>%`.
   If no new matches were verified: no commit, finish with "nothing new".
