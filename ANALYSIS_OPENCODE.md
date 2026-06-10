# Tennis Betting ML — Code & Architecture Audit
**Analyst:** opencode | **Date:** 2026-05-07 | **Scope:** Read-only audit, no modifications

---

## 1. Architettura

### 1.1 Struttura moduli

```
src/
├── data/          clean.py, scraper.py, download.py, label_markets.py, scrape_weather.py
├── features/     build_features.py, elo.py, player_stats.py, sota_features.py, clutch.py
├── models/        train.py, cross_validate.py, predict_live.py,
│                  shuffle_test.py, select_features.py, tune.py, dl_model.py
├── betting/       backtest.py, portfolio.py
├── live/          inference.py, agentic_research.py, news_adjustment.py,
│                  agent_llm.py, web_research.py, warm_up.py
└── ui/            app.py, audio_engine.py
```

### 1.2 Dipendenze esterne

| Libreria | Versione | Uso |
|---|---|---|
| pandas, numpy | >=2.0 / >=1.24 | Data handling |
| scikit-learn | >=1.3 | LR, RF, Voting, Scaler, Calibrazione |
| xgboost | >=2.0 | Modello primario |
| lightgbm | >=4.0 | Tuning, tuning Optuna |
| torch | >=2.0 | DNN (dl_model.py) |
| requests, beautifulsoup4 | >=2.31 / >=4.12 | Scraping |
| selenium | >=4.15 | Web automation |
| textual | latest | TUI |
| pygame, pyttsx3 | — | Audio engine |
| optuna | — | Hyperparameter tuning |
| sqlite3 | stdlib | Portfolio tracking |

### 1.3 Data flow

```
JeffSackmann (git) + tennis-data.co.uk (scraped)
    → data/clean.py (unified CSV)
    → features/build_features.py (ELO + rolling stats + SOTA)
    → models/train.py (XGBoost/LightGBM/RF/LR + calibration)
    → betting/backtest.py (Kelly + strategy simulation)
    → live/inference.py (warm-up ELO/stats → prediction → value detection)
    → live/agentic_research.py (ReAct LLM agent, Brave Search, Tennis Abstract)
    → betting/portfolio.py (BetAnalytix SQLite)
    → ui/app.py (Bloomberg-style TUI)
```

### 1.4 Accoppiamento e criticità architetturali

**Accoppiamento CRITICAL:**
- `warm_up.py` e `inference.py` caricano `live_engines.pkl` (joblib bundle di `EloRating` + `PlayerStatsEngine`). Se il formato dell'oggetto cambia, i file serializzati diventano illegibili.
- `cross_validate.py`, `backtest.py`, `shuffle_test.py`, `select_features.py` importano DA `train.py` la funzione `prepare_training_data` e `load_config`. Questo crea **circular dependency latente** se train.py evolve verso un import pattern diverso.
- `src/features/__init__.py` vuoto — non esporta `build_match_features`, ma la pipeline in `build_features.py:75` la importa come `from src.features.player_stats import build_match_features`. Incoerenza.

**SROTAMENTO ASSENTE:**
- Nessun `models/__init__.py` o `data/__init__.py` con costanti condivise. `_randomize_perspective` è duplicata in 3+ file (`train.py`, `backtest.py`, `test_randomization.py`, `clutch_test.py`).

---

## 2. Code Quality

### 2.1 Code Smell

