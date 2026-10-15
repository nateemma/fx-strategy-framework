# Implementation Plan: Standalone Long/Short Candidate Gates

**Branch**: `009-standalone-longshort-gates` | **Date**: 2026-10-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-standalone-longshort-gates/spec.md`

## Summary

Six shelved candidates, six verdicts, an afternoon each. Almost all the machinery already exists —
`portfolio.metrics()` for risk-adjusted returns, `validation.distant_window()` for the era split,
`voltarget` for sizing, `dataview.truncate()` for causality. Two pieces are genuinely missing and both
are small:

1. **A free daily-price loader with a cache** (`forex/data/yahoo.py`), built to the same shape as
   `fred.py`. This is the piece that keeps being rewritten in scratchpad and thrown away.
2. **A gate evaluator** (`forex/backtest/gate.py`) that composes metrics + era split + costs into one
   verdict record, so all six candidates are judged identically and SC-003/SC-004 hold *structurally*
   rather than by being remembered six times.

Everything else is per-candidate signal arithmetic, which is a handful of lines each.

**The plan's most consequential finding is a limit, not a feature**: the repo's financing model cannot
cost a short equity leg, so an ETF-pair long/short cannot be honestly evaluated with what exists. That
reshapes three of the six candidates — see [research.md](./research.md) R2.

## Technical Context

**Language/Version**: Python 3.12 (`.venv/bin/python`).

**Primary Dependencies**: **None new.** `pandas` and `pyarrow` are already used; the price loader uses
`urllib.request` from the standard library, matching `fred.py`'s pattern of a lazily-imported,
injectable client. Deliberately **not** adding `yfinance` — one HTTP call against a documented JSON
shape is less fragile than a wrapper library, and it keeps the test suite offline.

**Storage**: Parquet per series under `data_cache/`, exactly as `fred.py` does it.

**Testing**: pytest, offline. The price client and the FRED client are both injected, so no test
performs network I/O.

**Target Platform**: Local research. **No broker, no Gateway, no order path** (FR-012).

**Project Type**: Research library plus gate scripts; no service, no UI.

**Performance Goals**: Not a factor. Six candidates × ~6,000 daily bars.

**Constraints**: An afternoon per candidate (SC-002), and every verdict net of cost and financing
(SC-004). The second constraint is what makes the first hard — honest costing is where candidates die.

**Scale/Scope**: 6 candidates, ~24 years of daily history where available, ~250 lines of new library
code plus one findings doc per candidate.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Engaged? | How this feature satisfies it |
|---|---|---|
| **I. Framework/Strategy separation** | **Yes, and it shapes the design** | The candidates are not FX, so the `Strategy` contract (point-in-time data → target *currency* weights) does not fit and MUST NOT be stretched to fit. They follow the existing non-FX precedent instead: plain functions in `strategies/`, as `trend_book.py` does. New generic machinery (price loader, gate evaluator) goes in `forex/`; candidate-specific arithmetic goes in `strategies/`. No registry is added — Principle I forbids one. |
| **II. Point-in-time causality** | Yes | Every signal is built from released macro data or prices up to *t*. Universe construction for any cross-sectional candidate MUST be point-in-time — a prior assessment inflated a real effect ~4× through the author's own universe selection, which is the failure mode here. `dataview.truncate()` is the structural enforcement where a candidate uses a `DataView`. |
| **III. Tested and linted** | Yes | The loader and the gate evaluator ship with tests; both external clients are injected so the suite stays hermetic — no network, no key, no broker. `ruff` before commit. |
| **IV. Paper-trading safety** | Yes — trivially, and deliberately | This feature creates **no execution path at all**. Nothing imports an executor, nothing connects to a broker, nothing can place an order. The paper track stopped on 2026-10-14 stays stopped. A "pass" verdict means *worth a real build later*, never *trade it*. |
| **V. Planning state in the repo** | Yes | Spec, plan, research, tasks and one findings doc per candidate are committed. Every verdict — especially the rejections — is durable, because the record is the only output this feature has. |
| **Execution & Data Safety** (research verdicts) | **Yes, centrally** | "Research verdicts MUST be judged in the deployment regime with an era split, on cost- and liquidity-aware out-of-sample P&L." That is FR-003/FR-004 and the gate evaluator enforces both. **STANDALONE-FIRST** is the whole premise: these candidates were shelved under the portfolio-contribution lens this clause was added to correct. |

**Gate result: PASS.** No violations, so Complexity Tracking is omitted.

## Project Structure

### Documentation (this feature)

```text
specs/009-standalone-longshort-gates/
├── plan.md              # This file
├── spec.md
├── research.md          # Phase 0 — four findings, three of them inconvenient
├── data-model.md        # Phase 1 — the candidate register and the verdict records
├── quickstart.md        # Phase 1 — how to run a gate and what a verdict looks like
├── contracts/
│   └── interfaces.md    # Phase 1 — loader, evaluator and findings-doc contracts
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
forex/data/
└── yahoo.py                  # NEW: cached free daily prices. Same shape as fred.py —
                              #   load_prices(symbol, cache_dir, force, client), injectable client,
                              #   parquet cache. MUST assert the granularity the API reports.

