# 0001 — Pipeline stages hand off through files on disk

**Status:** accepted

## Context

The pipeline is five stages long — download, clean, build features, train,
backtest — and one of them, `build_features`, takes about twenty minutes on the
full ATP history. The stages are also not run together in practice: the nightly
loop retrains without re-downloading, an experiment re-runs training against
untouched features, and the desktop app exposes each stage as its own button.

The obvious alternative was an in-memory pipeline object that carries frames from
stage to stage in one process.

## Decision

Every stage ends by writing an artifact and the next stage begins by reading it.
The artifacts are the contract:

```
data/raw/**  →  data/processed/*_unified.csv  →  data/features/*_features.csv
             →  models/*.pkl + models/atp_metrics.json
```

No stage imports another stage's internals. A stage is a module you can run with
`python -m`, and its output is a file you can open.

## Consequences

**What it buys.** When a metric moves, the artifact can be diffed and the stage
that moved it identified — with an in-memory pipeline the same investigation is a
debugger session. Twenty minutes of feature building is paid once. Each stage is
independently runnable, which is what lets the whitelist in
[0004](0004-the-runner-takes-a-name.md) expose eight named commands instead of
one opaque "run everything", and what lets a scheduled loop retrain nightly
without touching the network.

**What it costs, and this is real.** The artifacts are not versioned against the
code that produced them. A stale `*_features.csv` sitting next to a rewritten
`build_features.py` will train happily and report numbers that describe neither
version. This has already bitten: on 2026-06-12, E2/E3/E4 had been merged but
never retrained, and stale pre-E2 pickles broke inference for a day
(`EXPERIMENTS.md`, "a merged experiment is NOT a verified one").

The mitigation is that `models/atp_metrics.json` carries each run's numbers and
`reports/metrics_history.csv` carries the history, so a claim can be traced to a
run. That is a mitigation, not a fix. A content hash of the inputs written beside
each artifact would be the fix, and it has not been done.
