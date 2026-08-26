# 0005 — Request named bookmakers, not whole regions

**Status:** accepted (2026-06-10)

## Context

Live odds come from the-odds-api, which bills per request and lets a caller ask
either for whole regions (`eu`, `uk`) or for a named list of bookmakers. Regions
is the obvious default and returns everything.

Everything is the problem. Two different things are wanted from an odds feed and
only two: a **sharp reference** to measure closing-line value against, and the
**venues a bet can actually be placed at** — which, in Italy, means an operator
with an ADM concession. Every other book in the response is a row that will be
filtered out downstream, after being paid for.

## Decision

Request the six books by name:

```
pinnacle, williamhill, sport888, marathonbet, betfair_ex_eu, betfair_ex_uk
```

Pinnacle and the Betfair exchanges are the sharp reference for the no-vig
consensus; the rest are execution venues. Regions stay configured as a fallback
for when the bookmaker list is empty.

The list is duplicated in three places on purpose — `config/config.yaml`,
`ALLOWED_BOOKMAKERS` in `src/dashboard/config.py`, and `ALLOWED_BOOKS` in
`src/betting/signals.py` — because the pipeline, the UI and the signal generator
must not be able to disagree about which books count.

## Consequences

**What it buys.** Fewer credits per scan, and a response with no rows that exist
only to be discarded. The CLV measurement gets a stable sharp reference rather
than whatever happened to be in the region that day, which matters because CLV is
a comparison against a *specific* closing line, not against an average of
whatever was available.

**What it costs.** Three copies of one list, kept in sync by a comment. That is
the wrong shape and it is written down here rather than pretended away: the right
fix is one source of truth read by all three, and the reason it has not been done
is that two of the three are import-time constants in modules that must not
import the pipeline config.

Adding a bookmaker also means editing three files and thinking about which of the
two roles it plays. A book added as an execution venue but treated as sharp would
quietly corrupt every CLV number that followed.
