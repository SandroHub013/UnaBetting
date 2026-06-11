---
tags:
  - ml
  - tennis
  - entrypoint
---

# UnaBetting - ML Prediction System

Questo vault contiene la documentazione di sistema (Knowledge Graph) per l'architettura di predizione ML dei match di tennis ATP.

## 🧭 Navigazione
- [[Architettura_Sistema]] - Visione d'insieme e data flow.
- [[Feature_Engineering]] - Il cuore del segnale: ELO, Statistiche e Forma.
- [[Modelli_e_Reti_Neurali]] - Dal Gradient Boosting ai Layer di PyTorch.
- [[Backtest_e_Metriche_Oneste]] - Numeri leak-free, storia dei falsi positivi, regole di inferenza.

## 🎯 Obiettivo Attuale
Il progetto è stato "ripulito" da tutto il rumore esterno (Betting, Arbitraggio, Criterio di Kelly) per focalizzarsi esclusivamente sulla componente di **pura analisi statistica e previsione**. 
L'obiettivo è estrarre il massimo *information gain* dai dati tabulari tramite alberi decisionali e integrare modelli di Deep Learning per catturare interazioni complesse tra stili di gioco (Player Embeddings).

## 📌 Status (2026-06-09)
- ✅ Risolto O(n*m) bottleneck in estrazione feature.
- ✅ Baseline onesta stabilita: ensemble 66.3% acc / LL 0.608 / ROC 0.731 (test 2025+); favorito B365 67.7%.
- ✅ Backtest realistico riscritto (il "win rate 85%" era un artefatto — vedi [[Backtest_e_Metriche_Oneste]]).
- ✅ Split aggiornato (train 2005-2023, val 2024) + flag `has_odds`.
- ⏳ E1 in coda: copertura serve-stats 2025-26 (la leva più grossa, vedi `EXPERIMENTS.md`).
- ✅ Loop autoevolutivi attivi (filosofia "write loops"): `TennisLoopNightly` (07:13, sonnet — dati+retrain+metriche), `TennisLoopWeekly` (dom 09:23, opus — un esperimento da `EXPERIMENTS.md`), `TennisLoopResultsCheck` (22:17, haiku — esiti reali da Sofascore vs previsioni → `reports/results_feedback.csv`), `TennisLoopCodeReview` (sab 10:17, opus — review modelli/sistema → `reports/reviews/`), `TennisLoopDocsSync` (ven 18:17, sonnet — traduzione EN, grafica repo, snapshot push pubblico). Runner: `scripts/loops/run_loop.ps1 -Loop <nome>` con mappa modello-per-difficoltà.
- ✅ **UnaBettingOS** (tab ✦): centro di memoria agentica — chat locale con tool su dati live, vault Obsidian (`search_knowledge`), knowledge graph (`query_graph`) e memoria persistente versionata (`UnaBettingOS_Memoria.md`).
- ✅ **Grafo 3D** (tab ❂): knowledge graph graphify renderizzato come campo stellare 3D (sprite additivi per community, `zoomToFit` che riempie la viewport, orbita automatica, ricerca nodi).
- ✅ **Browser web agentico** (tab 🌐): `/api/browse` (fetch server-side, fallback curl) → reader view con link cliccabili; tool `browse_web` per UnaBettingOS.
- ✅ **Anteprima media** nell'esplora file: `/api/media` streama immagini/video/audio/pdf; click su un media apre il viewer in-app.
- ✅ **Repo pubblica** github.com/SandroHub013/UnaBetting: snapshot pulito (commit unico, niente storia privata, niente dati personali, niente render da 80MB). Sync futuri additivi via loop DocsSync; PR gestite dal loop PRReview (Fable 5, ogni 4h).
- ✅ Licensing dati dichiarato: `DATA_SOURCES.md` (Sackmann CC BY-NC-SA 4.0 → progetto non commerciale).
- ✅ **Mission Control — app desktop** (`python -m src.dashboard`, o collegamento "Tennis Mission Control" sul Desktop): finestra nativa pywebview/WebView2 (niente browser) con layout IDE — activity bar + sidebar (cockpit dati, file explorer del progetto con editor CodeMirror e salvataggio, pipeline whitelisted, log dei loop, docs Obsidian, config con backup) e pannello terminali in basso (PowerShell/WSL reali via pywinpty + bottone ⚡VIBE che apre un terminale e lancia `claude` nel progetto). Server FastAPI interno solo su 127.0.0.1:8765. Spec: `docs/superpowers/specs/2026-06-09-mission-control-dashboard-design.md`.
