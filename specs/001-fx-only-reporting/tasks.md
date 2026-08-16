# Tasks: FX-Only Performance Reporting

**Input**: Design documents from `/specs/001-fx-only-reporting/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli-output.md](./contracts/cli-output.md)

**Tests**: **REQUIRED, not optional.** Constitution Principle III mandates pytest coverage for all new
code and requires it to run offline. Test tasks are therefore ordered before their implementation
tasks, per the repo's test-first practice.

**Organization**: Grouped by user story so each can be implemented and verified independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, or additive test cases with no shared edit)
- **[Story]**: US1 / US2 / US3, mapping to spec.md user stories
- Exact file paths included in every task

## Path Conventions

Single project, two packages. Pure logic in `forex/run/`, thin driver in `scripts/`, tests in
`tests/` — matching the existing `basket_track.py` / `fxbook.py` precedent recorded in plan.md.

---

## Phase 1: Setup

**Purpose**: The one shared piece every later test needs.

- [ ] T001 Add a `history()` test helper that builds `nav.csv` content from a list of daily rows, supporting rows with missing FX columns and multiple rows per day, in `tests/test_fxtrack.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The load-and-derive layer every user story sits on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Write failing tests for snapshot loading — FX-bearing filter, day-last collapse, timestamp ordering, and that non-FX rows survive for whole-account use — in `tests/test_fxtrack.py`
- [ ] T003 Implement snapshot loading and the FX-bearing filter returning a daily-collapsed sequence in `forex/run/fxtrack.py`
- [ ] T004 [P] Write failing tests for per-observation derivation — `pnl`, `carry_pnl`, the `spot_pnl` residual identity, `ret` against **prior** `gross_base`, and `gap_days` — in `tests/test_fxtrack.py`
- [ ] T005 Implement the `FxObservation` derivation per [data-model.md](./data-model.md) in `forex/run/fxtrack.py`

**Checkpoint**: A clean daily FX P&L series exists. User stories can now proceed.

---

## Phase 3: User Story 1 — Judge the FX book against its backtest (Priority: P1) 🎯 MVP

**Goal**: Print FX-book return, volatility, Sharpe, and max drawdown separately from the whole
account, with the walk-forward expectation attached to the FX figures only.

**Independent Test**: Run the report against a constructed FX-bearing history and confirm the FX
statistics differ from the whole-account statistics and are hand-traceable to the recorded values.

- [ ] T006 [P] [US1] Write failing tests for the aggregate — total return, annualised return, annualised vol, Sharpe, max drawdown over a constructed 25-observation history — in `tests/test_fxtrack.py`
- [ ] T007 [US1] Implement `fx_performance()` returning the aggregate per [data-model.md](./data-model.md), annualising on 252 days, in `forex/run/fxtrack.py`
- [ ] T008 [P] [US1] Write a failing test proving FX figures are invariant to `nav` — two histories identical in FX columns, one with `nav` flat and one up 20%, must yield identical FX output (SC-002, quickstart Scenario 1) — in `tests/test_fxtrack.py`
- [ ] T009 [US1] Add a labelled `FX BOOK ONLY (carry_cot_mom)` section to `scripts/track_report.py`, sourcing every figure from `fxtrack` and never from `nav`
- [ ] T010 [US1] Label the existing output `WHOLE ACCOUNT (FX book + ETF sleeves)` and add the sleeve-share note in `scripts/track_report.py`
- [ ] T011 [US1] Move the `~1.15` walk-forward expectation so it appears only in the FX section (C-02, FR-004) in `scripts/track_report.py`

**Checkpoint**: The report answers the question it exists to answer. See Implementation Strategy
before trusting live output.

---

## Phase 4: User Story 2 — Separate carry from spot (Priority: P2)

**Goal**: Show how much of FX P&L is interest accrual versus exchange-rate movement.

**Independent Test**: Run against a history where accrual falls while net rises and confirm both
components appear and sum to the total.

- [ ] T012 [P] [US2] Write failing tests for the decomposition — components sum to total exactly, and a negative carry is reported rather than netted away (SC-003, C-05, quickstart Scenario 2) — in `tests/test_fxtrack.py`
- [ ] T013 [US2] Surface cumulative `carry_pnl` and `spot_pnl` on the aggregate in `forex/run/fxtrack.py`
- [ ] T014 [US2] Print the `P&L: <total> (carry <c> + spot <s>)` line per the output contract in `scripts/track_report.py`

**Checkpoint**: Backlog #4 (negative carry accrual) becomes observable over time.

---

## Phase 5: User Story 3 — Trust the numbers or be told not to (Priority: P3)

**Goal**: Never present a statistic the sample cannot support, and never present contaminated data as
clean.

