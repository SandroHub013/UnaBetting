# 0007 — Two model families, routed at inference on `has_odds`

**Status:** accepted (verified 2026-06-12)

## Context

De-vigged market probability is by far the strongest single feature the pipeline
has — the bookmakers' consensus already encodes most of what ELO, form and serve
statistics are trying to reconstruct. But it is not always there. Historical rows
without odds coverage and matches that have not been priced yet have no market
feature at all.

One model over both populations has to choose a bad option: impute the missing
market probability, which invents a consensus that never existed, or drop the
feature for everyone, which throws away the best signal on the rows that have it.

## Decision

Train two families and route between them at inference on the `has_odds` flag:

- **`odds`** — trained on real-odds rows, with the market features.
- **`blind`** — trained without market features, for rows that have no price.

Each family is separately calibrated (sigmoid/isotonic per model, E3) and
ensembled with softmax weights over negative validation log-loss (E2, E4).

## Consequences

**What it buys**, measured against the 2026-06-09 baseline on the 2025+ test set:
routed accuracy 66.28% → 67.66% (+1.38 points), log loss 0.6080 → 0.6010, ROC
0.7312 → 0.7397. On real-odds rows alone the odds ensemble reached 69.85%
accuracy — above the naive favourite (67.7%) for the first time in this project.

**What it costs.** Two families is two of everything: two training paths, two
calibration steps, two sets of pickles, and a routing rule that must agree with
the flag the feature builder wrote. It also doubles the surface for the staleness
problem in [0001](0001-files-as-the-pipeline-seam.md) — and that is not
hypothetical. E2/E3/E4 were merged and then not retrained for a day, and the
stale pre-E2 pickles broke inference outright.

**What it does not buy, and this is the point.** The honest backtest still loses:
ROI −82.4% → −61.9%, win rate 45.6%. More accurate is not more profitable. The
model carries the market probability as a feature, so the matches where it
*disagrees* with the market are exactly the matches where it is betting against
the thing that was informing it — and those disagreements still lose to the vig.
The "no predictive edge" verdict in the README stands after this change; it is
just less bad. Recording that here is the reason this file exists.
