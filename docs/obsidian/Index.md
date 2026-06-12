---
tags:
  - ml
  - tennis
  - entrypoint
---

# Tennis Betting - ML Prediction System

Questo vault contiene la documentazione di sistema (Knowledge Graph) per l'architettura di predizione ML dei match di tennis ATP.

## 🧭 Navigazione
- [[Architettura_Sistema]] - Visione d'insieme e data flow.
- [[Feature_Engineering]] - Il cuore del segnale: ELO, Statistiche e Forma.
- [[Modelli_e_Reti_Neurali]] - Dal Gradient Boosting ai Layer di PyTorch.
- [[Backtest_e_Metriche_Oneste]] - Numeri leak-free, storia dei falsi positivi, regole di inferenza.

## 🔗 Documentazione estesa (repo root)
- **Roadmap & Milestones:** `../roadmap/README.md`
- **Specs & ADR:** `../specs/README.md`
- **Operations Playbooks:** `../operations/README.md`

## 🎯 Obiettivo Attuale
Il progetto è stato "ripulito" da tutto il rumore esterno (Betting, Arbitraggio, Criterio di Kelly) per focalizzarsi esclusivamente sulla componente di **pura analisi statistica e previsione**. 
L'obiettivo è estrarre il massimo *information gain* dai dati tabulari tramite alberi decisionali e integrare modelli di Deep Learning per catturare interazioni complesse tra stili di gioco (Player Embeddings).

## 📌 Status (2026-06-09)
- ✅ Risolto O(n*m) bottleneck in estrazione feature.
- ✅ Baseline onesta stabilita: ensemble 66.3% acc / LL 0.608 / ROC 0.731 (test 2025+); favorito B365 67.7%.
- ✅ Backtest realistico riscritto (il "win rate 85%" era un artefatto — vedi [[Backtest_e_Metriche_Oneste]]).
- ✅ Split aggiornato (train 2005-2023, val 2024) + flag `has_odds`.
- ⏳ E1 in coda: copertura serve-stats 2025-26 (la leva più grossa, vedi `EXPERIMENTS.md`).
- ✅ Loop autoevolutivi attivi: `TennisLoopNightly` (07:13, dati+retrain+metriche) e `TennisLoopWeekly` (dom 09:23, un esperimento da `EXPERIMENTS.md`). Runner: `scripts/loops/run_loop.ps1` → `claude -p` headless; log in `reports/loops/`.
- ✅ **Mission Control — app desktop** (`python -m src.dashboard`, o collegamento "Tennis Mission Control" sul Desktop): finestra nativa pywebview/WebView2 (niente browser) con layout IDE — activity bar + sidebar (cockpit dati, file explorer del progetto con editor CodeMirror e salvataggio, pipeline whitelisted, log dei loop, docs Obsidian, config con backup) e pannello terminali in basso (PowerShell/WSL reali via pywinpty + bottone ⚡VIBE che apre un terminale e lancia `claude` nel progetto). Server FastAPI interno solo su 127.0.0.1:8765. Spec: `docs/superpowers/specs/2026-06-09-mission-control-dashboard-design.md`.
