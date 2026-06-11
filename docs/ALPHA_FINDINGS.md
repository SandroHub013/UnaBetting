# Alpha Search — Findings & Roadmap

## TL;DR — alpha located (structural, not predictive)

- **Predictive alpha: NONE.** The model cannot beat the de-vigged sharp line — proven on overall calibration, every segment, and orthogonal residuals (§1). Building a predictor on a market that's already a feature is a dead end.
- **Structural alpha: YES.** 39 books disagree; line-shopping the best back price per side locks in **risk-free cross-book arbitrage** independent of outcome. On one live snapshot: **9 arbs across credible books (Pinnacle, Betfair, Marathonbet, gtbets, betonlineag, Paddy Power, Coolbet), 0.24–3.95% returns, net of exchange commission.** Tool: `src/betting/arbitrage.py` (`python -m src.betting.arbitrage`), tested. This is real, verifiable today (no outcomes needed) — the edge is in market *fragmentation*, not prediction.
- **Caveats (honest):** arb margins are mostly <1%; the larger ones (high-odds legs from a single book) carry stale-line/limit risk — the tight Pinnacle/Betfair/gtbets ones are the robust core. Books limit/ban arbers, stakes are capped, and legs must be placed fast before lines move. It's a real but operationally-constrained edge, not free money.

---


**Date:** 2026-05-22 · **Scope:** rigorous, leak-free test of whether the system has any edge over the market, and where genuine alpha could be found.
**Method:** all numbers from leak-free walk-forward (train on all years before the test year), after fixing the two leaks (imputation + perspective-pair). De-vigged B365 H2H used as the market benchmark.

---

## 1. Verdict: no alpha in the current data

The B365 **H2H market is efficient with respect to everything our features know.** Three independent tests, all negative:

| Test | Result | Reading |
|------|--------|---------|
| **Overall calibration** (Brier skill vs market) | **−0.0077** (95% CI negative in 2024, 2025, 2026) | Market predicts outcomes *better* than the model |
| **By segment** (surface × odds bucket) | No bucket has skill CI above 0; near-zero positives fail 2026 validation | No exploitable niche |
| **Orthogonal residual** (do non-market features predict the market's errors?) | OOS R² **−0.0012**, corr **+0.013** | Features carry no info the market hasn't priced |

**Why this is unsurprising:** the model *includes* the market's implied probability as a feature. A model built on the line cannot beat the line — it regresses toward it and adds noise. The earlier "ROC 0.73 > market 0.69" was misleading: 0.69 was a one-sided implied prob; the de-vigged two-way market line is sharper than the model on both ranking and calibration.

**Consequence for betting:** confirmed by the leak-free backtest — Value/Kelly **−11.9% ROI**, all strategies negative. **Do not bet real money on this system.**

---

## 2. What has signal vs what doesn't (leak-free walk-forward)

| Model | Metric | Verdict |
|-------|--------|---------|
| H2H (target) | acc 67.2%, ROC 0.727 — **worse-calibrated than market** | No edge |
| Totals (total_games) | MAE 6.50 vs 6.58 baseline, **R² −0.05** | No signal at all |
| **Spread (game_diff)** | MAE 3.91 vs 4.82 baseline, **R² +0.174** | **Real signal** — only model that beats its baseline meaningfully |

The spread/margin model is the one genuine signal we have. But we have **no spread/handicap odds** to test whether that signal beats a (potentially softer) handicap market.

---

## 3. Where alpha could actually be (requires data we don't have)

Alpha needs a signal **orthogonal to the sharp H2H line**, or a **less efficient market**. Ranked by expected payoff vs ingestion cost:

1. **Game-handicap / spread market** *(strongest lead).* We already have a spread model with R² 0.174 and the full match-score data to train it. Handicap lines are typically softer than H2H. **Action:** ingest game-handicap odds (the-odds-api `spreads` market, already wired via `ODDS_API_KEY` in `scraper.py`) and run the same calibration test (spread-model implied vs market handicap line). This is the cheapest test of a real lead.

2. **Closing Line Value (CLV).** Beating the closing line *is* the operational definition of alpha. We currently have only opening B365. **Action:** poll the-odds-api at fixed offsets (−24h, −2h, kickoff), store timestamped odds, and (a) use line movement as a feature, (b) measure whether our picks beat the closing line. CLV is also the only honest forward-validation of any strategy.

3. **Multi-book best-price / soft books.** B365 is sharp; smaller books lag. **Action:** the-odds-api returns many bookmakers per match — capture all, bet best price, flag books that systematically misprice. Even with no model edge, best-price execution + occasional arbitrage is a real (if thin) edge.

4. **Totals (over/under games).** Our totals model has **no signal** (R² −0.05) — *not* a lead until the model itself improves (e.g. surface/server-archetype interactions, best-of-5 handling).

5. **In-play / news** — highest potential, highest infrastructure cost. Out of scope without websocket + latency budget (in-play) or systematic, backtestable news ingestion.

---

## 3b. Multi-book snapshot — built & first probe (2026-05-22)

Added `snapshot_odds_history()` in `src/data/scraper.py` (CLI: `python -m src.data.scraper --snapshot`): logs **every bookmaker's** h2h + spreads + totals with a snapshot timestamp to `data/live/odds_history.csv`. First live run: **4046 rows, 112 matches, 39 books** (Roland Garros + Hamburg).

First probe — best back-price across books vs **Pinnacle no-vig fair** line:

| Book set | matches | % with >2% best-EV | median best-EV |
|----------|---------|--------------------|----------------|
| incl. 1xBet | 99 | 35% | +0.000 |
| reputable, **excl. 1xBet** | 99 | 17% | **−0.028** |
| sharp only (Pinnacle+Betfair) | 99 | 15% | **−0.032** |

**Reading (honest):** median best-price EV is **negative** — for the typical match you pay the vig even at the best book. The headline (+30% EVs) was an **outlier artifact**: top picks were all 1xBet on big underdogs (stale/loose lines, low limits, get voided/limited — not reliably bettable). A +EV *tail* remains (17% of matches >2% excl. 1xBet), consistent with the known soft-book value-betting strategy — **but it is NOT validated**: these are upcoming matches with no outcomes, and apparent edges may be stale lines that correct before kickoff. Treat as a lead, not proven alpha (consistent with every prior "too good" result being an artifact).

**To validate (the only honest path):** snapshot repeatedly (−24h/−2h/kickoff), join with results, and measure whether best-price picks (a) beat their implied rate and (b) beat the **closing** line (CLV > 0). One snapshot cannot prove edge.

## 4. Recommended next step

Build a small **the-odds-api ingestion job** that stores, per upcoming match: all bookmakers' H2H **+ spreads + totals** lines, timestamped, polled at a few offsets before kickoff. That single dataset unlocks tests #1, #2, #3 at once — and is the only way to know if real alpha exists, because every test above needs a market the model wasn't built from.

Until then: the system is **honest, well-tested, and without edge**. That is a result, not a failure — it prevents betting real capital on a leak-inflated illusion.
