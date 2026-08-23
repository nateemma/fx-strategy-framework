# Tasks: Cross-Asset Trend Sleeve (Futures)

**Input**: Design documents from `/specs/005-futures-trend-sleeve/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), and the A2 gate
[`cross-asset-trend-findings.md`](../../docs/cross-asset-trend-findings.md)

**Tests**: **REQUIRED** (Constitution III), and here they are the safety mechanism rather than a
formality — this feature trades a new asset class. Test tasks precede their implementations.

**⚠️ BLOCKING PREREQUISITE**: a CME/CBOT/NYMEX market-data subscription. Without it there is no price
history (the A1 gate measured 7 daily bars on a front month), so nothing past Phase 3 can be
validated against live data. Phases 1–4 can be built and tested offline in the meantime.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Add the eight-market universe table (symbol, exchange, multiplier, ETF proxy, granularity note) in `strategies/trend_book.py`
- [X] T002 Add a fake-IB fixture for futures, modelled on `tests/test_live_execution.py::_FakeIB`, in `tests/test_futures_execution.py`

---

## Phase 2: Foundational — contract roll (Blocking Prerequisites)

**Rolling wrong silently doubles or zeroes a position, so it is settled before anything places orders.**

- [X] T003 Write failing tests for front-contract selection and roll timing — which contract to hold on a given date, and that a roll is not a signal change — in `tests/test_futures_roll.py`
- [X] T004 Implement `front_contract(market, asof)` and `needs_roll(held, asof)` in `forex/run/futures_roll.py`
- [X] T005 [P] Write failing tests that reconciliation compares per MARKET, not per contract, so a roll does not read as a full round-trip — in `tests/test_futures_roll.py`

**Checkpoint**: "what should I hold today" is answerable and tested without a broker.

---

## Phase 3: User Story 1 — Place and reconcile safely (Priority: P1) 🎯 MVP

- [X] T006 [P] [US1] Write failing tests for the guard set: preview places nothing, confirm required, non-DU account refused without the live gate (FR-001) — in `tests/test_futures_execution.py`
- [X] T007 [US1] Implement `FuturesExecution` connect/preview/placement skeleton in `forex/run/futures.py`
- [X] T008 [P] [US1] Write a failing test that the per-order cap raises **before** any order is placed — an atomic pre-pass, as fixed in `basket.py` — in `tests/test_futures_execution.py`
- [X] T009 [US1] Implement the per-order cap pre-pass and the min-order skip in `forex/run/futures.py`
- [X] T010 [P] [US1] Write a failing test that an unchanged target places zero orders (FR-002) — in `tests/test_futures_execution.py`
- [X] T011 [US1] Implement reconcile-by-contract-identity, comparing per market so rolls are not round-trips, in `forex/run/futures.py`
- [X] T012 [P] [US1] Write a failing test that a mid-batch failure triggers an unwind that never raises, then re-raises the original error (FR-001) — in `tests/test_futures_execution.py`
- [X] T013 [US1] Implement the never-raising `_unwind` in `forex/run/futures.py`
- [X] T014 [P] [US1] Write a failing test that placement is refused when available funds would fall below the configured floor (FR-008) — in `tests/test_futures_execution.py`
- [X] T015 [US1] Implement the margin floor check in `forex/run/futures.py`

**Checkpoint**: futures can be traded as safely as FX and stocks. Nothing has been placed yet.

---

## Phase 4: User Story 2 — Compute target positions (Priority: P2)

- [X] T016 [P] [US2] Write failing tests that the signal reproduces the gate's construction — 3-lookback ensemble, inverse-vol weights — against a fixture with a known answer, in `tests/test_trend_book.py`
- [X] T017 [US2] Implement the ensemble signal and inverse-vol weights in `strategies/trend_book.py`
- [X] T018 [P] [US2] Write a failing causality test: weights on date *t* are unchanged when data after *t* is truncated (FR-005, Constitution II) — in `tests/test_trend_book.py`
- [X] T019 [P] [US2] Write failing tests that targets are whole contracts and that per-market rounding error is reported, including a market rounding to zero (FR-004, SC-003) — in `tests/test_trend_book.py`
- [X] T020 [US2] Implement `target_contracts(weights, risk_base, prices, multipliers)` returning integers plus the rounding report, in `strategies/trend_book.py`
- [X] T021 [US2] Implement the refuse-on-insufficient-history path (FR-007) in `strategies/trend_book.py`

**Checkpoint**: what to hold is computed, faithful to the gate, and honest about rounding.

---

## Phase 5: User Story 3 — Run it on schedule (Priority: P3)

- [X] T022 [US3] Implement `scripts/trend_sleeve.py` — preview by default, `--confirm` arms placement, `--risk-base` required
- [X] T023 [US3] Write the positions CSV on applied runs, reusing `forex/run/basket_track.py` (FR-009)
- [X] T024 [US3] Add a monthly `com.fx.trend-sleeve` agent to `scripts/install_schedules.sh`
- [X] T025 [US3] Add the sleeve to `WATCHED` in `forex/run/health.py` and update its tests

---

## Phase 6: Live validation — ⛔ BLOCKED (revised 2026-08-23)

> **The blocker is not the market-data subscription.** That was bought and verified live on
> 2026-08-21/23 (all eight markets return bars, `mdType=1`, `usfuture` connected). Two *other* things
> block this phase, and T026–T027 cannot be completed as originally written:
>
> 1. **The sleeve fetches the FRONT MONTH only** (`scripts/trend_sleeve.py`), so available history is
>    capped at that contract's own listed life — MESU6 ~294 bars, M6EU6 ~110, ZTU6/ZFU6 ~160, against
>    `MIN_HISTORY` 315. **No front contract can ever satisfy it**, at any subscription level. This needs
>    a stitched, back-adjusted continuous-series builder, which does not exist yet — `futures_roll.py`
>    decides what to *hold*, not how to build a price *history*.
> 2. **IBKR does not retain enough contract history to stitch from.** CONTFUT gives ~2 years on the
>    micros; `includeExpired` returns 8 contracts back to 2025-12. Needs Databento.
>
> T028 (single-contract executor validation) is the one task here that is **not** data-blocked — it needs
> only live quotes, which exist. It is blocked solely on US Futures **Trading** Permissions, still pending
> as of 2026-08-23. Do that one first when approval lands.
>
> Also beware two measurement artifacts that both look like "no data": IBKR **pacing** (>60 historical
> requests / 10 min silently times requests out) and a **competing login** (error 10197 — cuts market data
> to the API entirely, SPY included). Both produced false "0 bars" readings during this investigation.

- [ ] T026 Confirm the subscription is active: front-month daily bars return a full history, not the 7-bar signature the A1 gate found
- [ ] T027 Run `scripts/trend_sleeve.py` in preview against the live account and check all eight markets produce sane targets and rounding errors
- [ ] T028 Place a single-contract test order in one market, verify fill and reconcile, then flatten it
- [ ] T029 Trim the ETF sleeves ~20% to fund the sleeve, then place the full trend book
- [ ] T030 Record realised gross exposure and margin usage against the assumptions in the plan

---

## Phase 7: Polish

- [X] T031 Run `.venv/bin/python -m pytest -q` and `ruff check .`; confirm green and no new violations
- [X] T032 Update `specs/000-baseline/baseline.md` — sleeve deployed, allocations, and what remains unverified
- [X] T033 Document the sleeve in `docs/scheduled-paper-track.md` alongside the other four

---

## Dependencies

```
Phase 1 -> Phase 2 (roll)  BLOCKS everything that places orders
   └─> Phase 3 US1 (guards)        MVP — the safety work
        └─> Phase 4 US2 (signal)   needs somewhere safe to send targets
             └─> Phase 5 US3 (schedule)
                  └─> Phase 6 (live) ── BLOCKED on the market-data subscription
                       └─> Phase 7
```

Unlike previous features the stories are strictly sequential, because each is a precondition for the
next being safe rather than merely useful.

## Implementation Strategy

**MVP = Phases 1–3.** That is the executor, and it is the part worth being slow about. It can be
built and fully tested offline while the market-data subscription is arranged.

**US1 is the priority for risk reasons, not value reasons.** Every other feature in this repo put the
valuable thing first. Here the valuable thing is the signal, and it is P2 — because this is the first
feature to trade an asset class the engine has never touched, and the failure mode is placing wrong
orders in a live account rather than reporting a wrong number.

**Do not skip T028.** One contract, verified, flattened — before the full book. The FX and basket
sleeves both had guard bugs that only surfaced on first real placement (the basket's per-order cap
aborted its first run; the cash sleeve's cap made placement impossible at all). Assume this one does
too.

**Expect the first live reading to disagree with the gate.** The signal evidence is ETF-proxy and the
implementation is futures. SC-004 exists to measure that gap rather than assume it away.
