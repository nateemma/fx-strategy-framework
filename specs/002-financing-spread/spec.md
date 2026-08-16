# Feature Specification: Financing-Spread Diagnosis

**Feature Branch**: none — work proceeds on `main`; `specs/002-financing-spread/` is the feature identity

**Created**: 2026-08-16

**Status**: Draft

**Input**: Backlog #3 — investigate negative carry accrual (−841 base)

## Context

`carry_cot_mom` exists to harvest interest-rate differentials. The paper account is **paying** them:
accrued interest across the book is −841 base.

The backtest cannot see this. `forex/backtest/portfolio.py` accrues `carry/252` where carry is the
full interbank differential from FRED (`forex/features/carry.py`, `r - usd`) — **no broker financing
spread at all**. Live, you are paid below benchmark on long balances and charged at or above it on
shorts, on both legs of a dollar-neutral book.

A preliminary measurement (2026-08-16, live account) shows the asymmetry is large: dividing each
currency's realised `accrued/balance` by its FRED benchmark gives a median of **0.0121 for longs
against 0.0506 for shorts** — a 4.2× gap. Every currency shares the same accrual window, so that
ratio is period-independent and the comparison holds without knowing when interest last posted.
Benchmark carry on the current book is **+2,156/yr**; realised is roughly **−10,000 to −16,600/yr**.

If that survives scrutiny, the carry leg is not merely reduced but inverted, and every backtest in
the program overstates the deployable edge. **The decisive caveat is that this is a paper account,
and `docs/income-enhancements.md` records that its cash interest is simulated** — so this feature
must measure and document rigorously without claiming to have established live IBKR economics.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Measure the financing gap (Priority: P1)

As the operator, I want to see, per currency, what the account actually accrues against what the
backtest assumes, so I can tell whether the strategy's carry thesis survives real financing.

**Why this priority**: This is the question. Everything else is consequence.

**Independent Test**: Run the diagnostic against the live account and confirm it reports per-currency
realised-versus-benchmark ratios, with longs and shorts separated.

**Acceptance Scenarios**:

1. **Given** a connected account, **When** the diagnostic runs, **Then** it reports for each open
   currency leg: side, USD exposure, accrued, FRED benchmark rate, and the realised/benchmark ratio.
2. **Given** the same run, **Then** it reports the median ratio for longs and for shorts separately,
   and states that the ratio is period-independent.
3. **Given** a currency whose benchmark rate is near zero, **Then** the ratio is suppressed rather
   than reported as a meaningless large number.

---

### User Story 2 - Carry measurement survives interest posting (Priority: P2)

As the operator, I want the carry/spot split in the forward track to stay correct across IBKR's
monthly interest posting, so the very number this investigation depends on is not corrupted.

**Why this priority**: A defect in the instrument. Shipped in feature 001 and not yet triggered,
because no posting has occurred since FX recording began — it will corrupt the first month it does.

**Independent Test**: Run the track report over a history containing a posting reset and confirm
carry is not reported as a large positive jump.

**Acceptance Scenarios**:

1. **Given** a history where accrued moves sharply toward zero while net value is continuous,
   **When** the report runs, **Then** carry is not credited with the reset amount.
2. **Given** the same history, **Then** cumulative carry and spot still sum exactly to total P&L.
3. **Given** the same history, **Then** the report states how many observations had carry estimated
   rather than measured.

---

### User Story 3 - Quantify the drag against the backtest (Priority: P3)

As the operator, I want the measured financing gap expressed as an annual drag on the deployed book,
so I can judge it against the ~3%/yr unlevered expectation and decide whether the backtest needs a
financing-spread term.

**Why this priority**: Converts a diagnostic into a decision. Depends on US1.

**Independent Test**: Confirm the diagnostic reports benchmark carry, realised carry, and the gap,
each annualised and as a percentage of gross exposure.

**Acceptance Scenarios**:

1. **Given** a completed measurement, **Then** the report states benchmark annual carry, realised
   annual carry, and the difference, in both currency and percent-of-gross terms.
2. **Given** the accrual period is not directly observable, **Then** the report states the period
   assumption and shows the drag across a plausible range rather than a single false-precision number.
