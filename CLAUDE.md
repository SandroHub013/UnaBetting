# UnaBetting — guide for Claude

Tennis analytics (ATP/WTA): a leak-free ML pipeline plus a desktop app, TUI, website
and self-evolving loops. The project's one non-negotiable value: **accuracy proven
honestly**. Any accuracy claim that isn't leak-free is a bug, not a result.

## Setup & commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # optional: CPU wheel, avoids ~5 GB CUDA
pip install -r requirements.txt
```

| What | Command |
|---|---|
| Tests | `python -m pytest tests/ -q` — must be green; 2 `@slow` skips are expected without the real dataset |
| Pipeline | `python -m src.data.download` → `src.data.clean` → `src.features.build_features` → `src.models.train` → `src.models.backtest` |
| Desktop app | `python -m src.dashboard` (Windows native window); `--browser` or `--server-only` on Linux/macOS. Serves **http://127.0.0.1:8765** (not 8000) |
| Terminal UI | `python -m src.ui.app` (Textual; audio deps optional) |
| Data refresh | `python update_data.py [--retrain] [--check]` |
| Publish metrics | `python scripts/publish_metrics.py` (README + site from `models/atp_metrics.json`) |

## Fresh-clone gotchas

- **No datasets ship with the repo.** `download` fetches Sackmann + tennis-data.co.uk,
  but ATP cleaning (`src/data/clean.py`) also requires `data/raw/TML-Database/`
  (github.com/Tennismylife/TML-Database) which nothing clones automatically — known gap.
- Trained artifacts (`models/*.pkl`, scaler, medians, `atp_metrics.json`) are gitignored;
  run `train` to produce them. `backtest` and the leak tests explain what's missing.

## Leak-free golden rules (features / training / evaluation changes)

1. **Temporal split only** — train < validation_years < test (`test_start_year: 2025`
   in `config/config.yaml`); never random.
2. **Perspective randomization** — raw rows are winner-POV (`w_*`/`l_*`); any
   evaluation on non-randomized rows is inflated by construction.
3. **Train-only imputation** — medians from the train window, never the full dataset.
4. **Perspective pairs** — every `w_X` needs its `l_X` twin; `_enforce_perspective_pairs`
   in `src/models/train.py` guarantees it — don't bypass.
5. **Tilt probe** — new feature ⇒ `python scripts/probe_feature_tilt.py`; a single
   feature "guessing" the winner > 70% is a leak, not a signal.
6. `prepare_training_data` returns a **13-tuple** (X/P/y per split + scaler,
   feature_names, medians, player_mapping) — keep unpackings in sync.
7. ML claims need **before/after numbers** from a real `train` + `backtest` run
   (results land in `models/atp_metrics.json`; log to `reports/metrics_history.csv`).
   A merged experiment is NOT a verified one (see EXPERIMENTS.md, 2026-06-12 lesson).

## Map

- `src/data` — download, clean → `data/processed/*_unified.csv`, odds scraper
- `src/features` — ELO / rolling stats / clutch → `data/features/*_features.csv`
- `src/models` — train (anti-leak, E4 odds/blind routing), honest backtest, CV
- `src/betting` — signals (CLV vs sharp consensus) + `BetAnalytix` portfolio
  (`data/betanalytix.db`). **Never touch live betting code without the human.**
- `src/live` — live inference → `data/live/predictions.json`, news/agentic research
- `src/dashboard` — FastAPI + pywebview app; `src/ui` — Textual TUI. Both read the
  same `betanalytix.db` and `models/atp_metrics.json`.
- `scripts/loops/` — scheduled agent prompts; `EXPERIMENTS.md` — ML backlog & journal
- `src/runtime_paths.py` — `BUNDLE_DIR` (read-only, ships with the app) vs `DATA_ROOT`
  (writable; repo root in dev, per-OS app-data dir in packaged builds; override with
  `UNABETTING_DATA_DIR`). Runtime modules resolve paths through `DATA_ROOT`.

## Conventions

- Conventional Commits, English: `type(scope)` with scopes
  `models|data|features|dashboard|loops|web|docs|video|security`.
- English for code/comments/docs (legacy Italian strings exist; new code in English).
- `pathlib.Path`, explicit UTF-8 IO, catch *specific* exceptions, log the unexpected.
- Windows is first-class, Linux/macOS must keep working: guard OS-specific imports
  (`winpty`, `pty`, `webview`, `pygame`…) behind try/except with a working fallback.
- Frontend: vanilla JS, no build step; themes via CSS variables; user-facing strings
  through the `t()` i18n dictionary.

## Security

- Never commit secrets (`.env`, `github_pat_…`, `sk-…`) or personal data
  (`betanalytix.db*`, screenshots, `*.mp4`). If `git status` shows one — stop.
- File-serving endpoints go through `_safe_path` (`src/dashboard/data_api.py`).
- Server binds 127.0.0.1 only; `/ws/run` is whitelist-only; widening the in-app LLM
  tool whitelist requires human review.
- The in-app updater (`/api/update/apply`) extracts release bundles via
  `_extract_runtime_bundle`: members must resolve inside `DATA_ROOT`, be listed in
  the bundle's manifest with a matching size+sha256, and the whole bundle is
  validated before any write — don't bypass it (tests in `tests/test_updater.py`).
  The manifest gives **integrity, not authenticity** (it ships inside the same zip),
  so trust rests on HTTPS from the project's own GitHub Releases. **Follow-up before
  wide distribution:** sign the manifest and verify against a key baked into the
  read-only `BUNDLE_DIR` — the bundle ships pickled models that `joblib.load` runs.
- Public pushes are additive only — never force-push.
