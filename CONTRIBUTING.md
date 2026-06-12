# Contributing to UnaBetting

Thanks for being here. UnaBetting is a whole product, not just a model: a leak-free
tennis ML pipeline **and** a desktop app (UnaBettingOS), a live 3D knowledge graph, a
website, self-evolving loops, and the docs that hold it together. You can contribute to
**any** of these — you don't need to touch the ML to help.

The one value we never compromise: the worth of this project isn't "more accuracy", it's
**accuracy proven honestly**. Everything below serves that.

## Contribution priorities

When picking what to work on, this is roughly the order we value most:

1. **Bug fixes** — anything broken or crashing.
2. **Methodological rigor** — closing data leaks, making evaluation more honest, better tests.
3. **Cross-platform & robustness** — Windows/Linux/macOS parity, graceful failure, security hardening.
4. **App & automation** — UnaBettingOS UX, new panels, new/better loops.
5. **New ML work** — features, models, current-season data coverage (`EXPERIMENTS.md`).
6. **Reach** — website, docs, themes, i18n languages, demo videos.

None of these are off-limits to newcomers — a typo fix and a new feature are both welcome.

## Where you can contribute (pick a pathway)

| Area | What lives there | Good first contributions |
|---|---|---|
| **Models & data** | `src/models/`, `src/features/`, `data/` ingestion, `EXPERIMENTS.md` | a new feature, a calibration tweak, current-season data coverage |
| **Desktop app / UnaBettingOS** | `src/dashboard/` — FastAPI + pywebview cockpit, real terminals, chat agent, media viewer, agentic browser, 3D graph | UX fixes, new panels, sorting/filters, accessibility |
| **Automation / loops** | `scripts/loops/`, the scheduled self-evolving pipeline | a new loop, better guardrails, smarter model-by-difficulty routing |
| **Website & docs** | `docs/web/`, `docs/obsidian/`, `README.md` | copy, design polish, diagrams, deep-dive docs |
| **Design & reach** | themes, i18n languages, HyperFrames videos (`video_mission/`) | a new theme, a UI translation, a demo clip |

Pick an item from `EXPERIMENTS.md` **(ML only)**, an open issue, or propose your own via
an issue. **One concern per PR**, branched from `main`.

## The golden rule: no leaks (ML changes only)

This applies **only if your change touches features, training, or evaluation.** App,
website, loops, docs, design, and i18n PRs can skip this section.

1. **Temporal split** — train on past years, test on 2025+ — never a random split.
2. **Randomized perspective** — raw data has `w_` = winner; any evaluation on
   non-randomized rows is inflated by construction (see
   `docs/obsidian/Backtest_e_Metriche_Oneste.md` for the historical disasters).