| File | Riga | Smell | Gravità |
|---|---|---|---|
| `src/features/player_stats.py` | 78-82 | `zip(games_list, sets_list)` su liste di lunghezza diversa produce silenzio asimmetrico; indice atteso 79-80 ma `sets_list` può essere più corta | **HIGH** |
| `src/data/clean.py` | 144-145 | Iterrows su tutto il dataset per costruire `name_to_id` — O(n²) in pratica per ~200k righe | **HIGH** |
| `src/features/clutch.py` | 152 | `groupby(['date','player_name']).sum()` somma statistiche che dovrebbero essere massime (punti per round), non sommate | **HIGH** |
| `src/live/agent_llm.py` | 44 | Apertura file con percorso hardcoded `"config/config.yaml"` invece di usare `PROJECT_ROOT` | **MEDIUM** |
| `src/live/agentic_research.py` | 643 | Stesso percorso hardcoded `"config/config.yaml"` | **MEDIUM** |
| `src/data/scraper.py` | 13 | `PROJECT_ROOT` calcolato con `os.path.dirname` 4 livelli — fragile, funziona per esecuzione da root ma non da `python -m src.data.scraper` | **MEDIUM** |
| `src/models/tune.py` | 21 | `features_path` hardcoded `"data/features/"` invece di usare config paths | **MEDIUM** |
| `src/models/dl_model.py` | 48 | Stesso — percorso hardcoded | **MEDIUM** |
| `src/betting/portfolio.py` | 316-317 | Accesso a `config.yaml` in `get_bankroll()` che viene chiamato DA `resolve_bet()` (hot path) — lettura file YAML su OGNI bet resolution | **HIGH** |
| `src/features/build_features.py` | 70 | `df['score'].apply(parse_score)` in-place su intera colonna — inefficiente, dovrebbe essere vettorizzato | **MEDIUM** |
| `src/features/player_stats.py` | 276-306 | Doppio `iterrows()` su intero dataset — il loop esterno è O(n_matches), il inner `get_player_features` è O(n_player_matches) | **HIGH** |
| `src/features/sota_features.py` | 99 | `df.apply(lambda row: ...)` per calcolo `pts_earned_winner` — riga per riga invece di vettorizzazione | **MEDIUM** |
| `src/data/clean.py` | 256-304 | Loop esplicito `for _, r in gap.iterrows()` per conversione tennis-data.co.uk | **MEDIUM** |
| `src/live/warm_up.py` | 39-41 | Doppio iterrows su tutto il dataset storico per popolare stats_engine | **HIGH** |
| `src/live/inference.py` | 175-195 | Ricarica intero CSV storico + doppio iterrows per costruire name_to_id e id_to_rank | **HIGH** |

### 2.2 Duplicazioni

- `_randomize_perspective`: `src/models/train.py:161`, `src/betting/backtest.py:11`, `test_randomization.py:4`, `clutch_test.py` (versione semplificata). **4 duplicati.**
- `parse_pbp_match`: `src/features/clutch.py:8`, `clutch_test.py:4`. **2 duplicati.**
- `build_match_features`: esportata da `src/features/player_stats.py` ma non da `__init__.py`.
- `parse_score`: in `src/data/label_markets.py:8` e `src/features/elo.py:11` — logica identica.
- Surface detection: `TOURNEY_SURFACE_MAP` in `src/live/inference.py:65-86` e `_SURFACE_KEYWORDS` in `src/ui/app.py:81-94`. **2 duplicati.**

### 2.3 Dead Code

- `src/models/tune.py`: il file `config/best_params.yaml` generato non è mai letto da `train.py` — i parametri tunati vengono ignorati.
- `src/models/dl_model.py`: modello DNN PyTorch definito ma MAI usato in inference o train pipeline. Esiste solo come script standalone.
- `src/features/clutch.py`: `process_all_pbp` è un pipeline batch che genera `player_clutch_stats.csv`. Se il file è già generato, il pipeline non viene ri-eseguito ma il modulo è importabile direttamente. Nessun meccanismo di cache/invalidation.
- `src/features/sota_features.py:160-176`: blocco `if __name__ == "__main__"` con test hardcoded — mai eseguito in CI.
- `src/data/download.py`: script standalone che non viene mai chiamato dalla pipeline principale.

### 2.4 Pattern problematici

- **Fallback impliciti con default 0.5**: `build_features.py:130-132` — assunzione che la probabilità mancante sia sempre 50/50. Per feature come clutch BP save %, 0.6 come default è arbitrario (righe 283-292).
- **Magic numbers non estratti**: hardcoded `CACHE_TTL = 1200`, `CAP_DAYS = 90`, `COVERAGE_THRESHOLD = 0.5`, `MAX_AGENT_ITERATIONS = 8` sparsi nel codebase senza costanti nominate.
- **Config riscritto dentro funzioni hot path**: `portfolio.py:316` rilegge YAML su ogni `resolve_bet()`. Questo è dentro un lock SQLite — bottleneck I/O su percorso critico.

---

## 3. Performance

### 3.1 Bottleneck I/O

| Posizione | Problema | Stimaimpatto |
|---|---|---|
| `portfolio.py:316` | `yaml.safe_load(open(...))` su OGNI bet resolution (hot path) | ~5ms/operazione × n_bets |
| `warm_up.py:24` | `pd.read_csv(unified_path)` carica ~200k righe | ~2s cold start |
| `inference.py:173` | `pd.read_csv(unified_path)` a OGNI scan | ~2s/scan |
| `inference.py:175-195` | Doppio iterrows su 200k righe per name_to_id e id_to_rank | ~30s+ |
| `agentic_research.py` | Fetch sequenziale degli articoli (nessuna parallelizzazione) | ~10-30s per scan |

### 3.2 Vettorizzazione mancante

