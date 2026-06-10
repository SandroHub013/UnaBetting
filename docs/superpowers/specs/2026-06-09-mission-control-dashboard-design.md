# Mission Control Dashboard — Design

**Data:** 2026-06-09
**Path:** `src/dashboard/`
**Tipo:** App web locale (FastAPI backend + frontend statico stile Hermes)
**Branch:** `fix/temporal-leakage-imputation`

> **Nota sull'approvazione:** l'utente ha approvato in anticipo l'Approccio A e i pannelli del
> cockpit, e ha chiesto esplicitamente di procedere senza ulteriori domande ("procedi non mi
> chiedere più nulla"). Le scelte lasciate aperte sono state risolte con default ragionevoli,
> documentati qui sotto. Tutto è locale (`127.0.0.1`) e personale.

## Obiettivo

Una **mission control** locale da cui gestire, usare e personalizzare al 100% il progetto
tennis-betting: monitorare i dati operativi (segnali value, bet, CLV, bankroll/ROI), lanciare i
comandi della pipeline e **avviare terminali interattivi (PowerShell e WSL)** dentro la pagina.
Stile visivo coerente con il sito Hermes già presente in `docs/web/` (palette "terra battuta",
font, layout a griglia).

## Decisioni approvate / fissate

1. **Architettura:** Approccio A — singolo processo Python (FastAPI + uvicorn) su `127.0.0.1`.
2. **Terminali:** requisito non negoziabile. Terminali reali, multipli, **PowerShell + WSL**,
   via `xterm.js` (frontend) + `pywinpty`/ConPTY (backend) su WebSocket. Già `pywinpty` installato.
3. **Frontend:** vanilla JS, no build step (coerente con `docs/web/`). Riuso dei token
   CSS/font Hermes.
4. **Pipeline control:** comandi whitelisted lanciati come subprocess, output in streaming.
5. **Cockpit dati:** letti da `data/betanalytix.db` (tabelle `decisions`, `bets`, `daily_stats`),
   `data/live/odds_history.csv`, e dal motore `src/betting/signals.py`.

## Sicurezza (esplicita)

- Server **bind solo su `127.0.0.1`** (mai `0.0.0.0`). Niente esposizione di rete.
- I terminali danno una **shell completa** = esecuzione di codice arbitrario *by design*. È
  accettabile perché è uno strumento personale locale richiesto esplicitamente. Documentato, non
  un bug.
- Il pipeline-runner accetta **solo comandi da una whitelist** (mappa nome→argv), non testo libero
  (il testo libero passa dai terminali, non dai bottoni).
- Token di sessione opzionale (`DASHBOARD_TOKEN`): se settato in env, le connessioni WebSocket lo
  richiedono come query param. Default: nessun token (solo-locale).

## Architettura file

```
src/dashboard/
├── __init__.py
├── __main__.py          # entrypoint: python -m src.dashboard  → uvicorn 127.0.0.1:8765
├── server.py            # app FastAPI: monta static, registra router
├── config.py            # costanti: host/porta, path progetto, whitelist comandi, shell map
├── data_api.py          # router REST: /api/overview /api/bets /api/decisions /api/clv /api/odds /api/config
├── runner.py            # WebSocket /ws/run: lancia comando whitelisted, streamma stdout/stderr
├── terminal.py          # WebSocket /ws/term: sessione pywinpty (powershell|wsl), pump bidirezionale
└── static/
    ├── index.html       # shell SPA: header, nav tab, contenitori pannelli + terminali
    ├── style.css         # token Hermes (riuso/port da docs/web/style.css) + layout dashboard
    └── app.js           # fetch dati, render pannelli, gestione tab terminali (xterm.js via CDN)
```

`pyproject`/requirements: aggiungere `fastapi`, `uvicorn[standard]`. `pywinpty` già presente; va
aggiunto a `requirements.txt` per riproducibilità.

## Backend — endpoint

### REST (router `data_api.py`)
| Metodo | Path | Restituisce |
|--------|------|-------------|
| GET | `/api/overview` | Riepilogo: bankroll, n. bet aperte/chiuse, ROI, profit, win-rate, drawdown (da `bets`/`daily_stats`) |
| GET | `/api/bets?status=` | Lista bet (filtrabile per status) |
| GET | `/api/decisions?limit=50` | Ultime decisioni/segnali (da `decisions`), con edge, value_side, kelly, prob ML/news |
| GET | `/api/clv` | Serie CLV calcolata da `odds_history.csv` (riuso logica `signals.py`) |
| GET | `/api/odds?match=` | Ultimo snapshot quote multi-book per match |
| GET | `/api/config` | Contenuto `config/config.yaml` (per pannello personalizzazione) |
| PUT | `/api/config` | Salva `config/config.yaml` (con backup `.bak` prima della scrittura) |

Tutti read-only tranne `PUT /api/config`. Errori → JSON `{error, detail}` con status appropriato.
DB aperto in sola lettura (`mode=ro`) per gli endpoint GET.

### WebSocket pipeline runner (`runner.py`) — `/ws/run`
- Client invia `{cmd: "<nome-whitelist>"}`.
- Server risolve `nome` → argv dalla whitelist, lancia `subprocess` (cwd = root progetto),
  streamma righe stdout/stderr come messaggi `{type:"line", stream, text}`, chiude con
  `{type:"exit", code}`.
- Whitelist iniziale: `download` → `python -m src.data.download`; `clean` → `python -m src.data.clean`;
  `features` → `python -m src.features.build_features`; `train` → `python -m src.models.train`;
  `inference` → `python -m src.live.inference`; `signals` → `python -m src.betting.signals`.
- Un comando alla volta per connessione; bottone "stop" → termina il processo.

### WebSocket terminale (`terminal.py`) — `/ws/term?shell=powershell|wsl`
- Apre una `PtyProcess` (pywinpty) con la shell scelta: `powershell.exe` o `wsl.exe`.
- Pump bidirezionale: byte da WS → `pty.write`; output `pty.read` → WS (testo).
- Messaggio di resize `{type:"resize", cols, rows}` → `pty.setwinsize`.
- Chiusura WS → termina il processo PTY. Più connessioni = più terminali indipendenti.

## Frontend — struttura

SPA a tab (no router hash necessario, una pagina con sezioni commutabili):

- **Header** stile Hermes: logo `mission_control`, tab nav uppercase: `Overview · Segnali · Bet · CLV · Quote · Pipeline · Terminali · Config`.
- **Overview**: card metriche (bankroll, ROI, profit, win-rate, drawdown, bet aperte) — da `/api/overview`.
- **Segnali**: tabella ultime `decisions` con edge/value_side/kelly/prob; evidenzia edge positivo.
- **Bet**: tabella bet con status/profit/bankroll_after.
- **CLV**: grafico a linee (canvas leggero, no lib pesante) della serie CLV + nota "serve accumulo settimane".
- **Quote**: ultimo snapshot multi-book per match selezionato.
- **Pipeline**: i 6 bottoni comando + riquadro output streaming (stile CLI Hermes, mono) + stop.
- **Terminali**: barra "+ PowerShell" / "+ WSL" che apre tab terminale; ogni tab è un `xterm.js`
  collegato a `/ws/term`. Tab chiudibili. xterm.js + addon-fit via CDN.
- **Config**: editor testo di `config/config.yaml` con "Salva" (PUT) e conferma backup.

Stile: porta i token da `docs/web/style.css` (`--bg #EFE7D2`, `--surface`, `--ink`, `--accent
#2E6B3F`, `--accent-2 #C75A2A`, mono Courier). Niente effetti canvas pesanti del sito vetrina —
qui priorità a densità informativa e leggibilità.

## Flusso dati

```
Browser (app.js)
  ├─ fetch /api/* ───────────► data_api.py ──► sqlite (ro) + odds_history.csv + signals.py
  ├─ WS /ws/run ────────────► runner.py ─────► subprocess(python -m ...) ──► stream stdout
  └─ WS /ws/term (xterm.js) ─► terminal.py ──► pywinpty(powershell|wsl) ◄──► I/O bidirezionale
```

## Gestione errori

- Endpoint REST: try/except → JSON errore + status 4xx/5xx; mai 500 nudo.
- DB mancante/tabella vuota: rispondere con struttura vuota coerente (`[]`, zero-metriche), non errore.
- Runner: comando fuori whitelist → rifiuto `{type:"error"}`. Subprocess che fallisce → exit code
  propagato, non eccezione.
- Terminale: shell non disponibile (es. WSL non installato) → messaggio chiaro al client, chiusura
  pulita del WS.
- Frontend: stato di errore per pannello (banner), non pagina bianca.

## Test / Verifica

- Avvio: `python -m src.dashboard` → apre `http://127.0.0.1:8765`.
- Checklist:
  - [ ] Overview mostra metriche reali dal db (491 decisions, 1 bet).
  - [ ] Tab Segnali/Bet popolano le tabelle.
  - [ ] Pipeline: lanciare `signals` mostra output in streaming e exit code.
  - [ ] Terminale PowerShell: apre, esegue `dir`, risponde, resize ok.
  - [ ] Terminale WSL: apre se WSL installato, altrimenti messaggio chiaro.
  - [ ] Config: legge `config.yaml`, salva con backup `.bak`.
  - [ ] Server risponde solo su `127.0.0.1`.
- Test automatici minimi: `tests/test_dashboard_api.py` — endpoint REST con DB temporaneo
  (overview/bets/decisions ritornano JSON valido; comando fuori whitelist rifiutato).

## Scope / Fasi

Tutto in un'unica build (vertical slice completo), ordine di costruzione:
1. Scheletro: `server.py` + `__main__.py` + static vuoti + `python -m src.dashboard` che serve la pagina.
2. **Terminali** (priorità esplicita utente): `terminal.py` + xterm.js, PowerShell + WSL.
3. Cockpit dati: `data_api.py` + pannelli Overview/Segnali/Bet/CLV/Quote.
4. Pipeline runner: `runner.py` + pannello Pipeline.
5. Config editor + test minimi.

## Non-goal

- Niente esposizione di rete / auth multiutente / deploy pubblico.
- Niente editor file completo tipo VS Code (per quello c'è il terminale).
- Niente nuove feature ML o modifiche alla pipeline esistente — la dashboard la *orchestra*, non la cambia.
- Niente build step / npm (xterm.js da CDN, JS vanilla).
