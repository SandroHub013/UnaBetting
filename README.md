# 🎾 UnaBetting — Tennis Analytics & Honest ML

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

Sistema open-source di analisi tennis (ATP/WTA): pipeline ML **leak-free**, tracking scommesse stile bet-tracker professionale, misurazione CLV contro le linee sharp, e **Mission Control** — un'app desktop con cockpit dati, terminali integrati e chat con LLM locale.

> ## ⚠️ Disclaimer onesto (leggilo davvero)
> Il modello ML di questo progetto ha **accuracy ~66.3%** sul test out-of-sample 2025+.
> Il favorito del mercato (Bet365) sta a **~67.7%**: **il modello NON batte il mercato** e i
> backtest onesti perdono soldi. Questo è uno strumento di **ricerca, tracking e disciplina
> metodologica** (CLV, leak-detection, bankroll management) — **non** una macchina da soldi.
> Se scommetti: solo su operatori legali (in Italia: concessione ADM), solo soldi che puoi
> perdere, 18+. Il gioco può causare dipendenza.

## Cosa c'è dentro

| Componente | Descrizione |
|---|---|
| **Pipeline ML** | ELO (generale/superficie/stile), forma, fatica, clutch, H2H, quote de-viggate; training temporale rigoroso (train<2024, test 2025+), randomizzazione di prospettiva anti-leak, mediane train-only |
| **Mission Control** | App desktop (pywebview): cockpit dati, file explorer + editor, pipeline runner whitelisted, terminali reali (PowerShell/WSL/tmux), chat con **LLM locale via Ollama** con tool calling, bet tracker con equity curve, 6 temi |
| **Anti-leak** | La storia di questo progetto è una caccia ai leak (3 trovati e fixati, tutti documentati). Test di regressione in `tests/`, cronologia in `docs/obsidian/Backtest_e_Metriche_Oneste.md` |
| **CLV infra** | Snapshot quote multi-book schedulati, consenso sharp no-vig (Pinnacle/Betfair), Closing Line Value per segnale — la metrica di verità |
| **Loop autoevolutivi** | Task schedulati che lanciano un agente in headless: manutenzione notturna (dati→retrain→metriche) ed esperimento settimanale dal backlog `EXPERIMENTS.md` |

## Quick start

```bash
git clone https://github.com/SandroHub013/UnaBetting.git
cd UnaBetting
pip install -r requirements.txt
cp .env.example .env        # inserisci le tue API key (the-odds-api; openrouter opzionale)

python -m src.data.download           # dati Sackmann + quote storiche tennis-data.co.uk
python -m src.data.clean              # dataset unificato
python -m src.features.build_features # feature engineering (~20 min)
python -m src.models.train            # training multi-modello + calibrazione
python -m src.models.backtest         # backtest ONESTO (quote reali, prospettiva neutra)

python -m src.dashboard               # Mission Control (finestra nativa su Windows;
                                      # altrove: python -m src.dashboard --browser)
```

Per la chat in-app serve [Ollama](https://ollama.com) con un modello tool-calling (default: `qwen3.5:9b`, configurabile via env `CHAT_MODEL`).

## Le feature del modello (estratto)

- **ELO avanzato** — globale + per superficie + "style ELO" (vs big server / vs ribattitori), K-factor adattivo per giovani, time decay
- **Rolling stats** — servizio/risposta/clutch su finestre 10/20/50 match, tie-break e deciding set
- **Forma e fatica** — EWM form, minuti ultimi 14 giorni con decadimento
- **Mercato** — implied probability de-viggata (B365→PS→Avg) + flag `has_odds`
- **Contesto** — H2H recente, ranking, età, CPI, punti da difendere

Tre target: vincitore (H2H), spread (game diff), totals (over/under).

## Architettura

```
src/
├── data/        download, pulizia, scraper quote (the-odds-api, allowlist book)
├── features/    ELO, player stats, clutch, build_features
├── models/      train (anti-leak), backtest onesto, cross-validation
├── betting/     signals (value vs sharp + CLV), portfolio (bet tracker)
├── live/        inference live, agente news, web research
└── dashboard/   Mission Control (FastAPI + pywebview + xterm.js)
```

## Contribuire

Leggi [CONTRIBUTING.md](CONTRIBUTING.md). Il backlog di esperimenti con priorità è in
[EXPERIMENTS.md](EXPERIMENTS.md) — la regola del progetto: **ogni claim di accuracy va
dimostrato leak-free** (test temporale, prospettiva randomizzata, mediane train-only),
altrimenti è un bug, non un risultato.

## Licenza

[MIT](LICENSE) — fai quello che vuoi, ma il disclaimer qui sopra viaggia col codice.
