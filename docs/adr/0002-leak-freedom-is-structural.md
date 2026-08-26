# 0002 — Leak-freedom is enforced at the seams, not by convention

**Status:** accepted

## Context

Three leaks have been found in this project's history, and every one of them
produced a number that looked like progress. That is the shape of the problem: a
leak does not raise an exception, it raises the accuracy. The raw match rows are
winner-perspective (`w_*` for the winner, `l_*` for the loser), so a pipeline
that forgets to randomize perspective is not slightly optimistic — it is reading
the label.

Two other paths lead to the same place. A random train/test split lets a 2026
match teach the model about a 2024 one. Medians computed over the whole dataset
carry the test window into training through imputation.

A convention ("remember to randomize") is not a defence against any of this,
because the failure mode is silence.

## Decision

Five invariants, each enforced somewhere a change has to pass through:

1. **Temporal split only.** `test_start_year` in `config/config.yaml`; train <
   validation < test. Never a random split.
2. **Perspective randomization** before any evaluation, in `src/models/train.py`.
3. **Train-only imputation.** Medians come from the train window and are carried
   forward; they are part of `prepare_training_data`'s return.
4. **Perspective pairs.** Every `w_X` feature must have its `l_X` twin, checked
   by `_enforce_perspective_pairs`. A one-sided feature is the label in disguise.
5. **A tilt probe on every new feature** — `scripts/probe_feature_tilt.py`. A
   single feature that predicts the winner above 70% is a leak, and it will look
   like a breakthrough.

And one rule about evidence: an accuracy claim needs before/after numbers from a
real `train` + `backtest` run, logged to `reports/metrics_history.csv`.

## Consequences

**What it buys.** The project can state a number and mean it. The README's
headline is that the model reaches ~67% accuracy *and loses money in an honest
backtest* — a claim only worth making if the evaluation is trusted, and one that
would have been quietly replaced by a better-looking lie under any of the three
leak paths above.

**What it costs.** `prepare_training_data` returns a thirteen-element tuple —
X/P/y per split, plus scaler, feature names, medians and player mapping — and
every caller has to unpack it correctly. It is awkward, and the awkwardness is
deliberate: it is the single point where the split separation is materialised,
and collapsing it into one object would make passing the wrong split easy. It has
already caught its own class of bug — on 2026-06-12 three tests were still
unpacking the old shape, one of them checking the wrong frames entirely and
passing vacuously.

The second cost is that experiments are slower. A feature cannot be judged by
running it; it has to be trained, backtested and compared against a baseline band
of ±0.7 points. E1 spent a full cycle to conclude that serve-stat coverage is
*not* the accuracy lever — a result worth having, and one that took a full
honest evaluation to reach.
