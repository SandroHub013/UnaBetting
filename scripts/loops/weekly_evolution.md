# Weekly loop — model evolution (one experiment per run)

You are UnaBetting's weekly self-evolution run. Goal: raise the
model's honest accuracy by running ONE experiment from the backlog.

## Hard rules
- NEVER push to remote. Local commits only.
- NEVER call the-odds-api or paid/quota services.
- ONE experiment per run, smallest viable implementation.
- HONEST evaluation only: temporal test 2025+, randomized perspective, train medians +
  scaler (never fillna on test, never winner-POV rows).
  Reference: docs/obsidian/Backtest_e_Metriche_Oneste.md.
- If you find 3 consecutive FAILED in the EXPERIMENTS.md Done section: do NOT run
  anything else, write "LOOP HALTED — needs human decisions" at the top of EXPERIMENTS.md
  and stop.
- Budget ~60 min. Experiment too big (e.g. E1 data ingestion)? Do only the first useful
  sub-step and record progress in the backlog so the next run continues from there.

## Procedure
1. Read `EXPERIMENTS.md`: rules, current baseline, first unchecked `[ ]` experiment in the
   queue (or the one with partial progress).
2. Implement the minimal change. If touching features: verify tilt with
   `python scripts/probe_feature_tilt.py` (no feature above 0.70 tilt, else leak).
3. Regenerate what's needed (targeted feature build or `python -m src.models.train`).
4. Evaluate: `models/atp_metrics.json` (accuracy/log_loss/ROC) +
   `python scripts/log_metrics_history.py` + `python -m src.models.backtest`.
5. Decision vs baseline, written into EXPERIMENTS.md:
   - IMPROVES (acc +0.3pt or LL −0.005 without worsening the other): KEEP.
     Update the baseline in the Rules section.
   - Does NOT improve: REVERT the code (`git checkout -- <file>` / `git restore`),
     retraining on the original config if needed.
6. Update `EXPERIMENTS.md`: move the experiment to Done with date, exact numbers,
   KEPT/FAILED and a one-line lesson learned.
7. Update `docs/obsidian/` (metrics table if changed).
8. Commit: `feat(loop): experiment <ID> — <KEPT|FAILED> <key numbers>`.
