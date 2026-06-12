# Weekly Evolution Runbook

**Schedule:** Sunday 09:23 CET (Windows Task Scheduler `scripts/loops/run_loop.ps1`)
**Log location:** `reports/loops/weekly_YYYY-MM-DD.log`

## Purpose

Run ONE experiment from `EXPERIMENTS.md` per week. The loop:
1. Reads the next unclaimed experiment
2. Implements minimal change
3. Evaluates (metrics + backtest)
4. Decides: KEEP (commit) or REVERT
5. Updates EXPERIMENTS.md with result

## Steps (from `scripts/loops/weekly_evolution.md`)

1. **Pre-flight** `pytest tests/test_leakage.py -v` must pass
2. **Read EXPERIMENTS.md** — find first unclaimed experiment (status: `PENDING`)
3. **Implement** — minimal change, single commit
4. **Evaluate** — `python -m src.models.train` + `python -m src.models.backtest`
5. **Compare** — metrics vs baseline (accuracy, LL, ROC, backtest ROI)
6. **Decision**:
   — **KEEP**: commit, update EXPERIMENTS.md status to `KEPT` with numbers
   — **REVERT**: `git reset --hard HEAD~1`, update status to `FAILED` with numbers
7. **Log** — append run summary to `reports/loops/weekly_YYYY-MM-DD.log`
8. **3 FAILED rule** — if 3 consecutive FAILED, STOP loop, write “LOOP FERMO” in log, alert human

## Experiment Format (in EXPERIMENTS.md)

```markdown
### E1: Serve-stats 2025-26 coverage
**Status:** PENDING
**Hypothesis:** Current-season serve stats will recover the 84% NaN gap
**Implementation:** Update data ingestion for current season
**Evaluation:** Model accuracy on 2025+ test
**Result:** KEPT/FAILED — accuracy X.XX% (baseline 66.3%)
```

## Safety Rules

— ❌ NO push to remote
— ❌ NO the-odds-api calls
— ❌ NO modify EXPERIMENTS.md queue order (only status field)
— ✅ Inference outside train.py = mediane train + scaler + prospettiva randomizzata
— ✅ If 3 consecutive FAILED → STOP, write “LOOP FERMO” in log, alert human

## Manual Test Run

```bash
# Dry-run: just read EXPERIMENTS.md and show next experiment
python -c "
import re
with open('EXPERIMENTS.md') as f:
    content = f.read()
import re
matches = re.findall(r'### (E\d+: .+?)\n\*\*Status:\*\* (PENDING)', content)
for m in matches[:1]:
    print(f'Next: {m[0]}')
"
```

## Troubleshooting

| Issue | Action |
|---|---|
| Pre-flight test fails | STOP — leak introduced, do not run experiment |
| Experiment implementation unclear | Mark as `BLOCKED`, ask human |
| Evaluation metrics worse | REVERT, log as FAILED |
| Git conflicts on commit | Resolve, re-run evaluation |
| 3 consecutive FAILED | Write “LOOP FERMO” in log, STOP |

