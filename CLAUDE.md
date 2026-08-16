# CLAUDE.md — forex

## Working agreement

**Start of every session**, before anything else:

1. `git pull`
2. Read `specs/000-baseline/baseline.md` — the status page: what's done, in flight, and backlogged.
3. Read the `tasks.md` of any active feature under `specs/`.

**All non-trivial work goes through Spec Kit:** `/speckit.specify` → `/speckit.plan` →
`/speckit.tasks` → implement, checking off `tasks.md` items as they complete. Each feature gets its
own numbered folder under `specs/`. Start from a Backlog entry in `baseline.md` where one exists.

Trivial work (a typo, a one-line fix, a doc correction) may skip the flow — but never skips the
paper-safety and causality principles below.

**End of every session:** update the active `tasks.md` and `baseline.md` to reflect *actual* state,
then commit and push. **Planning state must never exist only on one machine.**

Governing principles: `.specify/memory/constitution.md` (v1.0.0). It wins over anything here that
conflicts.

## Project memory

Findings about this repo that aren't derivable from the code or git history:

@MEMORY.md

Add a new fact as one file under `memory/` and a one-line pointer in `MEMORY.md`. Cross-project
principles go in `~/.claude/quant-research-lessons.md` instead, not here.

## Docs of record

Don't re-derive these — read them:

- `specs/000-baseline/baseline.md` — status, backlog, and the list of known doc/code discrepancies.
- `README.md` — results, the deployable book, live-execution setup.
- `ARCHITECTURE.md` — the `strategies → forex` dependency rule and package layout.
- `docs/strategy-research-backlog.md` — the factor-search decision log. **The search is converged
  and closed.** Value, yield-curve slope, skewness, regime conditioning, central-bank NLP, learned
  vol forecasters, and all intraday ideas were each tested and rejected, with evidence. Don't
  relitigate them; a new factor earns its place only by being ~uncorrelated to carry.
- `docs/archive/` — superseded planning material, including the pre-Spec-Kit Superpowers plans and
  specs. Historical record only; do not treat as current.

## Execution safety

Everything running today is the IBKR **paper** account (`DUQ218063`, port 4002). Live trading is a
separate deliberate gate (`allow_live` + a `U…` account + the live port) — never cross it without
being asked explicitly, and never from automated code.

`BasketExecution` reconciles by conId **against the whole account**, so it cannot tell one sleeve's
IEF from another's. Keep every sleeve's symbols disjoint.

## Environment

`.venv/` at the repo root; run tools as `.venv/bin/python`. The test suite is offline and needs no
API key: `pytest -q` (297 tests). Lint with `ruff check .` — the config is scoped to real-bug rules
(F, E9, E501), deliberately not the style rules that clash with the repo's terse idiom.
