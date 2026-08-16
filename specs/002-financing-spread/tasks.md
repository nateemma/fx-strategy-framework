# Tasks: Financing-Spread Diagnosis

**Input**: Design documents from `/specs/002-financing-spread/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md)

**Tests**: **REQUIRED.** Constitution Principle III mandates pytest coverage running offline. Test
tasks precede their implementations.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Add a test helper building currency-leg records (balance, accrued, rate, benchmark) in `tests/test_financing.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T002 Write failing tests for the realised/benchmark ratio — including that it is period-independent across currencies — in `tests/test_financing.py`
- [X] T003 Implement the per-leg ratio and `CurrencyLeg` record in `forex/run/financing.py`
- [X] T004 [P] Write failing tests for benchmark-rate loading from cached FRED parquet, returning the rate with its as-of date, in `tests/test_financing.py`
- [X] T005 Implement cached benchmark-rate lookup keyed off `forex.config.CURRENCIES` in `forex/run/financing.py`

**Checkpoint**: Per-leg measurement exists and is testable offline.

---

## Phase 3: User Story 1 — Measure the financing gap (Priority: P1) 🎯 MVP

- [X] T006 [P] [US1] Write failing tests for long/short median ratios, including that near-zero-benchmark legs are excluded and counted (FR-002, FR-003) — in `tests/test_financing.py`
- [X] T007 [US1] Implement side split and median ratios with the near-zero-benchmark exclusion in `forex/run/financing.py`
- [X] T008 [P] [US1] Write a failing test that a zero-accrual leg is reported as measured-zero, not missing data (edge case) — in `tests/test_financing.py`
- [X] T009 [US1] Implement `scripts/financing_report.py` — read-only broker snapshot, per-leg table with benchmark as-of dates, long/short medians

**Checkpoint**: The asymmetry is measurable on demand.

---

## Phase 4: User Story 2 — Carry measurement survives posting (Priority: P2)

- [X] T010 [P] [US2] Write failing tests for posting detection and carry estimation — a reset toward zero must not be credited as carry, and carry + spot must still equal total (FR-007, FR-008) — in `tests/test_fxtrack.py`
- [X] T011 [US2] Implement posting detection and trailing-median carry estimation in `forex/run/fxtrack.py`
- [X] T012 [US2] Expose the estimated-observation count on `FxPerformance` and print it in `scripts/track_report.py` (FR-009)

**Checkpoint**: The instrument feature 001 shipped is now correct across a month boundary.

---

## Phase 5: User Story 3 — Quantify the drag (Priority: P3)

- [X] T013 [P] [US3] Write failing tests for benchmark vs realised annual carry and the gap, in currency and percent-of-gross (FR-004) — in `tests/test_financing.py`
- [X] T014 [US3] Implement the annualised benchmark/realised/gap computation in `forex/run/financing.py`
- [X] T015 [US3] Report the drag across a plausible accrual-period range rather than a point estimate (FR-005) in `scripts/financing_report.py`
- [X] T016 [US3] Print the paper-account caveat alongside every conclusion (FR-006, SC-005) in `scripts/financing_report.py`

---

## Phase 6: Polish & Findings

- [X] T017 Run the live diagnostic and capture the real measurement via `.venv/bin/python scripts/financing_report.py`
- [X] T018 Write `docs/financing-spread-findings.md` — method, result, the paper-account caveat, and what a live confirmation would require (FR-011)
- [X] T019 Run `.venv/bin/python -m pytest -q` and `ruff check .`; confirm green and no new violations beyond the 21 pre-existing
- [X] T020 Update `specs/000-baseline/baseline.md` — close Backlog #3, record the finding, and add any follow-up it creates

---

## Dependencies

```
Phase 1 (T001) -> Phase 2 (T002-T005) BLOCKS all
   ├─> US1 (T006-T009)   MVP
   ├─> US2 (T010-T012)   independent — touches fxtrack, not financing
   └─> US3 (T013-T016)   depends on US1's per-leg measurement
        └─> Phase 6 (T017-T020)
```

US2 is fully independent of US1/US3 — it repairs feature 001's module and could ship alone.

## Implementation Strategy

**MVP = Phases 1–3.** That answers the question: is the book earning or paying its differential.

US2 is the highest-urgency *correctness* item even though it is P2, because it is a live defect in
shipped code. It has not bitten yet only because no interest posting has occurred since FX recording
began on 2026-08-16 — it will bite at the first month boundary.

**The finding is the deliverable, not the code.** T018 matters more than any module here. The
constraint that governs it: this is a paper account whose interest may be simulated, so the honest
output is a measured asymmetry plus a clear statement of what it does and does not establish.
