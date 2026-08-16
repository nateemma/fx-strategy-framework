# Feature Specification: FX-Only Performance Reporting

**Feature Branch**: none — work proceeds on `main`; `specs/001-fx-only-reporting/` is the feature identity

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "FX-only performance reporting in track_report.py — Backlog #1"

## Context

The forward paper track reports whole-account performance. Because the ETF sleeves are roughly 90% of
account value, those numbers overwhelmingly measure the sleeves rather than the `carry_cot_mom` FX
book they are labelled as. The current report prints "forward paper track — carry_cot_mom" above a
Sharpe of 3.58 that the FX book did not earn.

The data needed to separate them is now recorded per snapshot (`fx_net_base`, `fx_gross_base`,
`fx_accrued_base`, `fx_legs`) but nothing reads it. This feature makes the forward track measure the
strategy, so it can be judged against its walk-forward expectation of Sharpe ~1.15.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Judge the FX book against its backtest (Priority: P1)

As the operator of the paper track, I want to see the FX book's own return, volatility, Sharpe, and
drawdown — separate from the ETF sleeves — so I can tell whether the deployed strategy is behaving
like its walk-forward estimate or has broken.

**Why this priority**: This is the entire purpose of running a forward track. Without it the track
record cannot answer the one question it exists to answer, and a strategy failure would be masked by
sleeve performance moving in the opposite direction.

**Independent Test**: Run the report against a snapshot history containing FX columns and confirm it
prints FX-only statistics that differ from the whole-account statistics, with the FX figures traceable
by hand to the recorded values.

**Acceptance Scenarios**:

1. **Given** a snapshot history with populated FX columns, **When** the report runs, **Then** it
   prints FX-only total return, annualised return, volatility, Sharpe, and maximum drawdown, clearly
   labelled as the FX book and visually distinct from whole-account figures.
2. **Given** the same history, **When** the report runs, **Then** it states the walk-forward
   expectation (Sharpe ~1.15) next to the realised FX Sharpe, not next to the whole-account Sharpe.
3. **Given** a history where the FX book lost money while the account gained, **When** the report
   runs, **Then** the FX section shows a negative return and the account section a positive one.

---

### User Story 2 - Separate carry from spot movement (Priority: P2)

As the operator, I want the FX book's P&L split into interest accrual and spot revaluation, so I can
see whether the carry the strategy exists to harvest is actually being earned.

**Why this priority**: A carry book that earns nothing from carry is not running the strategy, and
this is currently a live concern — accrued interest across the book is negative. This is
diagnostically valuable but secondary to knowing the headline number.

**Independent Test**: Run the report against a history where accrual and spot move in opposite
directions and confirm both components are reported and sum to the total.

**Acceptance Scenarios**:

1. **Given** a snapshot history, **When** the report runs, **Then** it shows cumulative carry accrual
   and cumulative spot revaluation, and their sum reconciles with total FX P&L.
2. **Given** a history where accrual is negative, **When** the report runs, **Then** the negative
   carry is displayed plainly rather than being netted invisibly into a single number.

---

### User Story 3 - Trust the numbers or be told not to (Priority: P3)

As the operator, I want the report to tell me when a statistic is not yet meaningful or is known to be
contaminated, so I do not act on a number that cannot support the conclusion.

**Why this priority**: The sample is currently one FX snapshot. A report that prints a confident
Sharpe from three days of data invites exactly the overfitting this project's methodology guards
against.

**Independent Test**: Run the report against a history with too few FX snapshots and confirm it
declines to print statistics, explaining what is missing.

**Acceptance Scenarios**:

1. **Given** fewer FX snapshots than the minimum needed, **When** the report runs, **Then** it prints
   the available raw values and states that statistics need more history, without printing a Sharpe.
2. **Given** a history whose early rows predate FX recording, **When** the report runs, **Then** those
   rows are excluded from FX statistics and the FX sample period is stated separately from the
   whole-account period.
3. **Given** a period containing a rebalance, **When** the report runs, **Then** the report indicates
   that affected observations carry rebalance flow, rather than presenting them as clean P&L.

---

### Edge Cases

- **No FX columns at all** (a history entirely predating the schema change): the report must still
  produce whole-account statistics and say the FX section is unavailable.
- **Partially populated FX columns**: rows before and after the schema change coexist; only populated
  rows count toward FX statistics.
- **Multiple snapshots on one day**: the existing report collapses to one point per day; FX statistics
  must use the same convention so the two sections cover identical periods.
- **A day with zero FX legs** (book fully closed): must not be treated as missing data or divided by.
- **Gaps in the daily curve** (a missed snapshot when the Gateway was down): must not be silently
  treated as a single-day move when annualising.
