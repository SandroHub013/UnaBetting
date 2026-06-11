# Tennis Betting ML — Project Evaluation & Roadmap

**Date:** 2026-05-07
**Sources:** `ANALYSIS_OPENCODE.md` (opencode audit, 325 lines) + Opus deep-dive ML/data integrity (hermes WSL audit timed out, supplemented inline)

---

## 1. Executive Summary

Sistema ATP betting ML maturo per pipeline (ELO + 86 feature + XGBoost calibrato 78.8% acc, walk-forward CV 78.0%) ma con **3 difetti strutturali critici** che minano i numeri dichiarati:

| # | Difetto | Impatto |
|---|---------|---------|
| **C1** | Target leakage via `fillna(median)` pre-split temporale (`train.py:94`, `cross_validate.py:47`, `backtest.py:159`) | Acc/ROI dichiarati sovrastimati. Va rimisurata baseline. |
| **C2** | Backtest senza commissioni / slippage / CLV — `backtest.py:240` profitto raw `stake*(odds-1)` | ROI +56.2% non realistico. Su Betfair (-5% commissione) e con drift quote, edge reale può collassare. |
| **C3** | Zero test (`tests/` inesistente) | Ogni refactor rompe Kelly/portfolio silenziosamente. Numeri non riproducibili. |

