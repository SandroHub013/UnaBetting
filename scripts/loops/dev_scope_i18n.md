# Scoped loop — UI translations ONLY (nex-n2-pro, free)

You ONLY complete UI translations. The app's strings live in the `I18N` dictionary in
`src/dashboard/static/app.js` (and language docs). Pick ONE gap — a key present in `en`
but missing/empty in another supported language, or a hardcoded English string that
should go through `t()` — and fix it. **Touch only `src/dashboard/static/app.js`** (plus
a docs note if needed). One small PR, then stop.

## Hard scope
- Edit only `src/dashboard/static/app.js` (the `I18N` map / `t()` usage). Do NOT change app
  logic, only translation strings. Keep it valid JS.
- Match an existing translated key as the template; translate faithfully and concisely.
- NEVER push to `main`, never merge, never commit secrets/personal data.

## Steps
1. `git fetch origin && git switch --detach origin/main && git switch --create i18n/<short-desc>`.
2. Add the missing translation(s) for ONE key (or route ONE hardcoded string through `t()`).
3. `node --check src/dashboard/static/app.js` must pass (don't break the JS) and
   `python -m pytest tests/ -q` must be green.
4. Commit `feat(dashboard): i18n <lang/area>`; `gh pr create --base main`. Stop.
