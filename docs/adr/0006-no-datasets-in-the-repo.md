# 0006 — No dataset is redistributed in this repository

**Status:** accepted

## Context

The pipeline is built on data that is not ours. The largest and most important
source, Jeff Sackmann's Tennis Abstract datasets, is licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): attribution
required, share-alike, and **non-commercial use only**. Historical odds come from
tennis-data.co.uk under its own terms; live odds come from a paid API.

Vendoring a copy into the repository would be the convenient choice — a fresh
clone would work immediately, and CI would have a fixture. It would also be
redistribution, which drags the share-alike and non-commercial terms onto
everything built from the copy, and it would make this project the apparent
source of data it did not collect.

## Decision

No dataset is committed. `src/data/download.py` fetches the sources at their
canonical locations, `DATA_SOURCES.md` names each one with its licence and the
obligations it imposes, and the README states the non-commercial constraint where
someone will read it rather than in a footnote.

Derived artifacts follow the same rule for a different reason: `data/processed/`,
`data/features/` and `models/*.pkl` are gitignored because they are reproducible
from the sources, and a committed 200 MB feature file would be a copy of the
upstream data wearing a different extension.

`data/betanalytix.db` is excluded on a third ground entirely — it is the user's
real wagering history, and it is personal data.

## Consequences

**What it buys.** The licence obligations stay attached to the data rather than
being laundered through this repository, and every user of this project meets the
upstream terms directly. The repository stays small enough to clone quickly.

**What it costs, and there is a known hole.** A fresh clone cannot complete the
pipeline. `download` fetches Sackmann and tennis-data.co.uk, but ATP cleaning in
`src/data/clean.py` also needs `data/raw/TML-Database/`
(github.com/Tennismylife/TML-Database), and nothing clones it automatically. A
new contributor gets through `download` and stops at `clean` with a missing
directory. That gap is documented in `CLAUDE.md` and it is a gap, not a design.

The second cost lands on the tests. Anything that needs the real dataset or
trained artifacts is marked and skipped — the leak regression tests and the live
inference test skip on a clean checkout. They are the tests that matter most, and
they do not run in the default suite. The mitigation is that they fail loudly
when the data *is* present rather than being silently disabled; it is not a
substitute for a small committed fixture, which is the obvious next step and is
blocked on nothing but the work of building one that is not derived from the
licensed data.