- **Zero or near-zero gross exposure** in a return denominator: must not produce an infinite or
  meaningless return.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The report MUST present FX-book performance separately from whole-account performance,
  in the same run, with each section unambiguously labelled.
- **FR-002**: The report MUST derive FX performance solely from the recorded FX values, never from
  whole-account value, so that ETF sleeve activity cannot influence it.
- **FR-003**: The report MUST present, for the FX book: total return, annualised return, annualised
  volatility, Sharpe ratio, and maximum drawdown.
- **FR-004**: The report MUST compare realised FX Sharpe against the walk-forward expectation of ~1.15,
  and MUST NOT present that expectation as a benchmark for whole-account performance.
- **FR-005**: The report MUST decompose FX P&L into interest accrual and spot revaluation, and the two
  components MUST reconcile with the total.
- **FR-006**: The report MUST exclude snapshots with no recorded FX values from FX statistics, and MUST
  state the FX sample period and count independently of the whole-account period and count.
- **FR-007**: The report MUST suppress FX statistics, with an explanation, when the FX sample is too
  small for them to be meaningful.
- **FR-008**: The report MUST exclude observations contaminated by rebalance flow from FX statistics,
  and MUST state how many observations were excluded and why. An excluded observation MUST NOT be
  silently treated as absent data.
- **FR-009**: FX returns MUST be expressed against the FX book's gross exposure at the start of each
  observation period, and the report MUST state that this is the base used. This makes realised
  figures directly comparable to the walk-forward expectation, which is quoted on the strategy's own
  capital at 1x gross.
- **FR-010**: The report MUST continue to produce its existing whole-account output unchanged for
  histories that contain no FX values, so no existing use of it breaks.
- **FR-011**: The report MUST remain runnable offline against the recorded history alone, requiring no
  broker connection, network access, or API key.

### Key Entities

- **Snapshot**: one dated observation of the account, carrying whole-account value alongside the FX
  book's net value, gross exposure, accrued interest, and open leg count.
- **FX book value**: the net worth of the FX positions in base currency, including accrued interest.
  Its change between snapshots is FX P&L. Unaffected by ETF trading, which moves only base-currency
  cash.
- **Carry accrual**: the accrued-interest component of FX book value — the return the carry strategy
  exists to harvest.
- **Spot revaluation**: FX P&L less carry accrual — the exchange-rate movement component.
- **Rebalance event**: a change to the FX book's target positions, which moves book value by a flow
  that is not P&L.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The operator can determine, from a single run, whether the FX book is meeting, beating,
  or missing its walk-forward expectation — without performing any arithmetic by hand.
- **SC-002**: FX-book statistics are unchanged by ETF sleeve activity: a sleeve rebalance of any size
  moves the whole-account figures and leaves the FX figures untouched.
- **SC-003**: Reported FX P&L reconciles to the recorded values to the cent, and its accrual and spot
  components sum to the total.
- **SC-004**: The report never presents a performance statistic derived from fewer observations than
  its stated minimum; it states what is missing instead.
- **SC-005**: Every reported FX figure states the period and observation count it was computed from.
- **SC-006**: A reader who does not know the implementation can tell from the output alone which
  figures describe the FX strategy and which describe the whole account.

## Assumptions

- The existing whole-account section stays; this feature adds to the report rather than replacing it.
  Both matter — the account figure is what the capital actually did.
- FX book value including accrued interest is the correct P&L level, because for a carry book the
  interest differential is the return. This was established when the recording was built.
- The report stays a read-only, on-demand command over the recorded history. It does not connect to
  the broker and does not backfill history it never recorded.
- Pre-2026-08-16 snapshots have no FX values and cannot be reconstructed; the FX track therefore
  begins later than the whole-account track and will be a very small sample for some weeks.
- Statistics use the same daily-resampling convention as the existing report, so both sections cover
  the same trading days.
- Rebalances are roughly monthly, so contaminated observations are rare but not negligible relative to
  a short sample. Excluding them costs roughly one observation per month, which is preferred to
  carrying a knowingly wrong value in a small sample.
- Rebalance days can be identified from the recorded history itself, without depending on the
  activity log, which is not versioned and so is not reproducible from a clone.
- No change is needed to how snapshots are recorded; the required values are already captured.

## Dependencies

- The snapshot history must contain the FX columns added on 2026-08-16. Only one such row exists
  today, so this feature is buildable and testable now (against constructed histories) but will not
  produce a meaningful live reading for several weeks.
- Constitution Principle III applies: the work needs test coverage and must run offline.