3. **Train-only imputation** — medians computed on the train set, never on the full dataset.
4. **Perspective pairs** — every `w_X` feature must have its `l_X` twin
   (`_enforce_perspective_pairs` guarantees it — don't bypass it).
5. **Tilt check** — new feature? run `python scripts/probe_feature_tilt.py`. If a single
   feature "guesses" the winner > 70% of the time, it's a leak, not a signal.

An ML PR that claims a gain without reproducible before/after numbers gets respectfully
sent back.

## Development setup

**Prerequisites**

| Tool | Notes |
|---|---|
| Python 3.10+ | the pipeline and app both run on it |
| git | with access to your fork |
| Windows: WebView2 | ships with modern Windows; the desktop app uses it |
| Linux/macOS | run the app in `--browser` mode (no WebView2 needed) |

**Clone & install**

```bash
git clone https://github.com/<you>/UnaBetting.git
cd UnaBetting
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

**Run the app**

```bash
# Windows desktop window (pywebview/WebView2 + pwinpty terminals)
python -m src.dashboard
# Linux/macOS (or headless): serve in the browser
python -m src.dashboard --browser
```

**Verify**

```bash
python -m pytest tests/ -q          # tests green (minus the known-skips in EXPERIMENTS.md)
python -m src.models.backtest       # honest backtest runs end-to-end
```

## Code style

- **Python**: follow the surrounding code — light type hints, short docstrings, comments
  only where the code doesn't speak for itself. Catch *specific* exceptions; log the
  unexpected with `logging` (`exc_info=True`), don't swallow silently.
- **Frontend**: vanilla JS, no build step. Themes via CSS variables + `data-theme`;
  strings via the `t()` i18n dictionary — don't hardcode user-facing text.
- **Encoding**: read/write files as explicit UTF-8 (Windows locale otherwise mangles it).
- **Language**: English — code, comments, docs, commit messages, and PRs.

## Cross-platform

Windows is a first-class target (it's where the desktop app primarily runs), Linux/macOS
must keep working too.

- Guard Unix-only modules (`pty`, `termios`, `fcntl`) behind `try/except ImportError` with
  a working fallback — the terminal/agentic-browser code already does this.
- Use `pathlib.Path`, never string path concatenation or hardcoded separators.
- Don't assume a shell: the app spawns terminals via `pwinpty` on Windows and a PTY
  elsewhere. Test both paths if you touch `src/dashboard/` terminal/process code.

## Security & safety

UnaBettingOS runs **real terminals, an agentic web browser, and a local LLM with
whitelisted tools** — so security is a real obligation, not boilerplate:

- **Never log or commit secrets** (`.env`, API keys, `github_pat_…`, `sk-…`). The PR-review
  loop scans for these and will reject a PR that contains them.
- **Never commit personal data** — `betanalytix.db`, personal screenshots/logs, `*.mp4`
  renders. `.gitignore` covers these; if `git status` shows one, stop and check.
- **Keep the chat-agent tool whitelist tight.** New tool access for the in-app LLM must be
  reviewed — don't widen it casually.
- **Validate paths** for any endpoint that reads files (`_safe_path` guards traversal — use
  it; don't bypass it). Quote/escape user input that reaches a shell.
- **Never force-push the public repo and never publish private history.** Public pushes are
  additive only (`git fetch` → commit on top → push, no `--force`).

Found a vulnerability or accidentally-published private data? Open a **private** report
(don't file a public issue with the sensitive detail in it).

## PR workflow

**Branch naming**: `fix/…`, `feat/…`, `docs/…`, `test/…`, `refactor/…`, `chore/…`

**Before you open the PR**

1. `python -m pytest tests/` is green.
2. You manually exercised your code path.
3. **If you touched the model**: `python -m src.models.train` +
   `python -m src.models.backtest`, with the **before/after numbers** (accuracy, log loss,
   ROC) in the description.
4. You considered cross-platform impact (Windows *and* Linux/macOS).
5. The PR is **one focused change**.

**PR description** should say: what changed and why, how to test it, platforms tested,
and any related issue. For ML, *how you measured* the gain.

**The review loop**: an automated PR-review loop checks open PRs **every 4 hours** — runs
the tests, scans for secrets/personal data, verifies the leak-free rules where they apply,
then **merges** good PRs (label `loop-accepted`) or **requests changes** with specific
feedback (label `loop-changes-requested`).

## Commit messages

Conventional Commits, in English:

```
<type>(<scope>): <summary>
```

- **types**: `fix`, `feat`, `docs`, `test`, `refactor`, `chore`
- **scopes**: `models`, `data`, `features`, `dashboard`, `loops`, `web`, `docs`, `video`,
  `security`
- Example: `feat(dashboard): sortable odds table` · `fix(models): train-only median reindex`

## Issue reporting

Open a GitHub issue with:

- OS + Python version, UnaBetting commit/branch
- what you expected vs what happened
- steps to reproduce + the full traceback
- a quick check that it isn't already reported

(Security or private-data issues → private report, see above.)

## License

Code is **MIT**; the datasets are **CC BY-NC-SA** (see `DATA_SOURCES.md`). By contributing,
you agree your code contributions are licensed under MIT.
