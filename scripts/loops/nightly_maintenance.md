# Loop notturno — manutenzione e refresh modello

Sei la run notturna automatica del progetto tennis-betting (G:\tennis betting).
Esegui questi step IN ORDINE. Sii conservativo: se uno step fallisce, annota e
prosegui se possibile; non improvvisare fix strutturali (quello è compito del
loop settimanale).

## Regole vincolanti
- NON pushare mai su remote. Solo commit locali sul branch corrente.
- NON chiamare the-odds-api o altri servizi a quota/pagamento.
- NON modificare la coda di EXPERIMENTS.md (solo il loop settimanale può).
- Ogni inferenza fuori da train.py DEVE usare mediane train + scaler + prospettiva
  randomizzata (vedi docs/obsidian/Backtest_e_Metriche_Oneste.md).
- Budget: se superi ~30 minuti di lavoro, chiudi con commit di quanto fatto.

## Step

1. **Stato repo**: `git status --short`. Se ci sono modifiche non committate non
   tue, NON toccarle; lavora intorno.
2. **Dati**: `python update_data.py --check`. Se segnala dati nuovi:
   `python update_data.py` (git pull Sackmann/TML + quote tennis-data.co.uk +
   rebuild features — può richiedere ~20 min). Se nessun dato nuovo, salta al
   punto 5.
3. **Retrain**: `python -m src.models.train` (solo se le feature sono state
   ricostruite al punto 2).
4. **Log metriche**: `python scripts/log_metrics_history.py`.
5. **Backtest onesto**: `python -m src.models.backtest`. Annota ROI e win rate.
6. **Guardia regressione**: confronta le ultime due righe di
   `reports/metrics_history.csv`. Se accuracy cala >1 punto o log_loss sale
   >0.01: scrivi un avviso in cima a EXPERIMENTS.md sezione "## Alerts" (creala
   se manca) con data e numeri — è l'unico caso in cui puoi toccare quel file.
7. **Obsidian**: se le metriche correnti sono cambiate, aggiorna la tabella in
   `docs/obsidian/Backtest_e_Metriche_Oneste.md` e lo Status in
   `docs/obsidian/Index.md`.
8. **Commit**: `git add` dei file toccati + commit con messaggio
   `chore(loop): nightly maintenance YYYY-MM-DD — <esito sintetico>`.
   Se non è cambiato nulla, NON committare; termina con "nessun aggiornamento".
