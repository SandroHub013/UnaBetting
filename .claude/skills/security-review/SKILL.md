---
name: security-review
description: Project-specific security pass — secrets, personal data, path traversal, LLM tool whitelist.
---

Run these checks on the pending diff/branch, in order:

1. **Secrets** — scan the diff for `github_pat_`, `sk-`, API key values, `.env`
   content. `.env` itself must never be staged.
2. **Personal data** — `betanalytix.db*`, `reports/screenshots/`, `*.mp4` renders
   are gitignored; if one is tracked or staged, stop and flag it.
3. **Path traversal** — any endpoint that reads/writes files must go through
   `_safe_path` (`src/dashboard/data_api.py`); reject bypasses.
4. **Bind & exec surface** — the server binds 127.0.0.1 only (never 0.0.0.0);
   `/ws/run` stays whitelist-only; `/ws/term` is arbitrary-exec *by design* but
   must remain local-only.
5. **LLM tools** — any widening of the chat agent's tool list
   (`src/dashboard/chat.py`) needs explicit human sign-off.
6. **Git hygiene** — additive public pushes only; never force-push.

Report each finding as: file:line → severity → concrete fix. Sensitive findings
go in a private report, never a public issue.
