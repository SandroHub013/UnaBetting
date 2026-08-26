# 0004 — The run WebSocket takes a command *name*, never a command line

**Status:** accepted

## Context

The desktop app has buttons that run pipeline stages and stream their output back
to the browser. The direct implementation is a WebSocket that accepts a command
string and runs it — and that is a remote shell with a nice progress bar,
reachable by anything that can open a WebSocket to loopback.

It is tempting to argue the risk away: the server binds `127.0.0.1`, so who could
reach it? A local page in the user's own browser could, which is exactly the
attacker this app has.

## Decision

`/ws/run` accepts a **key**, not a command. The key is looked up in
`COMMAND_WHITELIST` (`src/dashboard/config.py`), which maps eight names — `scan`,
`download`, `clean`, `features`, `train`, `backtest`, `inference`, `signals` — to
argument vectors the server owns. The process is started with
`create_subprocess_exec` and an argument list; no shell is involved, and the
client has no way to express a command that is not already in the map.

The app does have free-form execution — real terminals on `/ws/term`, ConPTY on
Windows and a POSIX PTY elsewhere. That endpoint is honest about being a
terminal, and it is a separate decision with separate consequences.

Both WebSockets go through `authorize_websocket`, which enforces the loopback
origin and, when `DASHBOARD_TOKEN` is set, an explicit session token.

## Consequences

**What it buys.** The runner's authority is a fixed, readable list of eight
entries. Reviewing it means reading one dictionary, not auditing an escaping
routine — and the class of bug where a quoting fix in one layer re-opens
injection in another cannot occur, because no string is ever parsed as a command.

**What it costs.** Every new pipeline entry point needs a whitelist entry; the UI
cannot invent one. That is friction by design, and it is the friction that makes
the review meaningful — a change to `COMMAND_WHITELIST` is visible in a diff in a
way that a new argument to a generic runner would not be.

It also means the whitelist carries knowledge that belongs elsewhere: the `scan`
entry is a `-c` one-liner that fetches odds and then runs inference, and it notes
in a comment that it spends paid API credits per run. That is the kind of thing
that wants to be a module rather than a string in a config file.
