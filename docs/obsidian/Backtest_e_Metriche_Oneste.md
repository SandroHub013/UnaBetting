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
| 2026-05 | Serve rolling stats (2024-25) | ROC 0.96 walk-forward | feature `_50` NaN sul 2025+ |
| 2026-06-09 | Backtest degenere (4 bug sopra) | win rate 85% | backtest riscritto |
| 2026-06-12 | `_50` NaN-poison (E1) | feature serve ~53% NaN | `_num()` NaN-safe → 1.8% |

## E1 — la leva serve, FALSIFICATA (2026-06-12)

A lungo abbiamo creduto che le serve-feature `_50` fossero NaN sull'84% dei match 2025-26
per il *lag dati Sackmann*. **Falso.** I serve-stat grezzi 2021-2025 sono presenti al
94-98%; solo il 2026 in corso è sparso. Il ~53% di NaN sulle `_50` veniva da un **bug**:
`sum(m.get(k,0) or 0 ...)` — in Python `np.nan or 0` ritorna `np.nan` (NaN è truthy),
quindi **una sola partita senza stat in una finestra di 50 avvelenava l'intera somma**
(~95% di probabilità). Fix con coercizione NaN-safe `_num()` → NaN `_50` da 53% → **1.8%**.

**Esito onesto:** accuracy **neutra** (routed 67.66 → 67.36, dentro ±0.7pt di SE; LL
0.6010 → 0.6006; ROC piatto; backtest ROI −61.9% → −57.4%, sempre nessun edge).
**Lezione: Elo + quota di mercato già codificano la forza al servizio; le serve-split
esplicite sono ridondanti.** Le serve-stat NON sono la leva di accuracy. Il fix resta
(codice corretto), l'ipotesi è respinta. La leva resta da trovare (E5/E6/E7).

Vedi [[Modelli_e_Reti_Neurali]] per l'architettura, [[Feature_Engineering]] per il segnale.
