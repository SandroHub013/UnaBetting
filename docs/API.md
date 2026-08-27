# Local API reference

The desktop app is a FastAPI server the UI talks to over HTTP and WebSockets. It
binds `127.0.0.1:8765` and nothing else — there is no hosted deployment, and none
of this is reachable from the network. FastAPI's own `/docs` and `/redoc` are
disabled (`docs_url=None, redoc_url=None`), which is why this file exists.

Everything below is served by `src/dashboard/`: `server.py` wires four routers,
`data_api.py` holds the twenty-six REST endpoints under the `/api` prefix, and
`runner.py`, `terminal.py` and `chat.py` hold one WebSocket each.

## Access rules

Every `/api/*` request and every WebSocket goes through the same two checks in
`src/dashboard/security.py`:

1. **Origin.** A request carrying `Sec-Fetch-Site: cross-site`, or an `Origin`
   that is not exactly `http://127.0.0.1:8765` (or `localhost` on the same port),
   is refused — `403` for REST, close code `4403` for a WebSocket. The check is
   strict: credentials, a path, a query or a fragment in the origin all fail it.
   A **missing** `Origin` header is allowed, which is what keeps the CLI and the
   test client working; neither can be driven by a hostile page.
2. **Token.** If `DASHBOARD_TOKEN` is set in the environment, WebSocket
   connections must also pass `?token=<value>` or they are closed with `4401`.
   `GET /api/session` hands the token to the bundled frontend so it can do this
   automatically.

Every response carries a Content-Security-Policy with `object-src 'none'` and
`base-uri 'none'`, plus `X-Content-Type-Options: nosniff`,
`Referrer-Policy: no-referrer` and `Cross-Origin-Resource-Policy: same-origin`.

Endpoints that take a path resolve it through `_safe_path`, which refuses
anything outside the directories the app may read and raises `PermissionError` →
`403 forbidden`.

---

## Session and overview

| Method | Path | What it returns |
|---|---|---|
| `GET` | `/api/session` | `{"websocket_token": …}` — browser-only session data, `Cache-Control: no-store` |
| `GET` | `/api/overview` | Bankroll, open/closed bet counts, wins, losses, total profit, ROI %, win rate, max drawdown %, decision count, last scan. All-null shape when `betanalytix.db` does not exist yet |
| `GET` | `/api/model` | Model health: current honest metrics from `models/atp_metrics.json` plus the training history |
| `GET` | `/api/loops` | Scheduled-loop run logs from `reports/loops`, newest first |

## Bets and decisions

`betanalytix.db` is opened read-only for reads (`_ro_conn`); writes go through the
`BetAnalytix` portfolio object.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/decisions?limit=50` | Recent model decisions |
| `GET` | `/api/bets?status=` | Bets, optionally filtered by status |
| `POST` | `/api/bet` | Register a manually placed bet. JSON body; a non-object body is rejected |
| `POST` | `/api/bet/{bet_id}/resolve` | Body `{"won": true|false}` — `won` must be a JSON boolean, not a truthy value |
| `POST` | `/api/bet/{bet_id}/undo` | Reverts a resolution; the bet returns to `pending` |

## Odds and CLV

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/odds` | Matches in the latest multi-book snapshot |
| `GET` | `/api/odds?match=P1 vs P2` | Per-book h2h prices for one match |
| `GET` | `/api/clv` | Closing-line-value series, computed by `src.betting.signals.compute_clv` over the signals log and the odds history. Needs weeks of snapshots before it means anything, and returns empty until both files exist |

Only the six bookmakers in [ADR-0005](adr/0005-named-bookmakers-not-regions.md)
appear here; rows from any other book in older `odds_history` files are dropped at
read time.

