# Experiment Backlog — accuracy roadmap

Brain of the self-evolving loop. The weekly evolution job picks the TOP unchecked
experiment, implements it, evaluates honestly (temporal test 2025+, perspective-
randomized, train medians + scaler), records the result here, keeps the change
only if it beats the baseline, then commits.

**Rules for the loop:**
- One experiment per run. Smallest viable implementation.
- Baseline to beat (2026-06-12, after E2+E3+E4): routed acc **67.66%** / LL **0.6010** /
  ROC **0.7397** (test 2025+); odds-ensemble 69.85% on real-odds rows. Prior baseline
  was 66.28% / 0.6080 / 0.7312 (2026-06-09).
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
- [x] **E2 — Walk-forward ensemble weighting.** DONE (PR #2). Softmax over -val-LL.
  Folded into the E4 retrain below.
- [x] **E3 — Per-model calibration.** DONE. Sigmoid/isotonic per model. Folded into E4.
- [x] **E4 — Odds-segment specialist.** DONE + **VERIFIED 2026-06-12** (was merged but
  never retrained until now — see lesson). Separate `odds` (market features, real-odds
  rows) and `blind` (no market features, no-odds rows) families, routed at inference by
  `has_odds`. **KEPT.**
- [ ] **E5 — Surface-specific ELO K tuning.** Optuna over k_factor/decay per surface,
  objective = test-year-free walk-forward LL (use cross_validate.py, NOT the 2025 test).
- [ ] **E6 — Fatigue interactions v2.** `decay_minutes_14d` × best_of_5, days_since_last
  × age. Verify tilt stays <0.70 (scripts/probe_feature_tilt.py) before training.
- [ ] **E7 — WTA pipeline parity.** Same features/training for WTA (config exists);
  doubles the prediction surface for the spread/CLV strategy direction.

## Done

- [x] **2026-06-12 — E2+E3+E4 verified (KEPT).** Merged earlier but NEVER retrained
  until a manual run on 2026-06-12 (the Nightly loop that would have caught this is
  paused). Numbers vs the 06-09 baseline:
  - routed acc **66.28% → 67.66%** (+1.38pt), LL 0.6080 → **0.6010**, ROC 0.7312 → **0.7397**.
  - odds-ensemble on real-odds rows: acc **69.85%**, LL 0.583, ROC 0.758 — for the first
    time ABOVE the naive favourite (67.7%).
  - **Honest backtest still LOSES: ROI −82.4% → −61.9%** (win rate 45.6%). More accurate
    ≠ profitable: the model carries the market prob as a feature, so its betting
    disagreements still lose to the vig. The "no predictive edge" verdict stands — just
    less bad.
  - Two bugs fixed during verification: `PreFittedEnsemble.__module__` hack broke
    pickle saving under `python -m` (aliased the running module instead);
    `log_metrics_history.py` made schema-tolerant (routed_*); `backtest.py` now loads
    the odds-ensemble.
  - **Lesson: a merged experiment is NOT a verified one.** With Nightly paused, E2/E3/E4
    sat unevaluated for a day and even broke inference (stale pre-E2 pickles).
    Re-enable Nightly, or have PR-review require before/after numbers from a retrain.

- [x] **2026-06-09 — train≤2023 + has_odds flag** (was train≤2022, no flag).
  Result: ~flat. ensemble 66.58→66.28 acc, LL 0.6082→0.6080, ROC 0.7291→0.7312;
  LightGBM single best 66.98 (+0.27). KEPT (fresher params, cleaner market signal,
  no regression on the headline LL/ROC). Lesson: split refresh alone doesn't move
  accuracy; data coverage (E1) is the lever.
