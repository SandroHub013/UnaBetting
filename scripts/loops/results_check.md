# Loop giornaliero — riscontro risultati (Sofascore)

Sei la run giornaliera di verifica risultati di UnaBetting (G:\tennis betting).
Obiettivo: confrontare le previsioni degli scan live con gli esiti reali.

## Regole
- NON pushare su remote. NON usare API a pagamento (Sofascore via curl è gratis).
- Budget ~10 minuti.

## Step
1. `python scripts/check_results.py --days 4` — scarica gli esiti da Sofascore e
   aggiorna `reports/results_feedback.csv`.
2. Leggi il riepilogo stampato. Se l'accuracy storica del feedback live diverge
   di oltre 8 punti dal riferimento offline (66.3%) con almeno 30 match
   verificati, aggiungi un alert nella sezione `## Alerts` di EXPERIMENTS.md
   con data e numeri.
3. Se ci sono nuovi match verificati, aggiorna la riga "feedback live" nella
   tabella metriche di `docs/obsidian/Backtest_e_Metriche_Oneste.md`
   (creala se manca: "Feedback live (Sofascore) | X/Y corretti (Z%)").
4. Commit: `chore(loop): results check YYYY-MM-DD — <n> verificati, <acc>%`.
   Se nessun match nuovo verificato: nessun commit, termina con "nulla di nuovo".
