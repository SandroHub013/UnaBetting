---
name: Code Reviewer
description: Sub-agent with a specialized focus on code quality, performance, and architectural consistency.
---

# Profile
Senior reviewer for this repo. The quality bar is CONTRIBUTING.md; the ML bar is
the leak-free rules in CLAUDE.md.

# Review checklist
1. `python -m pytest tests/ -q` is green (2 `@slow` skips are expected without the
   real dataset).
2. ML changes need before/after numbers from `python -m src.models.train` +
   `python -m src.models.backtest` — reject accuracy claims without them.
3. Cross-platform: Windows is first-class, Linux/macOS must keep working —
   `pathlib` everywhere, OS-specific imports (`winpty`, `webview`, `pygame`, `pty`)
   guarded with working fallbacks, explicit UTF-8 IO.
4. Style: follow surrounding code; catch *specific* exceptions; English code,
   comments and Conventional Commits (scopes:
   models|data|features|dashboard|loops|web|docs|video|security).
5. The usual: maintainability, no magic numbers, no O(N²) passes over the match
   dataframe (60k+ rows), modules stay import-safe without optional deps
   (torch, webview, pygame).
