# Scoped loop — test coverage ONLY (Nemotron 3 Ultra, free)

You ONLY add tests. Your entire job: pick ONE under-tested module or behaviour and add a
focused test in `tests/`. **Touch nothing outside `tests/`.** One PR, then stop.

## Hard scope
- Edit/create files **only under `tests/`**. If a fix needs a `src/` change, DON'T do it —
  pick a different, already-correct behaviour to pin with a test, or open nothing.
- NEVER push to `main`, never merge, never commit secrets/personal data.

## Good targets (high value, currently thin)
- The **live path**: a smoke test that imports `src.live.inference` and asserts
  `load_resources()` returns the expected tuple shape (this class of breakage has hit us).
- `src/features` (ELO, player_stats), `src/betting/signals`, `src/models/backtest` helpers,
  `src/runtime_paths`, the dashboard API endpoints not yet covered.

## Steps
1. `git fetch origin && git switch --detach origin/main && git switch --create test/<short-desc>`.
2. Add ONE focused test that **passes** against current code (a regression guard, not a
   test of a bug). If it needs data that isn't in the checkout, mark it `@pytest.mark.slow`
   and `pytest.skip(...)` when the data file is absent (mirror the existing `tests/test_leakage.py` pattern).
3. `python -m pytest tests/ -q` must be green (2 `@slow` skips are expected).
4. Commit `test(<scope>): <summary>`; `gh pr create --base main`. Stop.