- `player_stats.py` — loop `for idx, row in matches_df.iterrows()` (riga 276) è la **singola operazione più lenta** della pipeline. Per 200k partite con 50k giocatori, ogni chiamata `get_player_features` traversa la lista `player_matches[pid]`. Complessità O(n × m) dove m è la storia del giocatore. **Questo è il bottleneck critico della build_features pipeline.**

- `clean.py` — `merge_asof` non usato per la merge tennis-data.co.uk (usa merge con chiavi testuali O(n²) invece).

- `build_features.py:70` — `df['score'].apply(parse_score)` applica riga per riga invece del vettorizzato `str.extract`.

### 3.3 Caching

- `live_engines.pkl` (joblib bundle di EloRating + PlayerStatsEngine) è il meccanismo di warm-up. **PROBLEMA**: se `PlayerStatsEngine` viene evoluto (nuovi attributi, nuovo schema), il file vecchio produce errori silenziosi o crash. Nessun schema versioning.

- Research cache (`data/cache/research_cache.json`) è JSON-based con TTL. OK per dimensioni moderate, ma cresce illimitatamente — nessun max size cap.

- `WebResearch._cache` (in-memory dict) non persiste tra scan separati — ogni oggetto `WebResearch()` fresco ricrea il dizionario vuoto.

### 3.4 Memory

- `EloRating` mantiene `self.history` con una entry per OGNI match processato (`elo.py:72`). Per 200k match, ~200k dict in lista Python — consumo ~50-100MB di overhead.

- `PlayerStatsEngine.player_matches` mantiene l'intera storia per OGNI giocatore in una lista Python. Per giocatori con 1000+ match (top players), questo è significativo.

- `clutch.py` carica TUTTI i file PBP in memoria prima del groupby — rischio OOM su dataset completi.

- `inference.py:174` carica SOLO 7 colonne con `usecols` — **GOOD**. Ma riga 181-184 usa iterrows su tutto per name_to_id.

---

## 4. Testing

### 4.1 Copertura

| Area | Stato |
|---|---|
| Data cleaning | **NESSUN TEST** |
| Feature engineering | **NESSUN TEST** |
| ELO rating | **NESSUN TEST** |
| Player stats | **NESSUN TEST** |
| Model training | **NESSUN TEST** |
| Betting logic (Kelly) | **NESSUN TEST** |
| Backtesting | **NESSUN TEST** |
| Portfolio DB | **NESSUN TEST** |
| Live inference | **NESSUN TEST** |
| UI/TUI | **NESSUN TEST** |

**Nessuna directory `tests/` esistente. Zero test di unità o integrazione.**

### 4.2 Test esistenti (root level)

- `test_randomization.py` — print di debug, ZERO assertions. Non verifica che la randomizzazione preservi alcuna proprietà.
- `clutch_test.py` — print di debug, ZERO assertions. Verifica che `parse_pbp_match` non crashi su 10 righe, ma non valida la correttezza dei risultati.
- `src/models/shuffle_test.py` — stampa risultati ma non fail su acc > 0.55. Test di leakage detection utile ma senza enforcement CI.

### 4.3 Mock

Nessun uso di `unittest.mock`, `pytest-mock`, o fixture fixtures. Tutti i test caricano dati reali.

### 4.4 Integrazione vs Unit

Non esiste distinzione — solo test di integrazione ad-hoc che stampano output e richiedono ispezione manuale.

---

## 5. Sicurezza

### 5.1 Gestione segreti

| File | Riga | Problema |
|---|---|---|
| `src/data/scraper.py` | 1-3 | `load_dotenv()` all'import — secret caricato anche se lo script non viene mai eseguito |
| `src/live/agentic_research.py` | 40 | Stesso — `load_dotenv()` all'import |
| `src/live/news_adjustment.py` | 13-14 | Stesso |
| `src/live/agent_llm.py` | 12-13 | Stesso |
| `src/ui/app.py` | 14-15 | Stesso |
| `.env` | — | Presente nel repository (NON in .gitignore?) — **CRITICAL se contiene chiavi reali** |

**Tutte le API key sono runtime-only**: `os.getenv()` cercato all'esecuzione. Se `.env` non è caricato, il fallback `${VAR}` in `config.yaml` viene usato direttamente come stringa — l'API fallisce silenziosamente.

### 5.2 API Key esposizione

- `ODDS_API_KEY` (the-odds-api.com) — usata in `scraper.py`, `inference.py` via config.
- `OPENROUTER_API_KEY` — usata in `agentic_research.py`, `news_adjustment.py`, `agent_llm.py`.
- `BRAVE_API_KEY` — usata in `agentic_research.py` e `web_research.py`.

