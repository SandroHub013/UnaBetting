# Experiment Backlog — accuracy roadmap

Brain of the self-evolving loop. The weekly evolution job picks the TOP unchecked
experiment, implements it, evaluates honestly (temporal test 2025+, perspective-
randomized, train medians + scaler), records the result here, keeps the change
only if it beats the baseline, then commits.

**Rules for the loop:**
- One experiment per run. Smallest viable implementation.
- Baseline to beat (2026-06-09): ensemble acc 66.28% / LL 0.6080 / ROC 0.7312 (test 2025+).
- Evaluation = `models/atp_metrics.json` after `python -m src.models.train` + honest
  backtest `python -m src.models.backtest`. Log every result in `reports/metrics_history.csv`.
- If result worse: revert code, mark FAILED with the numbers, move on.
- After 3 consecutive FAILED: stop, write findings to docs/obsidian, wait for human.
- NEVER push to remote. NEVER touch live betting code (`src/betting/`) without human.

## Queue (priority order)

- [x] **E0 — Fix stale tests.** DONE 2026-06-11 via PR #1: test_player_stats &
  test_imputation_median_is_train_only now pass (feature names updated to
  form_ewm/decay_minutes_14d/days_since_last; synthetic frame got winner_id/
  loser_id; medians unpack made robust).
- [ ] **E0b — Fix test_shuffled_target_accuracy_is_chance.** Still fails on real
  data with `KeyError: 'target'` (separate from E0). prepare_training_data's
  return/columns changed; the test accesses y['target'] that no longer exists in
  that shape. Update the test to the current shuffle-guard contract.
- [ ] **E1 — Serve-stats coverage 2025-26.** `_50` rolling serve/return features are
  84% NaN on the test years (Sackmann lags current season) — the model flies blind
  exactly where it predicts. Ingest current-season match stats (Sackmann repo pull
  via `update_data.py`, or ATP site) and rebuild features. Expected: biggest single
  gain; legit ceiling ~ROC 0.80 / acc ~70-72% per walk-forward 2026 fold.
- [ ] **E2 — Walk-forward ensemble weighting.** PreFittedEnsemble is a flat mean;
  weight members by validation log-loss (softmax over -LL). Cheap, +0.1-0.3pt typical.
- [ ] **E3 — XGB calibration regression.** XGB LL degraded 0.61→0.66 with val=[2024]
  only (isotonic on a single year overfits). Try sigmoid calibration or val=[2023,2024]
  for calibration while keeping train≤2023 for fitting.
- [ ] **E4 — Odds-segment specialist.** Train a separate model on has_odds==1 rows
  (market features real) vs blind model for no-odds rows; route at inference.
- [ ] **E5 — Surface-specific ELO K tuning.** Optuna over k_factor/decay per surface,
  objective = test-year-free walk-forward LL (use cross_validate.py, NOT the 2025 test).
- [ ] **E6 — Fatigue interactions v2.** `decay_minutes_14d` × best_of_5, days_since_last
  × age. Verify tilt stays <0.70 (scripts/probe_feature_tilt.py) before training.
- [ ] **E7 — WTA pipeline parity.** Same features/training for WTA (config exists);
  doubles the prediction surface for the spread/CLV strategy direction.

## Done

- [x] **2026-06-09 — train≤2023 + has_odds flag** (was train≤2022, no flag).
  Result: ~flat. ensemble 66.58→66.28 acc, LL 0.6082→0.6080, ROC 0.7291→0.7312;
  LightGBM single best 66.98 (+0.27). KEPT (fresher params, cleaner market signal,
  no regression on the headline LL/ROC). Lesson: split refresh alone doesn't move
  accuracy; data coverage (E1) is the lever.
