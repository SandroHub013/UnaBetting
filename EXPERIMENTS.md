# Experiment Backlog — accuracy roadmap

Brain of the self-evolving loop. The weekly evolution job picks the TOP unchecked
experiment, implements it, evaluates honestly (temporal test 2025+, perspective-
randomized, train medians + scaler), records the result here, keeps the change
only if it beats the baseline, then commits.

**Rules for the loop:**
- One experiment per run. Smallest viable implementation.
- Baseline to beat (2026-06-12, after E2+E3+E4, NaN-fix in E1): routed acc **~67.5%**
  / LL **~0.601** / ROC **~0.740** (test 2025+); odds-ensemble ~69.7% on real-odds
  rows. Treat the bar as a band ±0.7pt SE (≈4000 test matches) — a single run inside
  it is NOT a gain. Latest run: 67.36 / 0.6006 / 0.7398. Prior 66.28 / 0.6080 / 0.7312
  (2026-06-09).
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
- [x] **E0b — Fix test_shuffled_target_accuracy_is_chance.** DONE 2026-06-12.
  Root cause: prepare_training_data returns a 13-tuple (X/P/y per split + scaler/
  features/medians/player_mapping) and three tests still unpacked the old shape —
  the shuffle test read P_train (player ids) as y and hit `KeyError: 'target'`;
  test_no_nan_after_imputation silently checked the WRONG frames (y_train/P_val
  instead of X_val/X_test) and passed vacuously. All three unpackings aligned to
  the contract; the no-NaN test now genuinely covers X_val/X_test (passes).
  Caveat: the two @slow tests still need the real features dataset to execute.
- [x] **E1 — Serve-stats coverage.** DONE + **FALSIFIED 2026-06-12.** The premise
  ("Sackmann lags 2025, 84% NaN") was WRONG: raw serve stats are 94-98% present for
  2021-2025 (only the in-progress 2026 is sparse). The real cause of the ~53% NaN on
  the `_50` serve features was a **NaN-poison bug** in `player_stats.py`:
  `sum(m.get(k,0) or 0 ...)` — `np.nan or 0` returns `np.nan` (NaN is truthy), so a
  single stat-less match in a 50-match window poisoned the whole sum (~95% hit rate).
  Fixed with a NaN-safe `_num()` coercion → `_50` NaN dropped 53% → **1.8%**.
  **Result: accuracy NEUTRAL** (routed 67.66 → 67.36, within ±0.7pt SE; LL 0.6010 →
  0.6006; ROC flat; backtest ROI −61.9% → −57.4%, still no edge). **Lesson: Elo +
  market odds already encode serve strength; explicit serve splits are redundant —
  serve coverage is NOT the accuracy lever.** Bug fix KEPT (correct code); hypothesis
  rejected.
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
