# Worked examples

Five things this project does, each one small enough to run and read in a minute.

**Every output block below is captured, not illustrative.** Each was produced by
running the code immediately above it from the repository root with
`pip install -r requirements.txt` already done. None of them needs a trained
model, a dataset, an API key or a running server — they exercise the pure
functions and the security boundaries, which is exactly the part a reader can
verify without earning access to anything.

| | |
|---|---|
| [1](#1-turn-an-odds-snapshot-into-a-signal) | Turn an odds snapshot into a signal |
| [2](#2-read-an-elo-the-way-the-model-reads-it) | Read an ELO the way the model reads it |
| [3](#3-refuse-a-bad-update) | Refuse a bad update |
| [4](#4-knock-on-the-local-app-from-the-wrong-page) | Knock on the local app from the wrong page |
| [5](#5-prove-an-evaluation-is-leak-free) | Prove an evaluation is leak-free |

---

## 1. Turn an odds snapshot into a signal

Four bookmakers price the same match differently. Two of them move the market and
two follow it. The question a signal answers is not "who wins" — it is "is anyone
offering more than the price implied by the books that know".

```python
import pandas as pd
from src.betting.signals import effective_odds, sharp_consensus, find_value_bets

print("effective_odds(3.00, 'betfair_ex_eu') =", round(effective_odds(3.00, "betfair_ex_eu"), 4))
print("effective_odds(3.00, 'williamhill')   =", round(effective_odds(3.00, "williamhill"), 4))

snapshot = pd.DataFrame([
    {"market": "h2h", "p1": "Sinner", "p2": "Alcaraz", "commence_time": "2026-08-27T13:00:00Z",
     "bookmaker": "pinnacle",      "price_1": 1.80, "price_2": 2.10},
    {"market": "h2h", "p1": "Sinner", "p2": "Alcaraz", "commence_time": "2026-08-27T13:00:00Z",
     "bookmaker": "betfair_ex_eu", "price_1": 1.83, "price_2": 2.14},
    {"market": "h2h", "p1": "Sinner", "p2": "Alcaraz", "commence_time": "2026-08-27T13:00:00Z",
     "bookmaker": "williamhill",   "price_1": 1.75, "price_2": 2.25},
    {"market": "h2h", "p1": "Sinner", "p2": "Alcaraz", "commence_time": "2026-08-27T13:00:00Z",
     "bookmaker": "sport888",      "price_1": 1.72, "price_2": 2.05},
])

fair = sharp_consensus(snapshot)
for key, (fp1, fp2, n) in fair.items():
    print("sharp_consensus:", key[0], "vs", key[1],
          "-> fair p1 =", round(fp1, 4), "| fair p2 =", round(fp2, 4), "| n_sharp =", n)

print()
print(find_value_bets(snapshot).to_string(index=False))
```

```text
effective_odds(3.00, 'betfair_ex_eu') = 2.9
effective_odds(3.00, 'williamhill')   = 3.0
sharp_consensus: Sinner vs Alcaraz -> fair p1 = 0.5382 | fair p2 = 0.4618 | n_sharp = 2

           match  player side        book  odds  fair_odds  sharp_fair_prob   edge  n_sharp        commence_time
Sinner v Alcaraz Alcaraz   p2 williamhill  2.25       2.17           0.4618 0.0389        2 2026-08-27T13:00:00Z
```

Three things happened in those eight lines, and each is a different discipline:

- **`effective_odds` charges commission to the exchange and not to the book.**
  3.00 on Betfair returns 2.90 to the bettor because the 5% is taken from the net
  winnings; 3.00 at William Hill returns 3.00. Compare the two raw and you will
  systematically prefer the venue whose displayed price is structurally better
  and whose realised price is not.
- **`sharp_consensus` removes the margin.** Pinnacle's 1.80/2.10 implies
  0.556 + 0.476 = 1.032 — that 3.2% is the house's, not information. Normalising
  the two sides to sum to 1, across the sharp books only, gives the fair pair
  0.5382 / 0.4618.
- **The edge is a comparison between the fair price and the best available one.**
  Alcaraz's fair price is 2.17; William Hill is showing 2.25. That is
  `2.25 × 0.4618 − 1 = +3.89%`, above the 3% floor, so it becomes a row in the
  signal log. Nobody's 1.7-something on Sinner clears the same bar, so nothing is
  emitted for that side.

Note what is *not* in this example: the model. A signal is a market observation,
and it is deliberately computable without a prediction. What the model adds is a
second opinion about the same fair probability — and the honest backtest exists
to report whether that opinion is worth anything. Today it is not: **67.4%
accuracy, −29% ROI**. See [`DOMAINS.md` §1](DOMAINS.md#1-machine-learning--market-microstructure).

## 2. Read an ELO the way the model reads it

`src/features/elo.py` is not a textbook ELO. Four behaviours matter, and all four
are visible without touching a dataset.

```python
from src.features.elo import EloRating

e = EloRating()
print("expected_score(1500, 1500) =", round(e.expected_score(1500, 1500), 4))
print("expected_score(1900, 1500) =", round(e.expected_score(1900, 1500), 4))
print("expected_score(2100, 1700) =", round(e.expected_score(2100, 1700), 4))

e.match_count["rookie"] = 3
e.match_count["veteran"] = 400
print()
for pid in ("rookie", "veteran"):
    print(f"_get_k_factor('A', {pid!r}) = {e._get_k_factor('A', pid):5.1f}   "
          f"_get_k_factor('G', {pid!r}) = {e._get_k_factor('G', pid):5.1f}")

e2 = EloRating()
e2.global_ratings["p"] = 1800
e2.surface_ratings["Clay"]["p"] = 2000
e2.surface_match_count["Clay"]["p"] = 4
print()
print("combined(Clay) with 4 clay matches =", round(e2.get_combined_rating("p", "Clay"), 1))
e2.surface_match_count["Clay"]["p"] = 5
print("combined(Clay) with 5 clay matches =", round(e2.get_combined_rating("p", "Clay"), 1))

e3 = EloRating()
e3.global_ratings["p"] = 2000
e3.last_played_date["p"] = "2025-01-01"
e3.apply_time_decay("p", "2025-01-20")
print()
print("after 19 days out  =", round(e3.global_ratings["p"], 1))
e3.apply_time_decay("p", "2026-01-01")
print("after 365 days out =", round(e3.global_ratings["p"], 1))
```

```text
expected_score(1500, 1500) = 0.5
expected_score(1900, 1500) = 0.9091
expected_score(2100, 1700) = 0.9091

_get_k_factor('A', 'rookie') =  80.0   _get_k_factor('G', 'rookie') = 120.0
_get_k_factor('A', 'veteran') =  32.0   _get_k_factor('G', 'veteran') =  48.0

combined(Clay) with 4 clay matches = 1800
combined(Clay) with 5 clay matches = 1940.0

after 19 days out  = 2000
after 365 days out = 1975.0
```

- **Only the gap matters.** 1900 vs 1500 and 2100 vs 1700 are the same match:
  400 points is 90.9% either way.
- **The same win is worth more to a newcomer, and more at a Slam.** A player with
  three career matches gets K × 2.5; at a Grand Slam the base is 48 rather than
  32, so the rookie's K is 120 against the veteran's 32. A breakout season is
  allowed to move a rating quickly instead of being averaged into invisibility
  over two years.
- **A surface rating has to be earned before it counts.** With four clay matches
  the combined rating is just the global 1800; the fifth match switches on the
  0.7/0.3 blend and it becomes 1940. The threshold is there because a single
  good week on clay is not a clay specialist.
- **Inactivity decays toward the mean, not toward zero.** Nineteen days out
  changes nothing (the rule needs 30). A full year out pulls the 500-point
  surplus in by 5%: 2000 → 1975. A player who has not played is not worse, but
  the rating is *less certain*, and decay toward 1500 is how that is expressed.

## 3. Refuse a bad update

The in-app updater downloads a zip and unpacks it into the writable data root.
That zip contains pickled models, and `joblib.load` executes code when it
deserialises them — so a bundle the client accepts is, in practice, code the user
runs. Here is the extractor deciding, five times, with a throwaway signing key
standing in for the release key.

```python
import base64, hashlib, json, tempfile, zipfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import src.dashboard.data_api as data_api

priv = ed25519.Ed25519PrivateKey.generate()
data_api._UPDATER_PUBKEY = priv.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
tmp = Path(tempfile.mkdtemp())

def build(name, files, sign=True, tamper=False):
    manifest = {"name": "UnaBetting", "version": "9.9.9", "files": [
        {"path": m, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        for m, b in files.items()]}
    if sign:
        payload = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()
        manifest["signature"] = base64.b64encode(priv.sign(payload)).decode()
    path = tmp / name
    with zipfile.ZipFile(path, "w") as zf:
        for m, b in files.items():
            zf.writestr(m, b + (b"  # injected" if tamper else b""))
        zf.writestr("manifest.json", json.dumps(manifest))
    return path

def attempt(label, bundle, root):
    try:
        n = data_api._extract_runtime_bundle(bundle, root)
        print(f"{label:<34} -> accepted, {n} file(s) written")
    except ValueError as e:
        print(f"{label:<34} -> REJECTED: {e}")

good = {"models/atp_metrics.json": b'{"accuracy": 0.674}', "config/config.yaml": b"a: 1\n"}
attempt("a genuine signed bundle", build("ok.zip", good), tmp / "r1")
attempt("one byte changed after signing", build("tampered.zip", good, tamper=True), tmp / "r2")
attempt("same files, no signature", build("unsigned.zip", good, sign=False), tmp / "r3")
attempt("a member escaping DATA_ROOT", build("slip.zip", {"../evil.txt": b"x"}), tmp / "r4")

root = tmp / "r5"
(root / "data").mkdir(parents=True)
(root / "data" / "betanalytix.db").write_bytes(b"the user's wagering history")
attempt("a signed bundle over the bet db",
        build("db.zip", {"data/betanalytix.db": b"replaced"}), root)
print("   the db on disk is still:", (root / "data" / "betanalytix.db").read_bytes().decode())
```

```text
a genuine signed bundle            -> accepted, 2 file(s) written
one byte changed after signing     -> REJECTED: size mismatch: models/atp_metrics.json
same files, no signature           -> REJECTED: unsigned bundle — refusing to extract
a member escaping DATA_ROOT        -> REJECTED: unsafe path in bundle: ../evil.txt
a signed bundle over the bet db    -> REJECTED: bundle contains no installable files
   the db on disk is still: the user's wagering history
```

Read the last two lines carefully, because they are the ones that are not
obvious:

- **The zip-slip guard runs before the manifest checks.** `../evil.txt` is
  rejected for its path, not for being unlisted, so an unsafe member fails
  identically on every OS — Windows normalises backslash and absolute names in
  ways that would otherwise trip a different check first and make the behaviour
  platform-dependent.
- **A correctly signed bundle still cannot touch the user's data.** The bet
  database is on the protected list, so it is *skipped* rather than overwritten —
  and once it is skipped the bundle has nothing left to install, which is why the
  refusal reads the way it does. The signing key is not a licence to overwrite a
  wagering history.

The tampered case reports a size mismatch rather than a signature failure only
because appending bytes changes the length first; strip the length change and the
signature check is what refuses it. `tests/test_updater.py` covers both paths, and
the whole extraction is all-or-nothing — a bundle that fails on its last member
writes nothing from the earlier ones.

## 4. Knock on the local app from the wrong page

The dashboard binds `127.0.0.1`, which is not isolation: every other page open in
the same browser can send it requests. This runs the real FastAPI app through a
test client — no server, no port.

```python
import os
from fastapi.testclient import TestClient
os.environ.pop("DASHBOARD_TOKEN", None)
from src.dashboard.server import app
from src.dashboard.config import COMMAND_WHITELIST

c = TestClient(app)
print("no Origin at all (the CLI, curl, this script):")
print("   GET /api/overview                ->", c.get("/api/overview").status_code)

print("\nthe app's own page:")
print("   Origin: http://127.0.0.1:8765    ->",
      c.get("/api/overview", headers={"Origin": "http://127.0.0.1:8765"}).status_code)

print("\nsome other page in the same browser:")
for origin in ("https://evil.example", "http://127.0.0.1:9999",
               "http://user:pw@127.0.0.1:8765", "http://127.0.0.1:8765/path"):
    r = c.get("/api/overview", headers={"Origin": origin})
    print(f"   Origin: {origin:<32} -> {r.status_code}")
r = c.get("/api/overview", headers={"Sec-Fetch-Site": "cross-site"})
print(f"   Sec-Fetch-Site: cross-site{' ':<22}-> {r.status_code}")

print("\nwhat the pipeline runner will accept as a command:")
print("   names:", ", ".join(sorted(COMMAND_WHITELIST)))
print("   'rm -rf /' ->", COMMAND_WHITELIST.get("rm -rf /"))

print("\nasking a file endpoint to leave the project:")
print("   GET /api/file ../../etc/hosts    ->",
      c.get("/api/file", params={"path": "../../../../Windows/System32/drivers/etc/hosts"}).status_code)

r = c.get("/api/overview")
for h in ("content-security-policy", "x-content-type-options", "referrer-policy"):
    print(f"   {h}: {r.headers[h][:96]}")
```

```text
no Origin at all (the CLI, curl, this script):
   GET /api/overview                -> 200

the app's own page:
   Origin: http://127.0.0.1:8765    -> 200

some other page in the same browser:
   Origin: https://evil.example             -> 403
   Origin: http://127.0.0.1:9999            -> 403
   Origin: http://user:pw@127.0.0.1:8765    -> 403
   Origin: http://127.0.0.1:8765/path       -> 403
   Sec-Fetch-Site: cross-site                      -> 403

what the pipeline runner will accept as a command:
   names: backtest, clean, download, features, inference, scan, signals, train
   'rm -rf /' -> None

asking a file endpoint to leave the project:
   GET /api/file ../../etc/hosts    -> 403

   content-security-policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com http
   x-content-type-options: nosniff
   referrer-policy: no-referrer
```

The two rows worth arguing about:

- **A missing `Origin` is allowed, on purpose.** That is `curl`, the test client
  and the CLI — none of which a malicious web page can drive. Requiring an origin
  header would break every non-browser caller while stopping nothing, because the
  attacker in this model *is* a browser and browsers always send one.
- **`http://127.0.0.1:8765/path` is refused even though it is the right host and
  port.** An origin is a triple; anything carrying a path, a query, a fragment or
  credentials is not an origin, and accepting a near-miss is how these checks
  usually fail.

And the runner does not take a command line at all. The client sends one of eight
names, the server looks up the argument vector itself and runs it with
`create_subprocess_exec` — no shell, and no way to express something the map does
not already contain. `"rm -rf /"` is not rejected by a filter; it simply has no
entry. See [ADR-0004](adr/0004-the-runner-takes-a-name.md).

## 5. Prove an evaluation is leak-free

The project's one non-negotiable claim is that its accuracy numbers are honest,
and three leaks were found in its history. So the leak rules are tests, not
conventions.

```bash
python -m pytest tests/test_leakage.py tests/test_randomization.py -v
```

```text
======================== 7 passed, 2 skipped in 4.15s =========================
```

The seven that ran need nothing but synthetic frames, so they guard every clone
and every CI run:

| Test | What a failure would mean |
|---|---|
| `test_imputation_median_is_train_only` | test-set information reached training through a median |
| `test_no_nan_after_imputation` | a NaN survived into the scaler, where its handling is silent |
| `test_perspective_pairs_added_when_partner_available` | a one-sided `w_X` kept without its `l_X` twin — the label wearing a hat |
| `test_perspective_pairs_drop_when_partner_missing` | an unpairable column tolerated instead of dropped |
| `test_odds_suffix_partner_detected` | `B365W` not recognised as the partner of `B365L`, so the pairing rule silently skips odds columns |
| `test_randomize_raises_on_unpaired_perspective` | randomisation proceeding on a frame it cannot safely randomise, instead of raising |
| `test_randomize_perspective_swaps_features_and_targets` | features and targets swapping out of step |

The **two skips are the expensive ones**, and they are skipped rather than
silently passed because they need a built feature matrix that no fresh clone has:

- `test_serve_only_walkforward_roc_is_not_leaky` — serve rolling statistics alone
  must not reconstruct the outcome. Before the unpaired-column fix this reached
  ROC ≈ 0.96; leak-free it has to sit below 0.82.
- `test_shuffled_target_accuracy_is_chance` — destroy the relationship between
  features and labels, run the whole pipeline, and demand chance performance.

That second one is the test to copy into your own project. Anything better than
chance on shuffled labels is the pipeline telling you where it hid the answer.
Run both with `python -m pytest tests/ -m slow` once `build_features` has
produced `data/features/atp_features.csv`.

The whole suite, for reference:

```bash
python -m pytest tests/ -q
```

```text
================= 145 passed, 4 skipped, 1 warning in 14.81s ==================
```

---

## Next

| | |
|---|---|
| Why the pieces are cut where they are | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| Which fields this project joins, and where they meet | [`DOMAINS.md`](DOMAINS.md) |
| Every REST and WebSocket endpoint | [`API.md`](API.md) |
| The scheduled agents and what they may not do | [`LOOPS.md`](LOOPS.md) |
| One decision per file, with what it cost | [`adr/`](adr/) |