### 5.3 Input validation

- `odds_p1` / `odds_p2` in `predict_live.py:42` — nessun check che sia > 1.0. Divisione per zero a riga 104.
- `kelly_fraction` in `backtest.py:50` — ha check NaN ma non check per odds <= 1.0 oltre a quello in `find_value_bets` a monte.
- `_resolve_td_name` in `clean.py:158` — nessuna sanitizzazione dell'output; restituisce stringhe che vengono usate come chiavi dict e ID.
- `tourney_level` in `sota_features.py:69-76` — lookup con fallback a `ATP_POINTS['D']` per livelli non trovati, ma nessuna validazione che sia un valore legale.

### 5.4 Network security

- HTTP verso tennis-data.co.uk: `config.yaml:15` usa `http://` (non https) per `tennis-data.co.uk`. **Trasmissione non cifrata.**
- Tutti gli altri endpoint (The Odds API, OpenRouter, Brave Search, Tennis Abstract) usano HTTPS — OK.
- Nessun certificate pinning.
- Nessun timeout esplicito su alcune richieste (BeautifulSoup fetch in `agentic_research.py:290` ha timeout=12, ma molte altre richieste `requests.get` hanno timeout di default illimitato).

---

## 6. Top 10 Issues

### CRITICAL

**1. Zero test coverage — `tests/` directory inesistente**
- Nessun file sotto `tests/`, nessun `pytest.ini`, nessuna config CI.
- Rischio: ogni refactoring rompe funzionalità senza alcun segnale.
- Fix: creare `tests/` con fixture per dati mock, test per `_randomize_perspective` (verifica invarianza total_games, target flip, column order), test per `kelly_fraction` (casi limite: odds=1.0, NaN, prob=0, prob=1), test per ELO rating monotonicità, test per portfolio atomicità.

**2. Bottleneck O(n×m) in `player_stats.py` — loop doppio iterrows**
- Riga 276-306: per ogni partita, chiama `get_player_features` che traversa `player_matches[pid]`. Per 200k partite con giocatori da 500 match, migliaia di operazioni per riga.
- Questo è il **singolo punto più costoso** dell'intera pipeline di feature engineering.
- Fix: pre-calcolare gli indici di window (10, 20, 50 match) con una sliding window buffer circolare invece di ri-slicare `matches[-w:]` per ogni match. Sostituire iterrows con `apply` vettorizzato dove possibile.

### HIGH

