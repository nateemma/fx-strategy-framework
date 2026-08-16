<!--
Sync Impact Report
Version change: (unversioned template) → 1.0.0
Bump rationale: MAJOR — first ratified constitution; all principles newly defined.
Modified principles: none (initial adoption; template placeholders replaced)
Added sections:
  - Core Principles I–V
  - Execution & Data Safety
  - Development Workflow
  - Governance
Removed sections: none
Deferred TODOs:
  - Principle III mandates ruff. [tool.ruff] was added to pyproject.toml at ratification
    (F, E9, E501 at line-length 120 — deliberately not E4/E7, which clash with the repo's
    terse house style). 21 pre-existing violations remain and are tracked as a Backlog item
    in specs/000-baseline/baseline.md. No CI enforces the gate; it is run by hand.
-->

# FX Strategy Framework Constitution

## Core Principles

### I. Framework/Strategy Separation

The dependency direction is **`strategies → forex`, never the reverse**. `forex/` is the
strategy-agnostic framework and MUST import zero concrete strategies; strategy-specific knowledge
(a signal, a universe assumption, a factor) MUST NOT appear in it. `strategies/` is the strategy
library and imports `forex` as a plain library.

A strategy is self-describing: a `Strategy` subclass with a class-level `NAME`, discovered at
runtime. Adding a strategy means dropping a file in `strategies/` — there is no central registry to
edit, and reintroducing one is a violation.

The `Strategy` contract (`NAME`, `target_weights`, optional `fit`/`params`/`search_space`/`build`)
is the load-bearing interface. **A breaking change to it requires a spec first** — it silently
invalidates every strategy in the library and every mode that drives them.

The one deliberate exception is carry accrual in the backtest: holding an FX position earns its
interest-rate differential, which is a market fact rather than a strategy property, so it is
computed framework-side and applied uniformly.

*Rationale: the framework's entire value is that one strategy definition works in every mode. A
framework that knows about carry cannot make that promise.*

### II. Point-in-Time Causality (NON-NEGOTIABLE)

A signal at date *t* MUST use only data available at *t*. Macro series are stamped with their
release date, not their reference date. Causality is enforced **structurally** — `DataView.truncate`
clips every series so a strategy literally cannot see the future — and never by convention alone.

Every strategy MUST pass `forex causal-check --strategy <name>` before it is used for any result
that informs a decision.

*Rationale: lookahead bias produces backtests that are indistinguishable from an edge until real
money is at risk. Structural enforcement is the only kind that survives refactoring.*

### III. Tested and Linted

All new code ships with pytest coverage, and the full suite MUST pass before a change is committed.
Pure logic MUST be extracted so it can be tested offline: the suite runs with no network, no API
key, and no broker connection, and that property MUST be preserved. Broker interaction goes through
injectable factories so tests never import `ib_async`.

New and modified code MUST pass `ruff`.

*Rationale: this codebase's failure mode is a silently wrong number, not a crash. Offline,
hermetic tests are what make a wrong number reproducible.*

### IV. Paper-Trading Safety (NON-NEGOTIABLE)

**Automated code MUST NOT place live orders.** Every execution path defaults to preview, which
connects read-only and places nothing. Placement requires an explicit `--confirm`, and reaching a
real-money account additionally requires the deliberate `allow_live` gate plus a `U…` account and
the live port. No scheduled job, script, or agent may cross that gate on its own.

The guard set on any execution path — account check, per-order and gross caps, minimum order size,
explicit TIF, reconcile-before-trade, and a never-raising unwind on partial failure — MUST be
preserved when that path is modified. Sleeves sharing an account MUST hold disjoint symbols, because
reconciliation is by contract ID against the whole account and cannot attribute a holding to a
sleeve.

*Rationale: the cost of a wrong order is unbounded and irreversible, unlike every other failure in
this repo.*

### V. Planning State Lives in the Repo

Specs, plans, task lists, and status MUST be committed and pushed. Planning state that exists only
on one machine does not exist. Research conclusions — including negative results and the reasoning
that rejected an approach — MUST be written down where the next session will find them, so a closed
question stays closed.

*Rationale: this is a long-running research program whose most valuable output is the record of what
was tried and rejected. That record is worthless if it is not durable and shared.*

## Execution & Data Safety

Secrets (FRED API key, broker settings) live in environment variables via `EnvConfig` and MUST NOT
be committed. Experiment parameters live in a versioned `RunConfig` (TOML). The two MUST NOT mix.

Runtime forward-record artifacts (`nav.csv`, `track.log`, `snapshot.log`, `launchd.err`,
`*_positions.csv`) are git-ignored local records. They are not versioned, so any history worth
keeping MUST be backed up deliberately.

Research verdicts MUST be judged in the deployment regime with an era split, on cost- and
liquidity-aware out-of-sample P&L — never on in-sample fit or a model-quality metric alone.

## Development Workflow

All non-trivial work goes through Spec Kit: `/speckit.specify` → `/speckit.plan` → `/speckit.tasks`
→ implement, checking off `tasks.md` items as they complete. Each feature gets its own numbered
folder under `specs/`. `specs/000-baseline/baseline.md` is the at-a-glance status page and MUST
reflect actual state, not intent.

Trivial work (a typo, a one-line fix, a doc correction) may skip the spec flow, but still obeys
Principles II–IV.

Changes to the framework MUST keep `ARCHITECTURE.md` true in the same commit. If a change would
falsify a sentence there, fix the sentence.

## Governance

This constitution supersedes other conventions in the repo where they conflict. Amendments are made
by editing this file with a Sync Impact Report recording the version change and rationale, and are
committed like any other planning state (Principle V).

Versioning is semantic: **MAJOR** for a backward-incompatible governance change or a principle
removed or redefined; **MINOR** for a new principle or materially expanded guidance; **PATCH** for
clarifications and wording.

Compliance is reviewed at the point of change: any work that touches an execution path, the
`Strategy` contract, or the causality machinery MUST state which principles it engages and how it
satisfies them. Complexity MUST be justified against the simpler alternative it replaces.

**Version**: 1.0.0 | **Ratified**: 2026-08-16 | **Last Amended**: 2026-08-16
