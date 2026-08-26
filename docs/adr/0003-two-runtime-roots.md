# 0003 — Two runtime roots: read-only bundle, writable data

**Status:** accepted

## Context

The same code has to run in two situations that disagree about where files live.

In a source checkout everything is under the repo: models, config, the SQLite
portfolio, the live caches. In a packaged (PyInstaller) build the application
sits in a read-only location and is *replaced wholesale* by an update, while
`data/betanalytix.db` holds the user's real wagering history and must survive
that replacement. A single `PROJECT_ROOT` cannot be both.

The failure this guards against is specific and unrecoverable: an update or a
reinstall overwriting a user's bet history.

## Decision

`src/runtime_paths.py` resolves two roots, and every runtime path goes through
one of them.

- **`BUNDLE_DIR`** — read-only, ships inside the app. `sys._MEIPASS` when frozen,
  the repo root otherwise. Static UI assets, the seed models, the default config.
- **`DATA_ROOT`** — writable and persistent. The repo root in dev; the per-OS
  application-data directory when frozen (`%LOCALAPPDATA%`, `~/Library/
  Application Support`, `$XDG_DATA_HOME`). Overridable with
  `UNABETTING_DATA_DIR` for portable installs and tests.

`seed_data_root()` copies the bundled seed into `DATA_ROOT` on first launch and
**skips any file that already exists**. That single condition is the guarantee:
the installer physically cannot reach a file the user already has.

Config resolution follows the same rule — a user-updated `config.yaml` under
`DATA_ROOT` wins, and the bundled one is the fallback.

## Consequences

**What it buys.** A packaged build is updatable without a migration step, and a
user who reinstalls keeps their history. It also means the first launch of a
packaged build is useful immediately: the seed carries models and inference data,
so a new user does not have to download a multi-gigabyte raw dataset or run a
twenty-minute pipeline before the app shows anything.

**What it costs.** Two roots is one more thing to get wrong, and getting it wrong
is invisible in development — in a source checkout `BUNDLE_DIR == DATA_ROOT`, so
a module that reaches for the wrong one still works, and only fails once frozen.
The discipline is that runtime modules resolve through `DATA_ROOT` and only
genuinely shipped, never-written resources use `BUNDLE_DIR`.

That invisibility is also why the decision survives: it costs a contributor
nothing to ignore, right up until they package a build.