**Independent Test**: Run against 1-, 4-, and 25-observation histories and a rebalance-containing
history, and confirm the report withholds or flags exactly as specified.

- [ ] T015 [P] [US3] Write failing tests for rebalance detection — the real `13 → 20 → 20 → 13` pattern from [research.md R1](./research.md), plus a rotation that leaves `fx_legs` unchanged — in `tests/test_fxtrack.py`
- [ ] T016 [US3] Implement rebalance flagging via a trailing-window ETF baseline and unsettled-trade count, including the T+2 trailing observation, in `forex/run/fxtrack.py`
- [ ] T017 [US3] Exclude contaminated observations from ratio statistics while retaining and exposing the excluded count, in `forex/run/fxtrack.py`
- [ ] T018 [P] [US3] Write failing tests for the sample gate — 1, 4, and 25 observations produce levels-only, P&L-only, and full statistics respectively, with no `nan`/`inf`/`0` stand-ins (C-07, quickstart Scenario 4) — in `tests/test_fxtrack.py`
- [ ] T019 [US3] Implement the 2-observation and 20-observation thresholds with explanatory messages in `forex/run/fxtrack.py`
- [ ] T020 [P] [US3] Write a failing test that an FX-less legacy history preserves the whole-account output and reports the FX section unavailable (C-08, quickstart Scenario 5) — in `tests/test_fxtrack.py`
- [ ] T021 [US3] Implement the degraded-mode FX section for FX-less histories in `scripts/track_report.py`
- [ ] T022 [US3] Print the FX period, observation count, excluded count with reason, and the gross-exposure return basis (C-03, C-04, C-06) in `scripts/track_report.py`

**Checkpoint**: Output is safe to act on — or says why it is not.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Write failing guard tests — zero `fx_gross_base`, a multi-day curve gap not annualised as one day, and two snapshots on one day (quickstart Scenario 6) — in `tests/test_fxtrack.py`
- [ ] T024 Implement the degenerate-input guards in `forex/run/fxtrack.py`
- [ ] T025 Run the live smoke test `.venv/bin/python scripts/track_report.py` and confirm single-observation mode against the real `nav.csv` (net 129, gross 996,532, accrued −841, no Sharpe)
- [ ] T026 Run `.venv/bin/python -m pytest -q` and `ruff check .`; confirm all green and **no new** violations beyond the 21 pre-existing (Backlog #8)
- [ ] T027 Move Backlog #1 to Completed and update In-flight item 1 in `specs/000-baseline/baseline.md`
- [ ] T028 Add a backlog entry for the explicit rebalance marker written at trade time (the robust alternative deferred in [research.md R1](./research.md)) in `specs/000-baseline/baseline.md`

---

## Dependencies

```
Phase 1 (T001)
   └─> Phase 2 (T002–T005)          BLOCKS everything
          ├─> Phase 3 US1 (T006–T011)   ── MVP
          ├─> Phase 4 US2 (T012–T014)   ── independent of US1 and US3
          └─> Phase 5 US3 (T015–T022)   ── independent of US1 and US2
                 └─> Phase 6 (T023–T028)
```

**Story independence**: US1, US2, and US3 touch the same two files but disjoint concerns, and none
depends on another's output. They can be built in any order once Phase 2 lands.

**One caveat on independence**: US1 alone prints statistics with no sample gate. It is a valid,
testable increment, but see Implementation Strategy before pointing it at live data.

## Parallel Opportunities

- **Phase 2**: T004 is `[P]` — it is an additive test case, writable while T003 is in progress.
- **Phase 3**: T006 and T008 are `[P]` with each other (independent test cases). T009–T011 all edit
  `scripts/track_report.py` and must be sequential.
- **Phase 5**: T015, T018, and T020 are `[P]` — three independent test groups. Their implementations
  (T016/T017, T019, T021) are not, where they share a file.
- **Across stories**: after Phase 2, one person could take US2 while another takes US3.

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1)** — 11 tasks. That delivers the feature's whole reason for
existing: FX-book performance judged against its backtest instead of against the ETF sleeves.

**But ship US3 before trusting live output.** Only one FX-bearing snapshot exists today, so US1 alone
would compute a Sharpe from a sample that cannot support one. US3's gate is what makes the live
report honest. Recommended order: **US1 → US3 → US2**, which departs from strict priority order
because US3 protects US1's correctness while US2 is purely additive.

**Incremental delivery**: each phase leaves the suite green and the report runnable. US2 and US3 can
land in separate commits.

**Expect an unflattering first reading.** Per [research.md R2](./research.md), the FX book is roughly
flat since inception (~+129 base on ~1M gross, spot +970 against carry −841). The report's job is to
show that plainly; the sample gate is what stops one month reading as a verdict.
