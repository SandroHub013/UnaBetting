# Disaster Recovery Playbook

**When to use:** DB corruption, .env loss, model artifact loss, config corruption.

## Scenario 1: SQLite DB Corruption (`betanalytix.db`)

### Symptoms
- `sqlite3.DatabaseError: database disk image is malformed`
- Dashboard shows 0 bets/decisions
- `BetAnalytix` methods raise `sqlite3.OperationalError`

### Recovery
1. **Stop dashboard** → kill FastAPI process
2. **Backup corrupted DB** → `cp data/betanalytix.db data/betanalytix.db.corrupted.$(date +%s)`
3. **Check WAL files** → if `.db-shm` and `.db-wal` exist, try:
   ```bash
   sqlite3 data/betanalytix.db ".backup data/betanalytix.db.recovered"
   ```
4. **If backup fails** → reconstruct from `reports/metrics_history.csv` and `data/live/signals_log.csv`:
   - Decisions → from signals_log.csv (has scan_id, match, odds, edge, etc.)
   - Bets → from manual records or re-run inference
5. **Verify** → `python -c "from src.betting.portfolio import BetAnalytix; db=BetAnalytix(); print(db.get_bankroll())"`

## Scenario 2: .env File Lost (API Keys)

### Symptoms
- `src.data.scraper` fails with `ODDS_API_KEY not set`
- `src.live.agentic_research` fails with `OPENROUTER_API_KEY not set`

### Recovery
1. **DO NOT** create new keys in panic
2. **Retrieve from password manager** (1Password / Bitwarden / OS keychain)
3. **Recreate .env**:
   ```bash
   cat > .env << 'EOF'
   ODDS_API_KEY=your_key_from_vault
   OPENROUTER_API_KEY=your_key_from_vault
   EOF
   ```
3. **Verify** → `python -c "from src.data.scraper import fetch_all_tennis_odds; print('OK')"`

## Scenario 3: Model Artifacts Lost/Corrupted

### Symptoms
- `FileNotFoundError: atp_target_xgboost.pkl`
- `joblib.UnpicklingError` on load
- Metrics missing in `models/atp_metrics.json`

### Recovery
1. **Check git history** → `git log --oneline models/`
2. **Restore from last known-good commit**:
   ```bash
   git checkout <last-good-commit> -- models/
   ```
3. **If no commit has models** → full retrain:
   ```bash
   python -m src.features.build_features
   python -m src.models.train
   python -m src.models.backtest
   ```
4. **Verify** → `cat models/atp_metrics.json`

## Scenario 4: Config.yaml Corrupted

### Symptoms
- YAML parse error on startup
- Missing sections causing defaults to apply silently

### Recovery
1. **Backup corrupted** → `cp config/config.yaml config/config.yaml.corrupted`
2. **Restore from git** → `git checkout HEAD -- config/config.yaml`
3. **If no git history** → recreate from `config/config.yaml.example` (if exists) or manual rebuild
4. **Validate** → `python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"`

## Scenario 5: Branch Accidentally on main

### Symptoms
- `git branch --show-current` shows `main`
- Safety check fails: `bash scripts/ci/safety_check.sh check` exits 1

### Recovery
1. **DO NOT** `git push --force` to main
2. **Create rescue branch** → `git branch rescue`
3. **Switch to working branch** → `git checkout nikomatt69-main`
4. **Fast-forward merge** → `git merge --ff-only rescue`
5. **Push working branch** → `git push origin nikomatt69-main`
6. **On GitHub UI**: delete the accidental commit on main (or ask owner)

## Verification Checklist (after any recovery)

- [ ] `pytest tests/test_leakage.py -v` passes
- [ ] `python -m src.dashboard --server-only` starts
- [ ] `curl -f http://127.0.0.1:8765/api/overview` returns 200
- [ ] `python scripts/audit/check_module_order.py` clean
- [ ] `ruff check src/` clean
- [ ] `bandit -r src/` no high/medium