Codice complessivamente leggibile, architettura modulare ragionevole, ma **bottleneck performance** in `player_stats.py` (O(n×m), opencode issue #2) e **API key handling** rischioso (`.env` da verificare in `.gitignore`).

**Verdetto:** progetto ricerca solido, **non production-ready** per soldi reali finché C1+C2 non risolti.

---

## 2. Difetti Critici (con file:line)

### C1 — Target leakage in imputation

**`src/models/train.py:94`**
```python
df_r = df_r.fillna(df_r.median())   # PRE temporal split
# split test_mask = year_col >= test_year arriva dopo, riga 109
```
La median di ogni feature è calcolata sull'intero dataset (train+val+test). Train viene imputato con valori che includono distribuzione 2025+. **Test contaminato.**

**`src/models/cross_validate.py:47`** stesso problema replicato in ogni fold. La walk-forward CV "78.0%" usa median fold-future.

**`src/betting/backtest.py:159`**
```python
X_r_numeric = X_r[numeric_features].fillna(X_r[numeric_features].median())
```
`X_r` è già filtrato a `start_year` (2025+) ma la median è cumulativa sull'intero periodo backtest — match di gennaio 2025 imputato con dati di dicembre 2026. Look-ahead.

**Fix:** salvare `medians = X_train.median()` (`train.py:156` lo fa già ma DOPO la fillna corrotta), passarli e usarli a inference. Per CV, calcolare median solo su `X_train` per fold.

### C2 — Backtest non realistico

`backtest.py:240` profit ignora:
- **Commissione bookmaker / exchange** (Betfair 5% sui win)
- **Slippage prezzo** (B365W è opening odds; closing line spesso peggiore)
- **Stake limit reali** (max_stake=500€ ma bookmaker accetta meno su mercati illiquidi)
- **CLV (Closing Line Value)** non tracciato — metrica chiave per validare edge

ROI +56.2% dichiarato → ricalcolare con commissione 5%, slippage stocastico, e stake realistici. Edge probabilmente ~1/3.

### C3 — Zero test

Nessun `tests/` directory. `test_randomization.py` e `clutch_test.py` sono debug print senza assertions. Refactor del codice betting (Kelly, portfolio resolve_bet) è cieco.

---

## 3. Issue High-Severity (sintesi opencode)

| # | File:Line | Problema |
|---|-----------|----------|
| H1 | `player_stats.py:276-306` | Loop O(n×m) iterrows — bottleneck #1 della pipeline (~10-20min per 200k match) |
| H2 | `portfolio.py:316-317` | `yaml.safe_load` su ogni `resolve_bet()` (hot path lock SQLite) |
| H3 | `inference.py:173-195` | Ricarica 200k righe + doppio iterrows ad ogni scan live (~30s) |
| H4 | `player_stats.py:78-82` | Bug zip mismatch lunghezza → `avg_games_per_set = NaN` silenzioso |
| H5 | `clutch.py:152` | `groupby.sum()` su statistiche che dovrebbero essere max — feature distorta |
| H6 | `warm_up.py` + `live_engines.pkl` | No schema versioning → crash silenzioso se EloRating evolve |
| H7 | `.env` | Verificare `.gitignore` — opencode segnala presenza file in repo |
| H8 | `clean.py:144-145` | Iterrows O(n²) per name_to_id su 200k righe |

## 4. Issue Medium

- ELO time decay non capped (`elo.py:78` decay illimitato vs `inference.py:364` CAP_DAYS=90 solo su days_since stat) — divergenza
- CPI_MAP hardcoded `sota_features.py` — valori non validati
- `tune.py` genera `best_params.yaml` mai letto da `train.py` — dead code
- `dl_model.py` PyTorch DNN definito mai usato in pipeline
- Config path inconsistenti (`agent_llm.py:44` stringa vs altri `PROJECT_ROOT`)
- HTTP non-cifrato verso `tennis-data.co.uk`
- `_randomize_perspective` duplicato 4 volte
- Calibrazione isotonica su val 2023-2024 → drift su 2025+ se distribuzione cambia

---

## 5. Roadmap Sviluppo Proposta

Ordinata per **impatto su affidabilità ROI** (non per facilità):

### P0 — Fix leakage (BLOCKER) — 2-4h
1. `train.py:prepare_training_data`: spostare `fillna(median)` DOPO split temporale, computare median solo su `X_train`. Salvare `medians.pkl` per inference.
2. `cross_validate.py`: stessa logica per ogni fold (median solo da pre-fold-train).
3. `backtest.py:159`: usare `medians.pkl` salvato dal training, non ricalcolare.
4. **Rimisurare**: accuracy test, log loss, ROI backtest. Aspettarsi -2/-5% acc, -10/-30% ROI.

### P1 — Backtest realistico — 4-6h
1. Aggiungere `commission_rate` (default 0.05) al config — applicare a profit lordo.
2. Slippage stocastico: `actual_odds = odds * (1 - U(0, slippage_max))` con `slippage_max=0.02`.
3. CLV tracking: registrare `closing_odds` se disponibile da `B365CW`/`B365CL` (closing odds tennis-data.co.uk) e calcolare `clv = (closing_odds - bet_odds) / bet_odds`.
4. Variance-aware reporting: bootstrap CI 95% su ROI invece di point estimate.

### P2 — Test foundation — 6-8h
1. `tests/test_kelly.py` — odds=1.0, NaN, prob∈{0,0.5,1}.
2. `tests/test_randomization.py` — invarianti: column count, total_games, ELO sum, target flip atomico.
3. `tests/test_elo.py` — monotonicità, no negative, K-factor newcomer.
4. `tests/test_portfolio.py` — atomicità resolve_bet, idempotency.
5. `tests/test_leakage.py` — replicare `forensic_leak_check.py` con assertion `assert acc_shuffled < 0.55`.
6. `pytest.ini` + GitHub Actions CI.

### P3 — Performance pipeline — 6-10h
1. Vettorizzare `player_stats.PlayerStatsEngine.get_player_features` con sliding window numpy invece di list slicing.
2. Pre-compute `id_mappings.pkl` in `warm_up.py` (name_to_id, id_to_rank).
3. Cache config in `BetAnalytix.__init__` invece di rilettura YAML.
4. Schema versioning su `live_engines.pkl` (`{'version': 2, ...}`).

**Atteso:** build_features 20min → 2min. Live scan 30s → <5s.

### P4 — Nuove feature ML / strategia — open-ended
- [x] **Player-vs-style**: ELO contestuale per stile avversario (server-vs-returner) e calcolo SOTA Clutch stats (rendimento tie-break, rendimento al 5° set, storico vs mancini). Auto-generazione feature differenziali. (COMPLETATO)
- [ ] **Form recency weighting**: invece di rolling fissa 10/20/50, usare exponential decay.
- [ ] **Fatigue compounding**: contare set giocati ultimi 14gg con decay (oggi solo days_since).
- **Live odds drift**: scaricare quote a -2h, -1h, kickoff e sfruttare market-implied movement come feature.
- **Multi-bookmaker arbitrage**: estendere oltre B365 (Pinnacle, Betfair) — trova best price.
- **In-play models** (Markov chain set-by-set) — orizzonte molto più ambizioso.

### P5 — Hardening operativo — 2-3h
1. Verificare `.env` in `.gitignore` (CRITICAL se chiavi committate — rotazione immediata).
2. Tutti i `requests.get` con timeout esplicito.
3. HTTPS forzato anche per tennis-data.co.uk (verificare disponibilità).
4. Centralizzare path in `config.yaml` (eliminare hardcoded in `tune.py`, `dl_model.py`, `agent_llm.py`, `agentic_research.py`).
5. Rimuovere dead code: `dl_model.py` se non usato, `tune.py` integrare con train o eliminare.

---

## 6. Decisioni aperte (richiedono input utente)

- **Capitale reale prima o dopo P0+P1+P2?** Raccomandazione forte: **dopo**. ROI dichiarato non verificabile finché leakage attivo.
- **DL model**: tenere `dl_model.py` o eliminare? Usato mai in produzione?
- **In-play / live trading**: P4 stretch goal. Fattibile ma serve infrastruttura nuova (websocket bookmaker, latency budget).
- **Multi-tour**: WTA pipeline esiste in config ma `train.py` chiama solo `tour="atp"`. Estendere?

---

## 7. Stato hermes audit

Hermes WSL ha avuto problemi shell escaping su 2 lanci consecutivi (-z arg eaten / fragmenting). Terzo lancio (PID 935) running ma >5min senza output file. Non blocca: l'analisi ML/data-integrity di questa sintesi (sezioni C1, C2, P0, P1) è stata prodotta da Opus tramite read diretto dei file critici (`train.py`, `cross_validate.py`, `backtest.py`, `elo.py`, `config.yaml`).

Se hermes completa, le sue findings vanno mergiate in §3-4.
