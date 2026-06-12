# On-Call Playbook

**When to use:** Metrics degrade, dashboard alerts, or loop failures.

## Quick Triage (5 min)

1. **Check loop logs** → `reports/loops/` (latest `.log`)
2. **Run anti-leak test** → `pytest tests/test_leakage.py -v`
   - If FAILS: **STOP** — leak introduced. Revert recent changes.
3. **Check git log** → `git log --oneline -10` on nikomatt69-main
4. **Check dashboard** → `python -m src.dashboard --server-only` + `curl /api/overview`

## Common Scenarios

### Accuracy drop > 1pt (e.g. 66.3% → 65.0%)
1. Recent changes to `src/models/`, `src/features/`, `src/data/`?
2. Run `probe_feature_tilt.py` → find leaky feature
3. If leak: revert commit, add regression test
4. If no leak: may be data drift (new season), document in EXPERIMENTS.md

### Backtest ROI crash (e.g. −11.9% → −50%)
1. Check `models/atp_metrics.json` for calibration drift (ECE spike)
2. Check `config.yaml` betting params unchanged
3. Verify `backtest.py` uses real B365 odds (not fair odds)
4. If odds source changed: check `scraper.py` allowlist

### Dashboard shows stale data
1. `data/betanalytix.db` locked? → check WAL files (`-shm`, `-wal`)
2. FastAPI server running? → `netstat -an | findstr 8765`
3. SQLite read-only mode OK? → `file:...?mode=ro`

### Loop failed (nightly/weekly)
1. Check `reports/loops/latest.log` for error
2. If `LOOP FERMO` written → 3 consecutive FAILED, manual intervention needed
3. Fix root cause, delete `LOOP FERMO` marker, re-trigger

## Escalation

| Severity | Action | Timeline |
|---|---|---|
| P0 (leak, data loss) | Revert immediately, alert owner | < 1 hour |
| P1 (accuracy ≥2pt drop) | Investigate, revert if needed | < 4 hours |
| P2 (dashboard down) | Restart server, check DB | < 2 hours |
| P3 (loop stuck) | Clear marker, re-trigger | < 24 hours |

## Contacts

- Owner: Sandro (@SandroHub013)
- GitHub Issues: use `leak_incident.md` template

