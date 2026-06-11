# SANDROMANTE TENNIS PREDICTION SYSTEM
## Analisi Critica e Proposte di Miglioramento State-of-the-Art

### Un Documento Tecnico per lo Sviluppo di un Sistema SOTA di Predizione Tennis

**Autore:** Sandromante AI Consulting (LLM-Assisted Technical Analysis)  
**Data:** 5 Aprile 2026  
**Versione:** 1.0  
**Revisione del Progetto:** Tennis Betting SOTA — v1.0  
**Stato del Progetto:** Produzione Live (ATP, 3 mercati, 5+ modelli)  

---

## INDICE

1. [Executive Summary](#1-executive-summary)
2. [Analisi Critica dell'Architettura Attuale](#2-analisi-critica-dellarchitettura-attuale)
3. [Feature Engineering: Stato Attuale e Gap Analysis](#3-feature-engineering-stato-attuale-e-gap-analysis)
4. [Modelli di Machine Learning: Analisi e Miglioramenti](#4-modelli-di-machine-learning-analisi-e-miglioramenti)
5. [Backtesting: Limiti e Avanzamenti](#5-backtesting-limiti-e-avanzamenti)
6. [Inference Live: Robustezza e Scalabilità](#6-inference-live-robustezza-e-scalabilita)
7. [Agent LLM e News Adjustment](#7-agent-llm-e-news-adjustment)
8. [Advanced Betting Theory e Bankroll Management](#8-advanced-betting-theory-e-bankroll-management)
9. [Data Pipeline: Qualità, Completezza e Freshness](#9-data-pipeline-qualita-completezza-e-freshness)
10. [Feature Selection e Dimensionality Reduction](#10-feature-selection-e-dimensionality-reduction)
11. [Probabilistic Calibration e Uncertainty Quantification](#11-probabilistic-calibration-e-uncertainty-quantification)
12. [Deep Learning e Architetture Sequenziali](#12-deep-learning-e-architetture-sequenziali)
13. [Ensemble Avanzato e Stacking](#13-ensemble-avanzato-e-stacking)
14. [Market Microstructure e Odds Dynamics](#14-market-microstructure-e-odds-dynamics)
15. [Live In-Play Prediction](#15-live-in-play-prediction)
16. [WTA e Challenger Expansion](#16-wta-e-challenger-expansion)
17. [Infrastruttura MLOps e CI/CD](#17-infrastruttura-mlops-e-cicd)
18. [Monetizzazione e Roadmap Commerciale](#18-monetizzazione-e-roadmap-commerciale)
19. [Risk Management e Compliance Legale](#19-risk-management-e-compliance-legale)
20. [Roadmap Prioritizzata — 12 Mesi](#20-roadmap-prioritizzata--12-mesi)
21. [Appendice A: Metriche di Riferimento](#appendice-a-metriche-di-riferimento)
22. [Appendice B: Riferimenti Bibliografici](#appendice-b-riferimenti-bibliografici)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Panoramica del Sistema

Il **Sandromante Tennis Prediction System** è un sistema di predizione tennis ATP basato su machine learning progettato per identificare value bets sui mercati H2H (esito), Spread (differenza games) e Totals (games totali). Il sistema integra:

- **Dataset:** Dati storici ATP dal 2000 (Jeff Sackmann + tennis-data.co.uk), con feature ELO globali e per superficie, statistiche rolling, head-to-head, clutch metrics, CPI, meteo, e probabilità implicite del mercato
- **Modelli:** Logistic Regression, Random Forest, XGBoost, LightGBM, Neural Network, con ensemble soft/hard voting
- **Architettura:** Pipeline completa da download → cleaning → feature engineering → training → backtesting → inference live → interfaccia TUI
- **Live:** Inferenza su match imminenti con quote da TheOddsAPI, news adjustment via LLM, e dashboard terminal

**Performance attuali:**
| Metrica | H2H | Spread (game_diff) | Totals (total_games) |
|---------|-----|-------------------|---------------------|
| Accuracy / MAE | 78.8% | MAE 3.30 games | MAE 5.37 games |
| ROC AUC | 0.884 | R² 0.40 | R² 0.37 |
| Walk-Forward CV | 78.0% ± 0.5% | — | — |

**Backtest ROI (strategia Kelly 25%, 2024-2026):**
| Strategia | Scommesse | Win Rate | ROI | Max DD |
|-----------|-----------|----------|-----|--------|
| Value (Kelly) | 564 | 77.3% | +56.2% | -17.2% |
| Blind (flat) | 972 | 80.8% | +31.0% | -7.4% |
| Threshold 0.8 | 462 | 95.9% | +49.8% | -2.8% |

### 1.2 Punti di Forza Identificati

✅ **Architettura solida:** Pipeline ben strutturata, modulare, con separazione chiara tra data, features, models, betting e live  
✅ **Prevenzione del leakage:** Randomizzazione prospettiva, split temporale, nuclear filter su post-match stats, staleness cap  
✅ **Multi-mercato:** H2H + Spread + Totals copre tutti i mercati principali del betting tennis  
✅ **Feature engineering ricco:** 86 feature con ELO adattivo, clutch metrics, CPI, weather, implied probability  
✅ **Kelly Criterion + fractional:** Gestione del bankroll professionale con max_stake  
✅ **Live inference multi-modello:** 3 modelli separati con edge calculation e forensics per match  
✅ **LLM integration:** News adjustment per infortuni/forma + agente conversazionale per analisi  

### 1.3 Lacune Critiche da Risolvere

❌ **Probabilità non calibrate:** Le probabilità dei modelli non sono calibrate (Brier score non ottimizzato, temperature scaling assente)  
❌ **Overfitting al passato:** Il backtest usa un singolo seed (42) per la randomizzazione — nessuna sensitivity analysis  
❌ **Feature correlation non gestita:** Molte feature sono altamente correlate (es. win_rate_10, win_rate_20, win_rate_50) — multicollinearità non diagnosticata  
❌ **Nessuna uncertainty quantification:** Il modello produce una singola probabilità senza intervallo di confidenza  
❌ **No in-play prediction:** Il sistema opera solo pre-match — il vero edge è in-play  
❌ **Nessun tracking delle scommesse reali:** Il backtest è storico, non c'è un sistema di Paper Trading live  
❌ **Modello singolo per tutti i tornei:** Non c'è specializzazione per superficie, livello torneo, o tipo di giocatore  
❌ **Deep learning sottoutilizzato:** La DNN `best_tennis_dnn.pth` sembra un esperimento isolato, non integrato nell'ensemble  
❌ **Nessun monitoring di data drift:** Non c'è alerting quando le performance degradano nel tempo  
❌ **Feature selection non ottimizzata:** La selezione è manuale via file di testo, non basata su metriche o SHAP  
❌ **Nessuna analisi di survivorship bias:** I giocatori ritirati o降级 non sono inclusi correttamente  

### 1.4 Obiettivi di Questo Documento

Questo paper ha tre obiettivi:
1. **Analizzare criticamente** ogni componente del sistema attuale
2. **Proporre miglioramenti concreti**, ordinati per impatto/complessità
3. **Definire una roadmap** di 12 mesi per evolvere il sistema verso lo SOTA

---

## 2. ANALISI CRITICA DELL'ARCHITETTURA ATTUALE

### 2.1 Struttura del Progetto

```
tennis_betting_sota/
├── config/              # Configurazione YAML
├── data/                # Raw → Processed → Features → Live
├── models/              # Modelli salvati (.pkl, .pth)
├── reports/             # Backtest CSV, charts, presentazioni
├── src/
│   ├── data/            # Download, cleaning, scraping
│   ├── features/        # ELO, stats, SOTA, clutch
│   ├── models/          # Training, CV, tuning, prediction
│   ├── betting/         # Backtesting, Kelly Criterion
│   ├── live/            # Inference, TUI, LLM agent, news
│   └── ui/              # App, audio engine
```

**Giudizio:** ⭐⭐⭐⭐ (4/5) — Struttura professionale, ben organizzata, segue best practice. Solo il modulo `ui/` potrebbe essere separato da `src/` per chiarezza.

### 2.2 Data Flow

```
Download → Clean → Features → Train CV Tune → Backtest → Inference → TUI
   ↓          ↓         ↓          ↓              ↓           ↓
  Raw      Unified   86 feat    5 modelli     3 strategie   Live odds
```

**Analisi del flusso dati:**

Il flusso è lineare e corretto. Tuttavia, presenta tre limiti critici:

1. **Nessuna validazione incrociata dei dati:** Non c'è un data validation layer (es. Great Expectations, Pandera) che verifichi qualità, consistenza e completezza ad ogni step
2. **Il cleaning è monolitico:** `clean.py` (25,670 righe) fa tutto insieme — download, merge, deduplica, parsing score. Dovrebbe essere spezzato in moduli indipendenti con output verificabile intermedio
3. **Nessun versioning dei dati:** Non c'è DVC, LakeFS, o MLflow per tracciare versioni del dataset. Se i dati cambiano, non puoi riprodurre risultati passati

### 2.3 Punti Critici dell'Architettura

#### 2.3.1 Single Point of Failure: Il Database SQLite

Il file `.cache.sqlite` (3.4 MB) è l'unico storage per i dati live. Se si corrompe:
- Tutte le predizioni live falliscono
- Non c'è backup automatico
- Non c'è replica

**Soluzione:** Migrare a SQLite con WAL mode + backup cron, o usare un database vero (PostgreSQL).

#### 2.3.2 Accoppiamento Forte tra Moduli

Il module `src/live/inference.py` importa direttamente da `src/features/`, `src/models/`, e `src/live/news_adjustment`. Questo crea:
- Difficoltà nel testare singoli componenti
- Dipendenze nascoste (es. il path hard-coded ai modelli)
- Impossibilità di riutilizzare i moduli in progetti diversi

**Soluzione:** Introdurre un'astrazione `Pipeline` o `ModelRegistry` che incapsuli tutti i componenti.

#### 2.3.3 Mancanza di Testing

Non ci sono test unitari (nessuna cartella `tests/`). Questo significa:
- Ogni modifica richiede verifica manuale
- Bug silenziosi possono introdursi facilmente
- Impossibile fare refactoring in sicurezza

**Soluzione minima:** Creare test per:
- `_randomize_perspective()` — verificare che la randomizzazione sia reversibile
- `kelly_fraction()` — test edge cases (odds ≤ 1, prob = 0, prob = 1)
- `implied_probability()` — verificare che 1/odds sia corretto
- Feature building — verificare che non ci siano leak

---

## 3. FEATURE ENGINEERING: STATO ATTUALE E GAP ANALYSIS

### 3.1 Feature Attuali (86 feature)

Il sistema attuale calcola 86 feature suddivise in categorie:

| Categoria | Feature | Count | Qualità |
|-----------|---------|-------|---------|
| ELO | global+surface con K-adaptivo | ~8 | ⭐⭐⭐⭐⭐ |
| Rolling Stats | win_rate, ace_rate, bp_save, hold% su 10/20/50 | ~30 | ⭐⭐⭐⭐ |
| H2H | Wins, losses, surface-specific | ~4 | ⭐⭐⭐⭐ |
| Fatigue | days_since_last, sets_last_week | ~4 | ⭐⭐⭐ |
| Clutch | BP saved/converted %, deuce win %, TB win % | ~8 | ⭐⭐⭐⭐⭐ |
| Context | Surface, livello, ranking diff, age diff | ~12 | ⭐⭐⭐⭐ |
| Market | Implied prob (margin-removed) | 3 | ⭐⭐⭐⭐⭐ |
| SOTA | CPI, defending pts, weather | ~8 | ⭐⭐⭐⭐ |
| Totals | Sum features, min features | ~10 | ⭐⭐⭐ |

### 3.2 Gap Analysis — Feature Mancanti SOTA

#### 3.2.1 Feature di Dinamica del Gioco (CRITICHE)

**Match Momentum / Flow Features:**
- Ultima partita: è stata una vittoria facile o sofferta? (2-0 vs 3-2)
- streak_type: ha vinto 5 match di fila o sta in una serie altalenante?
- comeback_rate: % di match vinti dopo aver perso il primo set
- dominance_ratio: (games won) / (games lost) negli ultimi N match
- tiebreak_performance: Win rate nei tiebreaks negli ultimi 20 match
- break_point_conversion_under_pressure: BP converted quando serve per restare nel set vs quando è avanti

**Implementazione proposta:**
```python
def compute_momentum_features(player_id, match_date, surface):
    """
    Calcola le feature di momentum basate sugli ultimi N match.
    Include: streak_type, comeback_rate, dominance_ratio,
    tiebreak_performance, pressure_bp_conversion
    """
```

#### 3.2.2 Feature di Matchup Specifico

Le feature H2H attuali sono troppo semplificate (wins/losses). Mancano:

- **Surface-specific H2H** con peso temporale: un H2H di 5 anni fa su erba vale meno di uno recente su cemento
- **Style matchup:** Big server vs returner aggressivo? Pusher vs baselinista? Queste categorie possono essere derivate dalle statistiche storiche
- **Serve-vs-Return matchup:** La prima di P1 vs il return rate di P2 sugli ultimi 20 match
- **Return game winning:** La % di games in cui P2 ha vinto il servizio contro giocatori con ACE rate simile a P1

#### 3.2.3 Feature di Fisicità e Infortunio

- **Travel distance:** Distanza percorsa dall'ultimo torneo (fatica da viaggio)
- **Time zone adjustment:** Cambio di fuso orario nelle ultime 72h
- **Match duration cumulative:** Ore totali giocate negli ultimi 14 giorni
- **Injury history proxy:** Ritiri (retirements) negli ultimi 12 mesi
- **Age × Surface interaction:** Giocatori >30 anni su clay hanno un calo diverso rispetto a hard

#### 3.2.4 Feature di Mercato SOTA

- **Odds movement:** Variazione delle quote nelle ultime 24/48/72h
- **Sharp vs soft bookmaker divergence:** Differenza tra Pinnacle e Bet365
- **Steam moves indicator:** Movimento improvviso delle quote su più bookmaker
- **Public money %:** Percezione del pubblico (da fonti esterne come VLT o Twitter sentiment)

#### 3.2.5 Feature di Deep Learning-Ready

- **Match sequence encoding:** Rappresentare gli ultimi 20 match come una sequenza (non come aggregazioni statistiche)
- **Player embeddings:** Vector representation dei giocatori appresa durante il training (come Word2Vec per il tennis)
- **Temporal decay features:** Feature con esponenziale decay invece di windows fisse

### 3.3 Analisi della Multicollinearità

Molte feature sono fortemente correlate tra loro. Ad esempio:
- `w_win_rate_10`, `w_win_rate_20`, `w_win_rate_50` (correlation ~0.85)
- `w_elo` e `w_surface_elo` (correlation ~0.75)
- `w_hold_pct_10` e `w_ace_rate_10` (correlation ~0.60)
- `sum_ace_rate_10` e `sum_ace_rate_20` (correlation ~0.90)

**Problema:** La multicollinearità inflaziona la varianza dei coefficienti nei modelli lineari, riduce l'interpretabilità e può causare overfitting in ensemble.

**Soluzione:** Calcolare la Variance Inflation Factor (VIF) per ogni feature e rimuovere quelle con VIF > 10. In alternativa, usare PCA o feature selection basata su SHAP.

---

## 4. MODELLI DI MACHINE LEARNING: ANALISI E MIGLIORAMENTI

### 4.1 Analisi dei Modelli Attuali

#### 4.1.1 XGBoost (Best H2H — 78.8% acc, 0.884 ROC AUC)

**Punti di forza:**
- Gestione nativa dei missing values
- Regularizzazione L1/L2 integrata
- Eccellente performance su dati tabulari

**Punti deboli:**
- `n_estimators=500`, `max_depth=6` potrebbe essere sottodimensionato per 86 feature
- `learning_rate=0.05` è conservativo — con early stopping si può usare 0.01-0.03
- Nessuna calibrazione delle probabilità post-training
- Nessun monitoraggio delle feature importance nel tempo

**Miglioramenti proposti:**
1. **Early stopping con validation set:** Usare i validation_years [2023, 2024] per early stopping invece di un numero fisso di alberi
2. **Hyperparameter tuning bayesiano:** Ottuna o Ray Tune invece di parametri fissi
3. **Probability calibration:** Isotonic regression o Platt scaling post-training
4. **Cross-validation per selezione iperparametri:** Walk-forward CV con ottimizzazione bayesiana

#### 4.1.2 Ensemble (Soft Voting)

**Punti di forza:**
- Commedia diversità tra modelli (LR, RF, XGB, LGB)
- Soft voting per H2H (probabilità mediate)

**Punti deboli:**
- Pesi uguali per tutti i modelli (non tutti contribuiscono allo stesso modo)
- Nessun stacking meta-learner
- L'ensemble è statico — non si adatta al tipo di match

**Miglioramenti proposti:**
1. **Pesi ottimizzati:** Usa logistic regression sul validation set per apprendere i pesi ottimali
2. **Stacking:** Secondo livello con un meta-learner (es. LightGBM) che prende come input le predizioni dei modelli base
3. **Dynamic ensemble:** Pesare i modelli in base alla superficie, al livello torneo, al tipo di matchup

#### 4.1.3 Neural Network (best_tennis_dnn.pth)

**Analisi:** Il modello esiste ma non è integrato nel training principale né nell'ensemble. La configurazione specifica hidden layers [128, 64, 32] con dropout 0.3.

**Miglioramenti proposti:**
1. Integrare la DNN nell'ensemble (peso ~20%)
2. Provare Architetture più avanzate: TabNet, NODE (Neural Oblivious Decision Ensembles)
3. Usare la DNN per apprendere embeddings dei giocatori

### 4.2 Modelli Mancanti nello SOTA

#### 4.2.1 CatBoost

CatBoost è superiore a XGBoost e LightGBM su molti dataset tabulari, specialmente con feature categoriali. Il sistema attuale non lo include.

**Perché usarlo:**
- Gestione nativa delle categorical features senza preprocessing
- Migliore generalizzazione su dataset di piccole-medie dimensioni
- Order boosting per evitare target leakage

#### 4.2.2 Modelli Bayesiani

Un modello Bayesiano (es. BART — Bayesian Additive Regression Trees) fornirebbe:
- Intervalli di confidenza sulle predizioni
- Quantificazione dell'incertezza epistemica vs aleatorica
- Migliore calibrazione delle probabilità

#### 4.2.3 TabNet / NODE

Per dati tabulari sportivi, TabNet e NODE possono superare ensemble tree-based se addestrati correttamente:
- Attention mechanism su feature rilevanti
- Interpretabilità integrata (feature importance dall'attention mask)
- Apprendimento sequenziale delle feature

---

## 5. BACKTESTING: LIMITI E AVANZAMENTI

### 5.1 Analisi del Backtest Attuale

Il backtest attuale simula 3 strategie su dati storici:
- **Value (Kelly):** Identifica value bets con edge ≥ 3% e usa Kelly fractionario al 25%
- **Blind (flat):** Scommette una quota fissa su ogni match con model_prob > 0.5
- **Threshold 0.8:** Scommette quota fissa solo su match con model_prob > 0.8

**Limiti critici:**

1. **Singolo bookmaker:** Usa solo B365. I bookmaker reali hanno spread diversi, limiti diversi, e reagiscono alle scommesse
2. **Nessun liquidity constraint:** Non tiene conto del fatto che alcune scommesse non sono piazzabili (limiti di mercato, sospensione quote)
3. **Commissioni e vig ignorate:** Non ci sono costi di transazione, spread bid-ask, o commissioni exchange
4. **Overfitting alla strategia:** Le 3 strategie sono testate sullo stesso dataset — nessuna holdout per la selezione della strategia
5. **Nessuna walk-forward ottimizzazione:** I parametri (min_edge=0.03, kelly_fraction=0.25) sono fissi, non riottimizzati periodicamente
6. **Slippage non considerato:** Nella realtà, la quota al momento della scommessa potrebbe differire da quella usata nel backtest

### 5.2 Proposte di Avanzamento

#### 5.2.1 Walk-Forward Optimization

```python
def walk_forward_backtest(features_df, model, config, 
                          train_window=365, test_window=30, step=7):
    """
    Walk-forward backtest: allena su finestre mobili,
    backtest sulla finestra successiva.
    """
```

Implementare un backtest walk-forward dove:
- Ogni mese: ri-allena il modello sugli ultimi 12 mesi
- Backtest sul mese corrente con parametri ottimizzati
- I parametri (min_edge, kelly_fraction) sono riottimizzati ogni quarter

#### 5.2.2 Monte Carlo Simulation

Eseguire 10,000 simulazioni Monte Carlo del backtest per:
- Distribuzione dei rendimenti (non solo media)
- Probabilità di rovina (< 50% del bankroll iniziale)
- Confidence intervals sul ROI
- Stress testing: cosa succede se il win rate cala del 5%?

#### 5.2.3 Multi-Bookmaker Simulation

Simulare l'uso di 3-5 bookmaker per:
- Identificare il bookmaker con le quote migliori per ogni match
- Considerare limiti di scommessa diversi
- Simulare lo slippage e la latenza di piazzamento

#### 5.2.4 Paper Trading Live

Creare un sistema di paper trading che:
- Piazza scommesse virtuali in tempo reale
- Confronta le quote usate con quelle effettivamente disponibili
- Traccia performance reale vs backtestata
- Genera report settimanali di divergence

---

## 6. INFERENCE LIVE: ROBUSTEZZA E SCALABILITÀ

### 6.1 Analisi del Sistema Live Attuale

Il sistema live (`inference.py`) funziona così:
1. Scarica quote live da TheOddsAPI
2. Per ogni match: identifica giocatori, calcola feature, scala, predice
3. Calcola edge per entrambi i lati
4. Applica news adjustment tramite LLM
5. Salva predizioni in JSON per la TUI

**Punti deboli:**

1. **Fuzzy matching dei giocatori:** `fuzzy_find_player_id` usa SequenceMatcher con threshold 0.85 — può fallire per nomi non standard o trascrizioni diverse
2. **Nessuna caching delle feature:** Ogni match richiede il ricalcolo delle feature da zero
3. **Gestione errori fragile:** Se un match fallisce, non c'è logging strutturato dell'errore
4. **Nessuna validazione dell'output:** Le predizioni non sono verificate per coerenza (es. prob > 1, edge negativo ma consigliato)

### 6.2 Proposte di Miglioramento

#### 6.2.1 Player Resolution System

Creare un sistema di risoluzione giocatori basato su:
- **Nome canonico:** Mappatura univoca nome → ID per ogni match storico
- **Alias detection:** "Novak Djokovic" = "N. Djokovic" = "Djokovic N."
- **API-based lookup:** Integrare con API tennis (es. ATP API) per risoluzione via ID ufficiale
- **Confidence scoring:** Per ogni match, un confidence score sulla risoluzione (se < 90%, flag per review umana)

#### 6.2.2 Feature Cache System

```python
class FeatureCache:
    """
    Cache delle feature per giocatore.
    Aggiorna solo quando cambia qualcosa (nuovo match giocato).
    """
    def __init__(self):
        self.cache = {}
        self.last_update = {}
    
    def get_features(self, player_id, surface, opponent_id, match_date):
        # Hit → ritorna dalla cache
        # Miss → calcola e aggiorna
```

**Vantaggi:**
- Velocità di inference: da ~2 secondi a ~100ms per match
- Aggiornamento incrementale: solo i giocatori che hanno giocato un nuovo match vengono ricalcolati

#### 6.2.3 Structured Logging

Aggiungere logging strutturato (JSON) per:
- Ogni predizione (match, modello, tempo di calcolo, confidenza)
- Ogni errore (tipo, messaggio, stack trace)
- Performance del sistema (latenza media, throughput)

```json
{
  "timestamp": "2026-04-05T14:32:00Z",
  "event": "prediction",
  "match": "Djokovic vs Alcaraz",
  "model": "xgboost_ensemble",
  "prob_1": 0.62,
  "prob_2": 0.38,
  "exp_game_diff": -2.1,
  "exp_total_games": 23.4,
  "edge": 0.08,
  "latency_ms": 145,
  "confidence": "high"
}
```

#### 6.2.4 Output Validation

Prima di salvare le predizioni:
```python
def validate_prediction(pred):
    assert 0 <= pred["prob_1"] <= 1, f"prob_1 fuori range: {pred['prob_1']}"
    assert 0 <= pred["prob_2"] <= 1, f"prob_2 fuori range: {pred['prob_2']}"
    assert abs(pred["prob_1"] + pred["prob_2"] - 1.0) < 0.001, "Prob non sommano a 1"
    assert pred["exp_game_diff"] > -30 and pred["exp_game_diff"] < 30, "Game diff irrealistico"
    assert pred["exp_total_games"] > 10 and pred["exp_total_games"] < 45, "Total games irrealistico"
```

---

## 7. AGENT LLM E NEWS ADJUSTMENT

### 7.1 Analisi del Sistema LLM Attuale

Il sistema integra un agente LLM (GPT-5-Nano via OpenRouter) che:
1. Analizza le predizioni ML e le quote
2. Calcola l'edge e la Kelly stake
3. Genera un'analisi conversazionale con rating a stelle

**News Adjustment:**
- Scraper web per notizie su infortuni/forma/giochi
- LLM estrae structured adjustment factors
- Applicazione di aggiustamenti capped a ±15pp sulle probabilità ML

**Limiti:**

1. **LLM leggero:** GPT-5-Nano potrebbe non avere la capacità di analisi sofisticata necessaria
2. **Nessun grounding:** Le news non sono verificate contro fonti multiple
3. **Adjustment heuristic:** I ±15pp sono arbitrari — non basati su dati empirici
4. **Nessun A/B test:** Non si misura se l'aggiustamento migliora o peggiora le predizioni

### 7.2 Proposte di Avanzamento

#### 7.2.1 Multi-Model LLM Ensemble

Usare 2-3 modelli LLM per l'analisi:
- **Analista quantitativo:** Modello con forte ragionamento (es. Claude Sonnet 4.6) per validazione matematica
- **Analista qualitativo:** Modello creativo per contestualizzare le news
- **Consensus:** Media pesata delle opinioni LLM

#### 7.2.2 Empirical News Impact

Creare un database storico di:
- Eventi tipo: infortunio, cambio di superficie, ritorno da infortunio, cambio di coach
- Impatto reale sulle performance successive
- Usare questi dati per calcolare adjustment factors empirici invece di heuristic

```python
# Database storico degli eventi
news_impact_db = {
    "return_from_injury_1_month": -0.05,   # -5pp sulla probabilità di vittoria
    "new_coach_first_3_matches": -0.03,     # -3pp (periodo di adattamento)
    "surface_switch_hard_clay": -0.04,      # Per giocatori hard-court specialist
    "back_to_back_finals": -0.02,           # Fatica accumulata
}
```

#### 7.2.3 A/B Testing del LLM

Implementare un sistema di A/B testing:
- Metà delle predizioni: solo ML (baseline)
- Metà: ML + LLM adjustment
- Dopo 500+ match: confrontare ROI e accuracy
- Se il LLM peggiora → disabilitarlo o rivedere il prompt

---

## 8. ADVANCED BETTING THEORY E BANKROLL MANAGEMENT

### 8.1 Kelly Criterion: Analisi Critica

Il sistema usa Kelly frazionario al 25% con max_stake di €500. Questo è un buon starting point, ma presenta limiti:

**Problema:** Il Kelly assume che:
1. Le probabilità del modello siano corrette (calibrated) — NON LO SONO
2. Le odds siano fisse al momento della scommessa — NON SONO SEMPRE COSÌ
3. Non ci siano limiti di scommessa — CI SONO

**Proposta di miglioramento:**

```python
def adaptive_kelly(p_model, odds, calibration_error, bankroll, 
                   kelly_base=0.25, min_kelly=0.1, max_kelly=0.4):
    """
    Kelly adattivo: riduce la frazione quando il modello è meno calibrato.
    
    calibration_error: Brier score o ECE (Expected Calibration Error)
    su una finestra mobile di 100 match.
    """
    base_f = kelly_fraction(p_model, odds) * kelly_base
    
    # Penalizza quando il modello è mal calibrato
    penalty = max(0.3, 1.0 - calibration_error * 5)  # Se ECE=0.1 → penalty=0.5
    adaptive_f = base_f * penalty
    
    return max(min_kelly, min(max_kelly, adaptive_f))
```

### 8.2 Bankroll Management Avanzato

#### 8.2.1 Dynamic Fractional Kelly

Non usare una frazione fissa del 25% ma adattarla in base a:
- **Performance recente:** Se il ROI degli ultimi 30 giorni è negativo → riduci Kelly al 15%
- **Confidenza della predizione:** Edge > 10% → Kelly 30%, Edge 3-10% → Kelly 25%, Edge < 3% → Kelly 10%
- **Volatilità del mercato:** Periodi di alta volatilità → Kelly ridotto

#### 8.2.2 Portfolio Optimization

Invece di trattare ogni scommessa indipendentemente, ottimizzare il portafoglio:
- Correlazione tra scommesse (es. due match dello stesso torneo con giocatori che condividono l'allenatore)
- Diversificazione per superficie, tipo di mercato, bookmaker
- Markowitz-style optimization per massimizzare risk-adjusted return

```python
def optimize_portfolio(bets, bankroll, max_correlation=0.3):
    """
    Ottimizza il portafoglio di scommesse per massimizzare
    il return/risk ratio, tenendo conto delle correlazioni.
    """
```

#### 8.2.3 Drawdown Management

Implementare regole di drawdown:
- **Drawdown > 10%:** Riduci Kelly del 50%
- **Drawdown > 20%:** Riduci Kelly del 75%
- **Drawdown > 30%:** Stop trading, review completa del modello
- **Recovery:** Solo quando il bankroll ritorna al precedente max storico, riallineare Kelly

### 8.3 Arbitrage Detection

Creare un modulo di arbitrage:
- Confronta quote tra 5+ bookmaker
- Identifica opportunità di arbitrage dove l'implicita probabilità combinata < 100%
- Calcola il profitto garantito e le quote ottimali per bookmaker

**Limitazioni legali:** In Italia, l'arbitrage è legale ma i bookmaker potrebbero limitare il conto.

---

## 9. DATA PIPELINE: QUALITÀ, COMPLETEZZA E FRESHNESS

### 9.1 Data Quality Audit

Il sistema attuale non ha un audit di qualità dei dati. Proporre:

#### 9.1.1 Automated Data Validation

```python
import pandera as pa

schema = pa.DataFrameSchema({
    "tourney_date": pa.Column(pa.DateTime, nullable=False),
    "winner_id": pa.Column(pa.String, nullable=False),
    "loser_id": pa.Column(pa.String, nullable=False),
    "surface": pa.Column(pa.String, pa.Check.isin(["Hard", "Clay", "Grass"])),
    "target": pa.Column(pa.Int, pa.Check.isin([0, 1])),
    # ... tutte le feature con vincoli
})

# Valida ad ogni step della pipeline
schema.validate(df)
```

#### 9.1.2 Freshness Monitoring

- Alert se i dati non sono aggiornati da >7 giorni
- Alert se il numero di partite nella settimana corrente è significativamente sotto la media storica
- Monitoraggio dell'API TheOddsAPI (latenza, missing matches)

#### 9.1.3 Completeness Report

Generare un report settimanale:
- % di partite con statistiche complete (Sackmann)
- % di partite con quote disponibili (tennis-data.co.uk)
- % di giocatori con profili completi

### 9.2 Data Enrichment Opportunities

#### 9.2.1 Point-by-Point Data

Il dataset Sackmann include match point-by-point per i match charting. Questi dati possono essere usati per:
- Calcolare la probabilità di break per ogni tipo di servizio
- Analizzare i pattern di gioco (serve-and-volley vs baseline)
- Identificare pattern di fatigue