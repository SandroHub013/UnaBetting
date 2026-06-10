# Loop settimanale — evoluzione del modello (un esperimento per run)

Sei la run settimanale di auto-evoluzione del progetto tennis-betting
(G:\tennis betting). Obiettivo: aumentare l'accuracy onesta del modello
eseguendo UN esperimento dal backlog.

## Regole vincolanti
- NON pushare mai su remote. Solo commit locali.
- NON chiamare the-odds-api o servizi a quota/pagamento.
- UN solo esperimento per run, l'implementazione più piccola possibile.
- Valutazione SOLO onesta: test temporale 2025+, prospettiva randomizzata,
  mediane train + scaler (mai fillna su test, mai righe winner-POV).
  Riferimento: docs/obsidian/Backtest_e_Metriche_Oneste.md.
- Se trovi 3 FAILED consecutivi nella sezione Done di EXPERIMENTS.md: NON
  eseguire altro, scrivi "LOOP FERMO — servono decisioni umane" in cima a
  EXPERIMENTS.md e termina.
- Budget ~60 min. Esperimento troppo grosso (es. E1 acquisizione dati)? Esegui
  solo il primo sotto-step utile e registra il progresso nel backlog, in modo
  che la run successiva continui da lì.

## Procedura

1. Leggi `EXPERIMENTS.md`: regole, baseline corrente, primo esperimento `[ ]`
   in coda (o quello con progresso parziale).
2. Implementa la modifica minima. Se tocchi feature: verifica il tilt con
   `python scripts/probe_feature_tilt.py` (nessuna feature >0.70 di tilt,
   pena leak).
3. Rigenera ciò che serve (feature build mirata o `python -m src.models.train`).
4. Valuta: `models/atp_metrics.json` (accuracy/log_loss/ROC) +
   `python scripts/log_metrics_history.py` + `python -m src.models.backtest`.
5. Decisione vs baseline scritta in EXPERIMENTS.md:
   - MIGLIORA (acc +0.3pt o LL −0.005 senza peggiorare l'altra): TIENI.
     Aggiorna la baseline nella sezione Rules.
   - NON migliora: REVERT del codice (`git checkout -- <file>` /
     `git restore`), rimetti i modelli ritrainando sulla config originale se
     necessario.
6. Aggiorna `EXPERIMENTS.md`: sposta l'esperimento in Done con data, numeri
   esatti, KEPT/FAILED e una riga di lezione appresa.
7. Aggiorna `docs/obsidian/` (tabella metriche se cambiate) e, se hai toccato
   codice, rinfresca il grafo con lo skill graphify in modalità --update se
   disponibile (altrimenti annota che va aggiornato).
8. Commit: `feat(loop): experiment <ID> — <KEPT|FAILED> <numeri chiave>`.
