# Architecture decision records

Decisions that shaped this repository, with the context that made them and the
price each one carries. One file per decision, numbered, never rewritten — a
decision that turns out badly gets a **superseded** status and a successor, so
the reasoning that led there stays readable.

An ADR belongs here when reversing the decision would mean moving a boundary
rather than editing a function. Experiment results do not: they live in
[`EXPERIMENTS.md`](../../EXPERIMENTS.md) with their before/after numbers.

| # | Decision | Status |
|---|---|---|
| [0001](0001-files-as-the-pipeline-seam.md) | Pipeline stages hand off through files on disk | accepted |
| [0002](0002-leak-freedom-is-structural.md) | Leak-freedom is enforced at the seams, not by convention | accepted |
| [0003](0003-two-runtime-roots.md) | Two runtime roots: read-only bundle, writable data | accepted |
| [0004](0004-the-runner-takes-a-name.md) | The run WebSocket takes a command *name*, never a command line | accepted |
| [0005](0005-named-bookmakers-not-regions.md) | Request named bookmakers, not whole regions | accepted |
| [0006](0006-no-datasets-in-the-repo.md) | No dataset is redistributed in this repository | accepted |
| [0007](0007-route-on-has-odds.md) | Two model families, routed at inference on `has_odds` | accepted |

## Template

```markdown
# NNNN — Title

**Status:** proposed | accepted | superseded by NNNN

## Context
What was true that forced a choice. Numbers where numbers exist.

## Decision
What was chosen, stated so someone can tell whether the code still obeys it.

## Consequences
What this buys, and what it costs. The cost paragraph is the point of the file.
```