3. **Given** the account is a paper account, **Then** the report prominently states that its
   financing may be simulated and must not be taken as live IBKR economics.

---

### Edge Cases

- **A currency with a near-zero or negative benchmark rate** (CHF at −0.045%): the ratio is unstable
  or sign-flipped and must be excluded from medians, not silently included.
- **A leg with zero accrual** (NZD): real and meaningful — it means nothing was paid — and must be
  distinguished from missing data.
- **A stale benchmark rate**: FRED interbank series are monthly and some lag (EUR/GBP currently
  2026-01). The report must state each rate's as-of date rather than implying it is current.
- **A leg too small to matter**: negligible balances should not distort medians.
- **No broker connection**: the diagnostic must fail clearly, not report zeros.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The diagnostic MUST report, per open currency leg, the realised accrual, the FRED
  benchmark rate with its as-of date, and the realised/benchmark ratio.
- **FR-002**: The diagnostic MUST separate longs from shorts and report each side's median ratio.
- **FR-003**: The diagnostic MUST exclude legs whose benchmark rate is too near zero for a ratio to
  be meaningful, and MUST report how many were excluded and why.
- **FR-004**: The diagnostic MUST report benchmark annual carry, realised annual carry, and the gap,
  in currency and as a percentage of gross exposure.
- **FR-005**: The diagnostic MUST state its accrual-period assumption and express the annualised
  figures as a range across plausible periods, never as a single unqualified number.
- **FR-006**: The diagnostic MUST state that the account is a paper account whose financing may be
  simulated, wherever it reports a conclusion.
- **FR-007**: The forward-track carry/spot split MUST NOT credit carry with an interest-posting reset.
- **FR-008**: Cumulative carry and spot MUST continue to sum exactly to total P&L (feature 001,
  SC-003), including across a posting.
- **FR-009**: The forward-track report MUST state how many observations had carry estimated rather
  than measured.
- **FR-010**: All measurement logic MUST be unit-testable offline, with no broker connection.
- **FR-011**: The findings MUST be written to a durable document, including the paper-account caveat
  and what would be needed to confirm the result on a live account.

### Key Entities

- **Currency leg**: an open non-base cash balance, with its accrued interest, USD exposure, and side.
- **Benchmark rate**: the FRED 3-month interbank rate the backtest's carry signal uses, with as-of date.
- **Realised/benchmark ratio**: `(accrued / balance) / benchmark_rate`. Equals the accrual period if
  financing were at benchmark; divergence between sides is the finding.
- **Financing gap**: benchmark annual carry minus realised annual carry.
- **Posting event**: IBKR moving accrued interest into cash, resetting accrued toward zero while
  leaving net book value continuous.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The operator can state, from one run, whether the deployed book earns or pays its
  interest differential, and by how much per year.
- **SC-002**: The long/short asymmetry is reported as a figure that does not depend on knowing when
  interest last posted.
- **SC-003**: Every reported rate carries its as-of date; no figure implies currency it lacks.
- **SC-004**: Carry and spot sum to total P&L across a posting event, and estimated observations are
  counted in the output.
- **SC-005**: No conclusion about live IBKR economics is stated without the paper-account caveat
  attached to it.
- **SC-006**: A reader can reproduce the measurement from the durable findings document.

## Assumptions

- FRED 3-month interbank rates are the right benchmark, because they are exactly what the backtest's
  carry signal uses. The comparison is against the model's own assumption, not against a market truth.
- The accrual period is the same for every currency in a single snapshot, which is what makes the
  cross-currency ratio period-independent. This is the load-bearing assumption of the method.
- IBKR accrues daily and posts monthly. The posting date is not directly observable from recorded
  data, so posting events are detected from the accrual series itself.
- Once posting is detected, that observation's carry is estimated from recent daily accrual rather
  than measured. Interest accrues smoothly, so the estimate is good — but it is an estimate.
- The paper account may not reproduce live financing. This feature measures and documents; it cannot
  settle live economics.

## Dependencies

- Feature 001 (`forex/run/fxtrack.py`) supplies the carry/spot split this feature repairs.
- Cached FRED rate series in `data_cache/`. Present for all 15 universe currencies.
- A connected IB Gateway for the live diagnostic; the pure measurement logic needs none.