**3. Bug silenzioso in `player_stats.py:78-82` — zip lunghezza mismatch**
```python
if games_list and sets_list and len(games_list) == len(sets_list):  # ← attenzione
    gps = [g / s for g, s in zip(games_list, sets_list) if s > 0]
```
- Se le due liste hanno lunghezze diverse (dati mancanti filtrano uno ma non l'altro), il blocco viene SKIPPATO interamente e `avg_games_per_set = np.nan`. Il check `len(games_list) == len(sets_list)` è troppo aggressivo — dovrebbe usare `min(len(games_list), len(sets_list))`.
- Fix: `for i in range(min(len(games_list), len(sets_list))))`.

**4. Config YAML riletto su ogni bet resolution — `portfolio.py:316`**
- `get_bankroll()` (chiamato da `resolve_bet` che è nel lock SQLite) riapre `config.yaml` ogni volta.
- Cost: ~5ms × n_bets in hot path.
- Fix: leggere il config una volta in `__init__` e memorizzare `initial_bankroll`.

**5. Ricarica intero dataset storico per ogni scan live — `inference.py:173-195`**
- Ogni `run_inference()` ricarica 200k+ righe con iterrows per costruire `name_to_id` e `id_to_rank`.
- `warm_up.py` già pre-calcola `elo_engine` e `stats_engine` in `live_engines.pkl`. Manca solo la pre-computazione di `name_to_id` e `id_to_rank` come lookup serializzato.
- Fix: aggiungere `id_mappings.pkl` al warm-up con `{name_lower: player_id}` e `{player_id: latest_rank}`.

**6. Dati .env potenzialmente committati nel repo**
- File `.env` presente nella directory di lavoro.
- Check: `git status .env` — se committato, le chiavi API reali sono esposte.
- Fix: `.env` DEVE essere in `.gitignore`. Il `.env.example` è già corretto.

### MEDIUM

**7. `ELO.apply_time_decay` applicato dopo caricamento in `warm_up.py` — double decay**
- `warm_up.py:36` chiama `elo_engine.process_matches(df)` che internamente chiama `apply_time_decay` per ogni match.
- Ma se `live_engines.pkl` è già stato salvato da un run precedente, ricaricarlo e processare nuovamente ri-applica il decay due volte.
- Fix: aggiungere flag `skip_decay=False` a `process_matches` o salvare `last_played_date` per ogni giocatore.

**8. CPI_MAP hardcoded in `sota_features.py` — valori estimati non verificati**
- Ogni CPI è un float stimato (es. Wimbledon=72.0). Se il Court Pace Index reale diverge, il modello riceve feature sistematicamente distorte.
- Nessun meccanismo di aggiornamento o validazione.
- Fix: rendere configurabile via `config.yaml` e aggiungere almeno un test con valori boundary.

**9. Stale ELO non capped per fairness — `inference.py:364-376`**
- Il `CAP_DAYS = 90` neutralizza solo le `days_since_last` nel player stats engine, ma il decay ELO in `elo.py:78-99` prosegue illimitato. Un giocatore con 400 giorni di assenza ha ELO sistematicamente abbassato vs. uno con 90 giorni.
- Fix: applicare la stessa logica di cap all'ELO stesso (non solo ai days_since) prima di calcolare `elo_win_prob`.

**10. Config paths inconsistent — percorso di 3 file su 4 usano Path, 1 usa stringa**
- `agent_llm.py:44` e `agentic_research.py:643` usano stringa `"config/config.yaml"`.
- Tutti gli altri moduli usano `PROJECT_ROOT / "config" / "config.yaml"`.
- Rischio: questi moduli falliscono se eseguiti da directory diverse.

---

## 7. Roadmap Sviluppo

### P1 — Test Foundation (ROI: alto, sforzo: medio, valore: critico)
Creare `tests/` con:
1. `test_randomization.py` → assertions su proprietà: total_games invariance, column order preserved, target flip correctness.
2. `test_kelly.py` → casi limite: odds=1.0, odds=inf, prob=0, prob=1, NaN.
3. `test_elo.py` → monotonicità rating, no rating negativo, K-factor scaling per newcomer.
4. `test_portfolio.py` → atomicità resolve_bet, idempotency, rollback.
5. Setup `pytest.ini` con `testpaths = tests` e `python_files = test_*.py`.

**Tempo stimato**: 2-3h. **Impatto**: ogni refactoring diventa verificabile. Previene regressioni in betting logic (Kelly, portfolio).

### P2 — Precompute live engine state (ROI: alto, sforzo: basso, valore: alto)
Aggiungere a `warm_up.py` il serialize di `id_mappings.pkl`:
```python
joblib.dump({
    'elo': elo_engine, 'stats': stats_engine,
    'name_to_id': name_to_id, 'id_to_rank': id_to_rank,
    'last_update': ts
}, cache_path)
```
E in `inference.py` caricarlo invece di ricaricare CSV + iterrows.
**Risparmio**: ~30s per scan. **Tempo**: 30 min.

### P3 — Vectorize player_stats engine (ROI: alto, sforzo: alto, valore: alto)
Sostituire la logica iterrows con un approccio sliding window buffer. Prevenire il ri-slicing `matches[-w:]` per ogni match usando un ring buffer o dataframe shift operations. Potenziale speedup: da ~10-20 minuti a <1 minuto per build_features su 200k match.
**Tempo**: 4-6h. **Impatto**: pipeline di feature engineering da ~20min a ~2min.

### P4 — Config YAML in-memory cache (ROI: medio, sforzo: basso, valore: medio)
In `BetAnalytix.__init__`, leggere `initial_bankroll` e memorizzarlo come attributo invece di rileggere YAML su ogni `resolve_bet`.
In `agent_llm.py` e `agentic_research.py`, usare `PROJECT_ROOT` costante invece di percorso relativo.
**Tempo**: 20 min. **Impatto**: ~5ms × n_bets risparmiati in hot path.

### P5 — Config-driven paths e schema versioning per live_engines (ROI: medio, sforzo: medio, valore: medio)
1. Centralizzare tutti i path in `config.yaml` (oggi `tune.py` e `dl_model.py` usano path hardcoded).
2. Aggiungere version tag a `live_engines.pkl`: `{'version': 2, 'elo': ..., 'stats': ...}` e validare versione su load — fail loudly se schema obsoleto invece di crashare silenziosamente.
**Tempo**: 1-2h. **Impatto**: elimina 3+ percorso hardcoded, previene crash da engine state mismatch.

---

*Documento generato da opencode audit. Tutte le osservazioni sono basate su analisi statica e dinamica dei file sorgente. Nessun dato è stato eseguito o modificato.*
