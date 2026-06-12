---
description: Analyzes and resolves a specific bug or console error provided by the user.
---

# Command: /fix-issue

When investigating a bug or an anomaly in this repo:

1. **Reproduce first:** run the failing path with the project venv
   (`.venv/bin/python -m …`). Missing-data crashes are common on fresh clones —
   check `data/features/`, `models/*.pkl`, and `data/raw/TML-Database/` before
   assuming a code bug.
2. **Root cause, not symptom:** trace the execution path to the faulty module;
   don't guess without a stack trace or log.
3. **Impact:** consider both platforms (Windows desktop app, Linux/macOS
   `--browser`/`--server-only`) and whether the fix touches the leak-free rules
   in CLAUDE.md.
4. **Fix + regression test:** land the smallest correct change with a test in
   `tests/` that fails before and passes after. Run the full suite.
