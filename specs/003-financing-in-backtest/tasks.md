# Tasks: Financing Cost in the Backtest

**Input**: Design documents from `/specs/003-financing-in-backtest/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md)

**Tests**: **REQUIRED** (Constitution III). Test tasks precede their implementations.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Add a test helper building a small rates/weights fixture with known spreads in `tests/test_financing_cost.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T002 Write failing tests for the schedule — every `TRADEABLE_CARRY` currency plus USD present, spreads positive, source recorded — in `tests/test_financing_cost.py`
- [X] T003 Encode IBKR's published credit/debit spreads with their source and date in `forex/backtest/financing.py`
- [X] T004 [P] Write failing tests for spread computation — the `min(rate, spread)` zero floor, NZD flooring to earn nothing, ILS earning nothing on any balance, and an unknown currency raising — in `tests/test_financing_cost.py`
- [X] T005 Implement `financing_spreads(rates, codes)` returning per-date long and short spreads in `forex/backtest/financing.py`

**Checkpoint**: Spreads computable and validated against the published limiting cases.

---

## Phase 3: User Story 1 — Charge financing in a backtest (Priority: P1) 🎯 MVP

- [X] T006 [P] [US1] Write failing tests that the cost is `|weight| × spread / 252`, charged on both long and short, and zero for a zero weight (FR-002, FR-003) — in `tests/test_financing_cost.py`
- [X] T007 [US1] Add the optional financing term to `simulate()` in `forex/backtest/portfolio.py`
- [X] T008 [P] [US1] Write a failing test that financing off reproduces the pre-existing result exactly (FR-006, SC-002) — in `tests/test_financing_cost.py`
- [X] T009 [US1] Thread financing through `returns_of`/`backtest` from the view's rates in `forex/run/backtest.py`
- [X] T010 [US1] Add the `financing` config field and `--financing` CLI flag in `forex/core/config.py` and `forex/cli.py`
- [X] T011 [US1] Verify `forex causal-check` still passes with financing enabled (Constitution II)

**Checkpoint**: The backtest can charge what holding actually costs.

---

## Phase 4: User Story 2 — Quantify the impact (Priority: P2)

- [X] T012 [US2] Walk-forward `carry_cot_mom` on the deliverable universe with and without financing, same window, and capture both metric sets
- [X] T013 [US2] Cross-check the modelled cost against the independently measured −2.18%/yr of gross (SC-004)
- [X] T014 [US2] Write the result into `docs/financing-spread-findings.md`, faithfully whatever it shows (FR-010)

---

## Phase 5: User Story 3 — Visible and adjustable (Priority: P3)

- [X] T015 [P] [US3] Write a failing test that an overridden schedule changes the cost (FR-008) — in `tests/test_financing_cost.py`
- [X] T016 [US3] Support a caller-supplied schedule override in `forex/backtest/financing.py`
- [X] T017 [US3] Document the encoded assumptions and the lower-bound property in the module docstring (FR-011)

---

## Phase 6: Polish

- [X] T018 Run `.venv/bin/python -m pytest -q` and `ruff check .`; confirm green and no new violations beyond the 21 pre-existing
- [X] T019 Update `specs/000-baseline/baseline.md` — close Backlog #3, record the measured impact, and add whatever follow-up it creates
- [X] T020 Update `README.md` if the headline deployability claim changed

---

## Dependencies

```
Phase 1 -> Phase 2 (T002-T005) BLOCKS all
   └─> US1 (T006-T011)  MVP
        ├─> US2 (T012-T014)   needs US1 to run at all
        └─> US3 (T015-T017)   independent of US2
             └─> Phase 6
```

## Implementation Strategy

**MVP = Phases 1–3.** The model can charge financing; everything after is measurement and polish.

**US2 is the point.** The code is a means to one number: what `carry_cot_mom` earns after financing.
T014 must record it faithfully — the plausible outcome is that the deployable book does not clear the
bar it was selected on, and the whole value of this work is being told that plainly rather than
discovering it with real money.

**T011 is not a formality.** Adding a data source to the return calculation is exactly where lookahead
enters. Causal-check must pass with financing on.
