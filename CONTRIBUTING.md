# Contribuire a UnaBetting

Grazie! Questo progetto vive di rigore metodologico: il valore non è "più accuracy"
ma **accuracy dimostrata onestamente**.

## La regola d'oro: niente leak

Ogni modifica a feature/training/valutazione DEVE rispettare:

1. **Split temporale**: train su anni passati, test su 2025+ — mai random split.
2. **Prospettiva randomizzata**: i dati grezzi hanno `w_` = vincitore; ogni valutazione
   su righe non randomizzate è gonfiata per costruzione (vedi
   `docs/obsidian/Backtest_e_Metriche_Oneste.md` per i disastri storici).
3. **Imputazione train-only**: mediane calcolate sul train, mai su tutto il dataset.
4. **Coppie di prospettiva**: ogni feature `w_X` deve avere la gemella `l_X`
   (`_enforce_perspective_pairs` lo garantisce — non aggirarlo).
5. **Tilt check**: nuova feature? `python scripts/probe_feature_tilt.py` — se una
   feature singola "indovina" il vincitore >70% delle volte, è un leak, non un segnale.

## Workflow

1. Scegli un esperimento da `EXPERIMENTS.md` (o proponine uno via issue).
2. Branch da `main`, implementazione minima.
3. Valuta: `python -m src.models.train` + `python -m src.models.backtest` +
   `python -m pytest tests/`.
4. PR con i numeri PRIMA/DOPO (accuracy, log loss, ROC) e come li hai ottenuti.
   Claim senza numeri riproducibili = PR respinta con affetto.

## Setup ambiente

Vedi il Quick start nel [README](README.md). Su Windows l'app desktop usa
pywebview/WebView2 e pywinpty; su Linux/macOS gira con `python -m src.dashboard --browser`.

## Cosa NON committare

`.env` (API key), `data/` (dataset rigenerabili), DB personali (`betanalytix.db`),
screenshot/log personali. Il `.gitignore` copre già tutto: se `git status` ti mostra
un file di dati personali, fermati e controlla.

## Stile

Python: segui il codice esistente (type hints leggeri, docstring corte, commenti solo
dove il codice non parla da solo). Frontend: vanilla JS, niente build step.
