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

## Release bundles are signed, and why that is the load-bearing check

A release bundle contains pickled models, and `joblib.load` executes code
when it deserialises them. So a bundle the updater accepts is, in
practice, code the user runs. The in-app updater (`/api/update/apply`)
extracts through `_extract_runtime_bundle`, which decides acceptance in
this order and writes nothing until every step passes:

1. `manifest.json` must carry a valid **Ed25519 signature** over its own
   canonical JSON, verified against the public key baked into
   `data_api._UPDATER_PUBKEY`. An unsigned bundle is refused outright.
2. Every member must resolve inside `DATA_ROOT`.
3. Every member must match the manifest's size and SHA-256, and the
   manifest may not list files the zip does not contain.
4. Protected user paths — the portfolio database above all — are skipped
   rather than overwritten.

Validation is all-or-nothing: a bundle that fails on its last member
writes nothing at all. Tests in `tests/test_updater.py` pin every step,
and [`docs/EXAMPLES.md`](docs/EXAMPLES.md) shows each refusal running.

**The limitation that remains:** the verification key is a constant in the
source, so rotating or revoking it requires shipping a new release, and
installations already in the field keep trusting the old key until their
users update. If you have reason to believe the release key is
compromised, report it through the process below rather than opening a
public issue.

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
