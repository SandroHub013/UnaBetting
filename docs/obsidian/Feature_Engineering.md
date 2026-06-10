---
tags:
  - features
  - pruning
---

# Feature Engineering: Il Segnale e il Rumore

Sulla base delle analisi del *Giudice delle Feature*, il dataset di addestramento è in fase di sfoltimento per combattere la **Curse of Dimensionality** (maledizione della dimensionalità) e la collinearità.

## 🟢 Feature Core (Mantenute)
Queste colonne rappresentano l'ossatura predittiva per i modelli ad albero e le future reti neurali:
1.  **ELO Rating Avanzato**: Assoluto, per superficie e il nuovissimo **Style ELO** (`vs_server_elo`, `vs_returner_elo`) che calcola dinamicamente quanto un giocatore sia bravo a battere specifiche tipologie di avversario.
2.  **Statistiche di Servizio (`hold_pct`, `bp_save_pct`)**: L'attitudine al servizio è il metronomo del tennis maschile.
3.  **Statistiche di Ritorno e Clutch SOTA**: Oltre alle classiche metriche in risposta (`return_pts_win_pct_50`), ora il sistema traccia performance critiche come vittorie nei tie-break (`tiebreak_win_pct`), prestazioni al quinto/terzo set (`deciding_set_win_pct`) e percentuali di vittoria contro i mancini (`vs_lefty_win_pct`).
4.  **Forma e Momentum (`form_ewm`)**: Una media mobile esponenziale per misurare la fiducia recente del giocatore, reagendo più velocemente dell'ELO.
5.  **Court Pace Index (CPI) e Punti da Difendere**: Metriche SOTA che incorporano la velocità reale del campo e la pressione piscologica legata ai punti ATP in scadenza nel torneo in corso.
6.  **Head-to-Head (H2H) Recente**: Storico degli scontri diretti limitato agli ultimi anni.
7.  **Contestuali**: indicatori `w_is_seeded`/`l_is_seeded`, `age_diff`, `height_diff` e i flag di **mano** `w_is_lefty`/`l_is_lefty`.
8.  **Probabilità implicite di mercato + `has_odds`**: `w/l_implied_prob` (B365→PS→Avg, de-viggate). Le righe senza quote vengono riempite con la sentinella 0.5/0.5: il flag `has_odds` (aggiunto 2026-06-09) permette al modello — e al backtester — di distinguere informazione di mercato reale dal riempimento. Solo ~32% delle righe storiche (e ~65% di quelle recenti) ha quote reali.

## 🔴 Feature Prunate o Modificate
-  **Finestre Multiple Temporali**: Ricalcolare tutto su 10, 20 e 50 match genera solo rumore. Ora si calcolano le *skill tecniche* sul lungo termine (50) e la *forma* sul breve (10).
-  **Colonne Differenziali (`diff_`)**: Reintegrate tramite un sistema di auto-diff in `build_features.py`. Sebbene si pensasse che i Decision Trees creassero i differenziali da soli tramite gli split, fornirli matematicamente pre-calcolati (es. `diff_form_ewm`) si è rivelato fondamentale per incrementare l'accuratezza pura oltre il 67.5% e l'R2 della regressione.
-  **Fatica a Decadimento**: Invece della fatica passiva, utilizziamo un decadimento temporale intelligente dei minuti giocati negli ultimi 14 giorni (`decay_minutes_14d`).

Vedi [[Modelli_e_Reti_Neurali]] per capire come questi dati puliti verranno processati.