## Files, media and the knowledge graph

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/tree?path=` | One directory level, lazily — path relative to the project root |
| `GET` | `/api/file?path=` | File contents for the in-app editor |
| `PUT` | `/api/file` | Body `{"path": …, "content": …}`; `content` must be a string |
| `GET` | `/api/media?path=` | Streams an image, video, audio file or PDF for in-app preview |
| `POST` | `/api/screenshot` | Captures a region of the app window from the real screen (client-area CSS coordinates plus device pixel ratio), writes it to `reports/screenshots/` and copies it to the clipboard |
| `GET` | `/api/graph` | The graphify knowledge graph from `graphify-out/graph.json`, slimmed for the 3D viewer |

`/api/tree`, `/api/file` and `/api/media` all go through `_safe_path`.

## Agentic browser

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/browse?url=` | Fetches a URL and returns its title, readable text and links. A scheme-less URL is prefixed with `https://` |

Everything this returns is untrusted input — it is a remote page.

## Configuration

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/config` | `{"path": …, "content": …}` for the active `config.yaml` — the user copy under `DATA_ROOT` if present, otherwise the bundled default |
| `PUT` | `/api/config` | Body `{"content": …}`; a body that is not JSON is a `400 bad_request` |
| `GET` | `/api/chat/config` | Current chat settings |
| `PUT` | `/api/chat/config` | Validated by `chat.save_chat_settings`; an API key is referenced by environment-variable *name* and never stored in the file |
| `GET` | `/api/chat/models?ram_gb=&vram_gb=` | Installed Ollama models ranked by full-GPU, partial-GPU or CPU fit. The two query values override hardware detection; both are bounded (`ram_gb` 1–4096, `vram_gb` 0–1024) |
| `POST` | `/api/chat/test` | Runs the chat self-test against the configured provider |

## Updater

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/update/check` | A packaged build compares its `VERSION` against the latest GitHub Release; a source checkout falls back to a git fast-forward check |
| `POST` | `/api/update/apply` | Packaged: downloads the release bundle and extracts it into `DATA_ROOT`, preserving the portfolio database, settings and config overrides. Source checkout: `git pull --ff-only` |

Extraction goes through `_extract_runtime_bundle`: the manifest's **Ed25519
signature** is verified against the baked-in public key before any member is read,
every member must resolve inside `DATA_ROOT` and match the manifest's size and
SHA-256, and the whole bundle is validated before a single byte is written.
`tests/test_updater.py` pins this; [`EXAMPLES.md`](EXAMPLES.md) shows the refusals
running. The bundle carries pickled models that `joblib.load` deserialises, and
unpickling executes code — which is why the signature check comes first. See
[`../SECURITY.md`](../SECURITY.md).

---

## WebSockets

| Path | Module | What it does |
|---|---|---|
| `/ws/run` | `runner.py` | Runs one pipeline stage and streams its output |
| `/ws/term` | `terminal.py` | A real interactive terminal — ConPTY via `pywinpty` on Windows, the standard-library `pty` on POSIX |
| `/ws/chat` | `chat.py` | The in-app assistant, defaulting to a local Ollama tool-calling model |

**`/ws/run` accepts a command *name*, never a command line.** The name is looked
up in `COMMAND_WHITELIST` and the server owns the argument vector;
`create_subprocess_exec` runs it with no shell. The eight names are `scan`,
`download`, `clean`, `features`, `train`, `backtest`, `inference` and `signals`.
`scan` spends paid odds-API credits on every run. The reasoning is in
[ADR-0004](adr/0004-the-runner-takes-a-name.md).

`/ws/chat` reaches the rest of the app through a fixed tool list — it can query
the data API, search the Obsidian vault, query the knowledge graph and persist
memories, and it cannot reach anything the whitelist does not already name.
Widening that list is a human review.

## Errors

Failures come back as JSON with an `error` key and a matching HTTP status —
`403 forbidden` for a path outside the allowed roots or a cross-origin request,
`400` for a malformed body. Endpoints whose data does not exist yet return an
empty list or an all-null shape rather than an error: a fresh checkout has no
`betanalytix.db`, no odds history and no trained model, and the dashboard is
expected to render anyway.
