# CLAUDE.md — forex

## Project memory

Findings about this repo that aren't derivable from the code or git history:

@MEMORY.md

Add a new fact as one file under `memory/` and a one-line pointer in `MEMORY.md`. Cross-project
principles go in `~/.claude/quant-research-lessons.md` instead, not here.

## Docs of record

Don't re-derive these — read them:

- `README.md` — results, the deployable book, live-execution setup.
- `ARCHITECTURE.md` — the `strategies → forex` dependency rule and package layout.
- `docs/strategy-research-backlog.md` — the factor-search decision log. **The search is converged
  and closed.** Value, yield-curve slope, skewness, regime conditioning, central-bank NLP, learned
  vol forecasters, and all intraday ideas were each tested and rejected, with evidence. Don't
  relitigate them; a new factor earns its place only by being ~uncorrelated to carry.

## Execution safety

Everything running today is the IBKR **paper** account (`DUQ218063`, port 4002). Live trading is a
separate deliberate gate (`allow_live` + a `U…` account + the live port) — never cross it without
being asked explicitly.

`BasketExecution` reconciles by conId **against the whole account**, so it cannot tell one sleeve's
IEF from another's. Keep every sleeve's symbols disjoint.

## Environment

`.venv/` at the repo root; run tools as `.venv/bin/python`. The test suite is offline and needs no
API key: `pytest -q`.
