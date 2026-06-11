# Loop settimanale — docs, traduzione e sync repo pubblica

Sei la run di sincronizzazione documentazione/repo di UnaBetting
(G:\tennis betting). La repo pubblica è github.com/SandroHub013/UnaBetting.

## Regole
- Push SOLO con il flusso snapshot: branch orfano `public-main` → push force su
  `unabetting main`. MAI pushare la cronologia privata, MAI il remote `origin`.
- Prima di OGNI push: `git ls-files` non deve contenere `betanalytix.db`,
  `debug_bet365*`, `Cattura.PNG`, `.antigravitycli`, screenshot personali;
  `git grep -iE "api[_-]?key.{0,6}[A-Za-z0-9]{16}|github_pat_|sk-or-"` deve
  essere vuoto. Se trovi qualcosa: FERMATI, non pushare, scrivi alert.
- Budget ~60 minuti.

## Step
1. **Inglese**: porta avanti la traduzione in inglese di README.md,
   CONTRIBUTING.md, DATA_SOURCES.md e delle stringhe UI dell'app
   (`src/dashboard/static/*.js|html` — testi visibili, non i nomi di funzione).
   Lavora in modo incrementale: prima i file principali, poi il resto.
2. **Grafica repo**: assicurati che README abbia badge, diagrammi mermaid
   (architettura + data flow) e screenshot aggiornati da `docs/assets/`
   (se mancano screenshot, generali: avvia `python -m src.dashboard --server-only`,
   usa POST /api/screenshot... solo se l'app è già aperta; altrimenti salta).
3. **Obsidian/sito**: allinea `docs/obsidian/Index.md` e `docs/web/` allo stato
   corrente del progetto (nuove feature, metriche, loop).
4. **Tests**: `python -m pytest tests/ -q` deve essere verde prima del push.
5. **Sync pubblico ADDITIVO (niente force-push — le PR mergiate vanno
   preservate)**:
   a. `git fetch unabetting main` e checkout di un branch locale che traccia
      `unabetting/main` (es. `public-main`), `git pull` per avere le PR mergiate
      dal loop pr_review.
   b. Copia i file pubblici aggiornati dal branch di lavoro (codice in `src/`,
      `scripts/`, `docs/` pubblici, README/CONTRIBUTING/DATA_SOURCES/LICENSE,
      `requirements.txt`, `tests/`) — NON i dati personali/gitignorati.
   c. Commit normale su `public-main` e `git push unabetting public-main:main`
      (SENZA `--force`). Torna al branch di lavoro privato.
   ⚠️ La cronologia privata NON si pubblica mai; pubblichi solo lo stato dei file
   pubblici come commit additivo. Se un push richiederebbe force, FERMATI: c'è
   divergenza, segnala invece di forzare.
6. Commit locali per ogni blocco + `chore(loop): docs/repo sync YYYY-MM-DD`.
