# Scoped loop — documentation ONLY (Nemotron 3 Ultra, free)

You ONLY improve documentation. Pick ONE doc gap and fix it. **Touch nothing outside
`docs/`, `*.md`, and the website under `docs/web/`.** One PR, then stop. No code, no tests.

## Hard scope
- Edit/create only: `docs/**`, `README.md`, `CONTRIBUTING.md`, `docs/web/**` (deep-dive
  `docs.html` content, Obsidian vault pages). **Never** touch `src/`, `tests/`, `scripts/`.
- Keep it **factual and English**. Do not invent metrics — if you cite a number, it must
  come from `models/atp_metrics.json`, `reports/last_backtest.json`, or `docs/web/metrics.js`.
- NEVER push to `main`, never merge, never commit secrets/personal data.

## Good targets
- Fill thin sections of the Docs deep-dive (`docs/web/docs.html`): architecture, the live
  scan, CLV, the loops. Expand Obsidian pages. Fix stale/inaccurate statements. Improve
  the README where it's vague. Keep the honest-no-edge framing intact (no marketing spin).

## Steps
1. `git fetch origin && git switch --detach origin/main && git switch --create docs/<short-desc>`.
2. One self-contained doc improvement. Verify any number against the sources above.
3. Commit `docs(<area>): <summary>`; `gh pr create --base main`. Stop.
