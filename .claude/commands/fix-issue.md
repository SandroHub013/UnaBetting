---
description: Analyzes and resolves a specific bug or console error provided by the user.
---

# Command: /project:fix-issue

When investigating a bug or an anomaly, follow this structured troubleshooting procedure:

1. **Context Analysis:** Ask for full stack traces or logs if they are not provided. Do not guess the root cause without evidence.
2. **Root Cause Identification:** Trace the execution path to isolate the faulty module, function, or configuration.
3. **Impact Assessment:** Consider edge cases and how the proposed fix might impact other parts of the system.
4. **Actionable Fix:** Produce a clear explanation of the problem and provide the exact code changes required to resolve the issue. If tests are missing, suggest adding them to prevent regressions.
