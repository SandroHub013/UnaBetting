---
description: Performs an in-depth code review of the current code or diff.
---

# Command: /review

Review the current diff as a senior engineer of THIS repo:

1. Run `python -m pytest tests/ -q` — must be green (2 `@slow` skips are expected
   without the real dataset).
2. If the diff touches `src/features/`, `src/models/` or evaluation: enforce the
   leak-free rules in CLAUDE.md (temporal split, perspective randomization + pairs,
   train-only medians, tilt probe) and require before/after train+backtest numbers.
3. Cross-platform: `pathlib`, guarded OS-specific imports, explicit UTF-8 IO —
   Windows and Linux/macOS must both keep working.
4. Security quick-pass: no secrets or personal data in the diff, `_safe_path` for
   file endpoints, the in-app LLM tool whitelist unchanged.
5. Deliver findings as concrete bullets with `file:line` and proposed code.
