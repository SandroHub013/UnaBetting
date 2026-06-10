# Brief — hermes (ML/data/strategy audit)

## Scope
Audit ML pipeline + strategia betting. **Solo lettura + produzione documento.**

## Output richiesto
File: `/mnt/g/tennis betting/ANALYSIS_HERMES.md` (Windows: `G:\tennis betting\ANALYSIS_HERMES.md`)

Sezioni obbligatorie:
1. **Data integrity** — leakage temporale, look-ahead bias, target leakage in feature engineering, gestione NaN
2. **Feature engineering** — qualità ELO (K-factor, time decay, surface), rolling stats, sota_features, clutch
3. **Modeling** — split temporale, walk-forward CV, calibrazione probabilità, ensemble, hyperparameter tuning
4. **Backtest realismo** — slippage, commissioni, esecuzione quote chiusura vs apertura, sample bias
5. **Bankroll/staking** — Kelly fraction, edge stimato, varianza, drawdown
6. **Edge probabilistico** — confronto con mercato (overround removal), value bet detection, ROI atteso
7. **Top 10 issue ML/strategia** — severità + fix
8. **Roadmap ML/strategy** — 5 proposte ordinate per impatto su ROI atteso

## Vincoli HARD
- **NON eseguire** `git commit`, `git push`, `gh pr create`
- **NON modificare** file sorgente — solo creare `ANALYSIS_HERMES.md`
- **NON installare** dipendenze, **NON** training pesante
- **OK** leggere file, ispezionare CSV (head/describe), eseguire script di analisi statica leggera

## File chiave
- `src/features/elo.py` — ELO custom: verifica leakage, init values, K-factor
- `src/features/build_features.py` — pipeline feature, rolling windows, shift correctness
- `src/features/sota_features.py`, `src/features/clutch.py`, `src/features/player_stats.py`
- `src/models/train.py` — split, target encoding, fit/predict separation
- `src/models/cross_validate.py` — walk-forward setup
- `src/betting/backtest.py` — execution model
- `src/betting/portfolio.py` — staking
- `forensic_leak_check.py`, `verify_rolling_leak.py`, `feature_audit.py`, `data_quality_audit.py` — script audit esistenti, USA come reference

## Tono
Critico ML, focus su rigore statistico. Numeri concreti dove possibile.
