# Brief — opencode (code/architecture audit)

## Scope
Audit completo del progetto ML tennis betting. **Solo lettura + produzione documento.**

## Output richiesto
File: `G:\tennis betting\ANALYSIS_OPENCODE.md`

Sezioni obbligatorie:
1. **Architettura** — moduli `src/{data,features,models,betting,live,ui}`, dipendenze, accoppiamento
2. **Code quality** — code smell, duplicazioni, dead code, pattern problematici
3. **Performance** — bottleneck I/O, vettorizzazione mancante, caching, memory
4. **Testing** — copertura, mock, integration vs unit
5. **Sicurezza** — gestione segreti, API key, input validation (vedi `.env.example` se esiste)
6. **Top 10 issue** — ordinati per severità (critical/high/medium/low) con file:line e fix proposto
7. **Roadmap sviluppo** — 5 proposte concrete prioritizzate (ROI sviluppo vs valore)

## Vincoli HARD
- **NON eseguire** `git commit`, `git push`, `gh pr create`
- **NON modificare** file sorgente — solo creare `ANALYSIS_OPENCODE.md`
- **NON installare** dipendenze
- **NON eseguire** training / backtest / scraping (costoso)
- **OK** leggere file, eseguire `python -c "import ast"` per analisi statica, `pytest --collect-only`

## File chiave da analizzare
- `src/features/build_features.py`, `src/features/elo.py`, `src/features/sota_features.py`
- `src/models/train.py`, `src/models/cross_validate.py`, `src/models/predict_live.py`
- `src/betting/backtest.py`, `src/betting/portfolio.py`
- `src/data/clean.py`, `src/data/scraper.py`
- `src/live/` (tutti)
- `src/ui/` (tutti)
- `requirements.txt`, `setup.py`, `CLAUDE.md`

## Tono
Critico tecnico, no fluff. Cita file:line. Diff snippet quando proponi fix.