forex/backtest/
└── gate.py                   # NEW: the standalone-gate evaluator. Composes portfolio.metrics(),
                              #   validation.distant_window() and a cost/financing model into one
                              #   GateVerdict. Pure; no I/O.

strategies/
├── longshort_candidates.py   # NEW: the six-row candidate register (plain data), iterated by both
│                             #   gate scripts so neither hardcodes six paths
├── curve_spread.py           # NEW (A3): 2s10s signal + two-leg weights
├── macro_spread.py           # NEW (B5, B6): breakeven and credit-spread signals — same shape,
                              #   so one module rather than two near-identical ones
└── (B2/B3 only if they survive the data gate — expected not to)

scripts/
├── gate_data_feasibility.py  # NEW: the US2 cull. One free-data probe per candidate, reporting
                              #   testable / dead-on-data with the usable history span.
└── gate_candidate.py         # NEW: run one candidate's gate and emit its verdict table

docs/
└── standalone-longshort-findings.md   # NEW: one doc, one section per candidate, verdicts + evidence

tests/
├── test_yahoo.py             # NEW: cache behaviour, granularity assertion, injected client
├── test_gate.py              # NEW: era split (incl. the (recent, distant) return order),
│                             #   cost/financing application, verdict logic
├── test_curve_spread.py      # NEW: signal arithmetic and causality
├── test_macro_spread.py      # NEW: the shared two-leg spread signal (B5/B6)
├── test_data_feasibility.py  # NEW: the cull's status logic, probes injected
└── test_no_broker.py         # NEW: FR-012 made structural — no module here imports a broker
                              #   library or any execution path
```

**Structure Decision**: the repo's established split is followed — **pure logic in `forex/` and
`strategies/`, I/O and side effects in `scripts/`** — which is what keeps the suite offline.

**What gets committed versus thrown away.** Prior gates (RSP vs SPY, the momentum basket) ran entirely
from scratchpad scripts and delivered only a findings doc. That was right for a one-off; it is wrong
here, because the loader and the evaluator are used **six times** and the scratchpad version has
already been written and discarded at least twice. So: **commit the two shared pieces and the
per-candidate signal functions; keep genuinely exploratory poking in the scratchpad; put the numbers
and the method in the findings doc** so a rejection is reproducible from the doc alone (FR-009).

**One findings doc, not six.** Six files for six candidates — four of which are expected to be a
paragraph each ("dead, no free data") — would scatter the record. One document with a section per
candidate keeps the comparison readable, which is the point.

## Phase 0 — Research

See [research.md](./research.md). Four questions were resolved by **probing rather than reasoning**,
which is this project's own rule, and three of the four answers were unwelcome:

- **R1** — the obvious price-API call silently returns *monthly* bars while reporting `interval=1d`.
  Caught by measurement; it would have produced a daily strategy backtested on monthly data.
- **R2** — the repo's financing model **cannot cost a short equity leg**, which reshapes B5/B6/B4.
- **R3** — `distant_window()`'s default split is tuned to the FX sample and is wrong for a 24-year
  history; it must be parameterised per candidate.
- **R4** — adjusted closes are available and are **mandatory** for bond and credit ETFs.

## Phase 1 — Design

See [data-model.md](./data-model.md) for the candidate register and verdict records,
[contracts/interfaces.md](./contracts/interfaces.md) for the function and document contracts, and
[quickstart.md](./quickstart.md) for how to run a gate and read a verdict.

**Post-design Constitution re-check: PASS.** The design adds no dependency, no network call in tests,
and no execution path. R2 made the design *more* conservative rather than less: candidates that cannot
be honestly costed are now required to say so in their verdict instead of quietly reporting a number
that assumes free shorting.
