# Loop settimanale — code review di modelli e sistema

Sei la run settimanale di review di UnaBetting (G:\tennis betting). Obiettivo:
trovare bug, debolezze metodologiche e opportunità di miglioramento CONCRETE
nel codice di modelli e sistema, per raggiungere risultati migliori.

## Regole
- NON pushare su remote. Solo commit locali.
- NON modificare il codice in questa run: produci la review; i fix passano dal
  backlog (EXPERIMENTS.md) o dal loop weekly_evolution.
- Eccezione: bug evidenti e a rischio zero (typo, import rotto, test rotto) —
  fixali subito con commit separato `fix(review): ...`.
- Budget ~60 minuti.

## Focus (a rotazione, scegli l'area meno recentemente coperta leggendo
   reports/reviews/)
1. `src/models/` — train, backtest, cross_validate: leak residui, calibrazione,
   split, metriche.
2. `src/features/` — elo, player_stats, build_features: correttezza temporale,
   NaN handling, feature inutilizzate.
3. `src/betting/` + `src/live/` — signals, portfolio, inference: coerenza
   allowlist book, edge cases, error handling.
4. `src/dashboard/` — sicurezza endpoint, robustezza WS, qualità JS.

## Output
- Scrivi `reports/reviews/review_YYYY-MM-DD_<area>.md`: findings ordinati per
  severità, ognuno con file:riga, problema, fix proposto, impatto stimato.
- I findings ad alto impatto su accuracy/correttezza vanno ANCHE aggiunti come
  esperimenti `[ ]` in coda a EXPERIMENTS.md (formato E<n>).
- Aggiorna `docs/obsidian/Index.md` se emergono problemi strutturali.
- Commit: `docs(review): weekly code review — <area>, <n> findings`.
