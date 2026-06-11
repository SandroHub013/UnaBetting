# Code review loop — models & system

You are UnaBetting's code-review run (G:\tennis betting). Goal: find bugs,
methodological weaknesses and CONCRETE improvement opportunities in the model and
system code, to reach better results.

## Rules
- NEVER push to remote. Local commits only.
- Do NOT change code in this run: produce the review; fixes go through the backlog
  (EXPERIMENTS.md) or the weekly_evolution loop.
- Exception: obvious zero-risk bugs (typo, broken import, broken test) — fix them
  immediately with a separate commit `fix(review): ...`.
- Budget ~60 minutes.

## Focus (rotate; pick the least recently covered area by reading reports/reviews/)
1. `src/models/` — train, backtest, cross_validate: residual leaks, calibration,
   splits, metrics.
2. `src/features/` — elo, player_stats, build_features: temporal correctness, NaN
   handling, unused features.
3. `src/betting/` + `src/live/` — signals, portfolio, inference: book allowlist
   consistency, edge cases, error handling.
4. `src/dashboard/` — endpoint security, WS robustness, JS quality.

## Output
- Write `reports/reviews/review_YYYY-MM-DD_<area>.md`: findings ordered by severity, each
  with file:line, problem, proposed fix, estimated impact.
- High-impact findings on accuracy/correctness ALSO go as `[ ]` experiments at the end of
  EXPERIMENTS.md (format E<n>).
- Update `docs/obsidian/Index.md` if structural problems emerge.
- Commit: `docs(review): code review — <area>, <n> findings`.
