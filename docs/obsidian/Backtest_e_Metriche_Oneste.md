---
tags:
  - backtest
  - leakage
  - metriche
---

# Backtest e Metriche Oneste

Pagina di verità del progetto: numeri leak-free e storia dei falsi positivi.
Storico delle run in `reports/metrics_history.csv` (append via `scripts/log_metrics_history.py`).

## Metriche correnti (2026-06-12, dopo E2+E3+E4 "routed", train 2005-2023, val 2024, test 2025+)

| Metrica | 06-09 (baseline) | 06-12 (E2+E3+E4) |
|---|---|---|
| Accuracy routed (test 2025+) | 66.3% | **67.7%** |
| Log Loss | 0.608 | **0.601** |
| ROC AUC | 0.731 | **0.740** |
| Odds-ensemble su righe con quote | — | **69.85%** |
| Favorito B365 (baseline mercato) | 67.7% | 67.7% |
| Backtest onesto (Kelly/4, edge>3%, quote reali) | ROI −82% | **ROI −62%, win rate 46%** |

**Verdetto onesto (verificato 2026-06-12):** E2/E3/E4 = miglioramento REALE e persistito
(accuracy +1.4pt, per la prima volta l'odds-ensemble 69.85% supera il favorito 67.7%).
**Ma il backtest perde ancora (−62%, era −82%): più accurato ≠ redditizio.** Il modello
porta la quota come feature, quindi i suoi "dissensi" col mercato perdono ancora contro il
vig. **Nessun edge di scommessa — solo meno negativo.** Coerente coi check CLV di maggio.

> ⚠️ Lezione: gli esperimenti erano stati *mergiati ma mai ri-allenati* (il loop Nightly che
> li avrebbe valutati era in pausa). Un esperimento mergiato NON è un esperimento verificato.

## Il falso "85% win rate" (2026-06-09) — anatomia di un artefatto

Il vecchio `src/models/backtest.py` riportava win rate 85% e bankroll esplosivo. Quattro bug compositi:

1. **Niente scaler/mediane train**: il modello è allenato su feature StandardScaler-izzate;
   su valori raw l'output degenera (95.6% delle righe → "vince p1", p medio 0.70).
2. **Righe in POV-vincitore mai randomizzate**: nei dati p1 È il vincitore; puntare su p1
   = vincita automatica per costruzione.
3. **Quote fantasma**: le righe senza quote hanno la sentinella `implied_prob` 0.5/0.5
   (→ quota finta 2.00) e passavano il `dropna`. Da qui il flag `has_odds`
   (vedi [[Feature_Engineering]]).
4. **Quote fair de-viggate** al posto dei prezzi reali B365 (margine assente).

Il backtest riscritto fa inferenza perspective-neutral (mediane train + scaler + flip
randomizzato), prezza ai listini reali, applica Kelly/4 con cap 2% e quote min 1.30.

**Regola permanente: ogni inferenza fuori da train.py DEVE replicare il preprocessing
del training (mediane → scaler) e randomizzare la prospettiva.** Anche col preprocessing
giusto, righe non randomizzate mostrano +11pt di bias di orientamento (76% vs 65%).

## Storia dei leak (cronologia)

| Data | Leak | Numeri gonfiati | Fix |
|---|---|---|---|
| 2026-05-21 | Imputazione pre-split | acc 78.8% | mediane train-only |
| 2026-05-22 | Coppie w_/l_ spaiate | acc 77.8%, ROI +46% | `_enforce_perspective_pairs` |
| 2026-05 | Serve rolling stats (2024-25) | ROC 0.96 walk-forward | feature `_50` NaN sul 2025+ (lag Sackmann) |
| 2026-06-09 | Backtest degenere (4 bug sopra) | win rate 85% | backtest riscritto |

## Leva principale per più accuracy

Le feature serve/return `_50` sono **NaN sull'84% dei match 2025-26** (Sackmann lagga la
stagione corrente): out-of-sample il modello gira solo su elo+quote+form. Recuperare le
statistiche correnti è l'esperimento E1 in `EXPERIMENTS.md` (tetto realistico ~70-72%).

Vedi [[Modelli_e_Reti_Neurali]] per l'architettura, [[Feature_Engineering]] per il segnale.
