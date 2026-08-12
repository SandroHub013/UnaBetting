# Security policy

## Reporting a vulnerability

Report privately — do not open a public issue.

- GitHub private advisories: **Security → Report a vulnerability** on this
  repository.
- Email: boni.alessandro997@gmail.com

Expect an acknowledgement within 3 working days and an assessment within
10.

## What this is

A tennis analytics pipeline plus a desktop app. It runs locally: the
dashboard binds `127.0.0.1:8765` and there is no hosted service. The
interesting surface is what a local process, a malicious download or a
tampered release bundle can do to a user who runs it.

## Known gap — model bundles carry integrity, not authenticity

The in-app updater (`/api/update/apply`) extracts release bundles through
`_extract_runtime_bundle`, which requires every member to resolve inside
`DATA_ROOT` and to match the manifest's size and SHA-256 before anything
is written. Tests in `tests/test_updater.py` pin this.

That manifest ships **inside the same zip**. It proves the bundle was not
corrupted in transit; it does not prove who built it. Trust currently
rests entirely on HTTPS to this project's own GitHub Releases.

This matters because the bundle contains pickled models that `joblib.load`
deserialises, and unpickling executes code by construction. Anyone who
can serve a bundle the client accepts gets code execution.

**Planned fix:** sign the manifest and verify it against a key baked into
the read-only `BUNDLE_DIR`. Until then, do not point the updater at any
source other than this project's releases.

## What is already enforced

- **`/ws/run` is whitelist-only.** The WebSocket authorises the
  connection, then accepts a command *name* and looks it up in
  `config.COMMAND_WHITELIST`; the client never supplies a command line.
  `create_subprocess_exec` is used with an argument list — no shell.
- **File-serving goes through `_safe_path`** (`src/dashboard/data_api.py`),
  so a path from a request cannot escape the directories it is allowed
  to read.
- **The server binds `127.0.0.1` only.** It is not meant to be reachable
  from the network, and nothing in it assumes an authenticated remote
  caller beyond that.
- **The in-app LLM picks from a fixed tool list.** It cannot execute
  anything the whitelist does not already name.

## Scope

- `src/dashboard/` — the FastAPI app, the run WebSocket, the updater, the
  chat tool routing.
- `src/data/download.py` and `src/data/scraper.py` — the code that
  fetches from Sackmann, tennis-data.co.uk and the odds API. Everything
  they return is untrusted input.
- `src/betting/` — reads and writes `betanalytix.db`, which holds real
  wagering history.

## Secrets and personal data

No credentials are tracked. `.env.example` lists variable names —
`ODDS_API_KEY`, `OPENROUTER_API_KEY` — with placeholder values, and
`.env` is ignored.

`data/betanalytix.db` is personal wagering data and is never committed.

## Not a financial product

The README says the model does not beat the market, and that is a
statement about this repository's purpose, not modesty. Treat any output
as research, not advice.

## Supported versions

The `main` branch is the only supported version.
