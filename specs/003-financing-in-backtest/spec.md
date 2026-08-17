# Feature Specification: Financing Cost in the Backtest

**Feature Branch**: none — work proceeds on `main`; `specs/003-financing-in-backtest/` is the feature identity

**Created**: 2026-08-16

**Status**: Draft

**Input**: Backlog #3 (highest priority) — add a financing-spread term to the backtest

## Context

The backtest credits every held position with the full interbank rate differential
(`forex/backtest/portfolio.py`, `carry/252`) and charges 3–5bp per trade. It charges **nothing for
holding**.

[`docs/financing-spread-findings.md`](../../docs/financing-spread-findings.md) established, against
IBKR's *published* rate schedule, that holding this book actually costs **−2.18% of gross per year**:
you are paid `benchmark − spread` on long balances (floored at zero) and charged
`benchmark + spread` on short ones, on both legs of a dollar-neutral book.

Every walk-forward number in this program was produced without that cost — including the **Sharpe
1.15** on which `carry_cot_mom` was selected as the deployable book. Until financing is modelled, the
framework cannot answer whether the chosen book is genuinely best or merely best under an assumption
now known to be wrong.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Charge financing in a backtest (Priority: P1)

As a researcher, I want the backtest to charge what holding a position actually costs, so results
reflect deployable economics rather than an idealised differential.

**Why this priority**: Everything else depends on the model being able to express the cost at all.

**Independent Test**: Run the same strategy with and without financing enabled and confirm the
financed run returns strictly less, by an amount traceable to the position sizes held.

**Acceptance Scenarios**:

1. **Given** a strategy and a universe, **When** a backtest runs with financing enabled, **Then**
   returns are reduced by a per-currency cost proportional to the absolute weight held.
2. **Given** the same run, **Then** a long position and a short position of equal size are **both**
   charged — financing is never a credit.
3. **Given** financing is not enabled, **Then** results are identical to before this feature, so
   every prior result remains reproducible.

---

### User Story 2 - Quantify the impact on the deployable book (Priority: P2)

As the operator, I want to know what financing does to `carry_cot_mom`'s walk-forward Sharpe, so I
can judge whether the deployable book survives its own costs.

**Why this priority**: This is the decision the feature exists to inform. It needs US1 first.

**Independent Test**: Walk-forward the deployable book with and without financing over the same
window and compare the reported metrics.

**Acceptance Scenarios**:

1. **Given** the deployable book and universe, **When** walk-forward runs both ways, **Then** the
   Sharpe, return, and drawdown of each are reported side by side.
2. **Given** that comparison, **Then** the result is written to a durable document, whatever it shows
   — including if it shows the book is not viable.

---

### User Story 3 - The assumption is visible and adjustable (Priority: P3)

As a researcher, I want the financing schedule to be inspectable and overridable, so its assumptions
can be challenged rather than buried.

**Why this priority**: The schedule is a broker's published table at one point in time, applied
across decades of history. That is a strong assumption and must not be invisible.

**Independent Test**: Inspect the encoded schedule, override a spread, and confirm the result moves.

**Acceptance Scenarios**:

1. **Given** the encoded schedule, **When** a researcher inspects it, **Then** each currency's credit
   and debit spread is visible with its source.
2. **Given** an overridden schedule, **When** a backtest runs, **Then** the cost changes accordingly.
3. **Given** a currency absent from the schedule, **Then** the run fails clearly rather than silently
   charging zero.

---

### Edge Cases

- **A currency whose benchmark rate is below its credit spread** (NZD today: 2.098% benchmark,
  2.5% spread): the broker floors credit at zero, so the effective cost is the whole rate, not the
  spread. Must be modelled, not approximated.
- **A currency that earns nothing on any balance** (ILS): same mechanism at the limit.
- **A negative benchmark rate** (CHF): borrowing should earn, but the spread still applies.
- **A zero-weight currency**: no position, so no financing cost.
- **Historical dates far before the schedule was published**: the model must state this assumption
  rather than implying the rates were in force.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backtest MUST be able to charge a per-currency financing cost on held positions,
  in addition to the existing per-trade cost.
- **FR-002**: The financing cost MUST always reduce returns, for both long and short positions.
- **FR-003**: The cost MUST scale with the absolute size of the position held.
- **FR-004**: Long positions MUST be charged the currency's credit shortfall plus the base currency's
  borrowing spread; short positions MUST be charged the currency's borrowing spread plus the base
  currency's credit shortfall.
- **FR-005**: The credit shortfall MUST respect the broker's zero floor — a currency whose benchmark
  is below its credit spread earns nothing, and the model MUST charge the full benchmark rather than
  the nominal spread.
- **FR-006**: Financing MUST be off by default, and with it off every existing result MUST be
  bit-for-bit reproducible.
- **FR-007**: Enabling financing MUST be available from the command line for every mode that runs a
  backtest.
- **FR-008**: The schedule MUST be inspectable, with each currency's spreads and their source
  recorded alongside the values.
- **FR-009**: A currency missing from the schedule MUST cause a clear failure, never a silent
  zero-cost assumption.
- **FR-010**: The impact on the deployable book MUST be measured and written to a durable document,
  reported faithfully whatever it shows.
- **FR-011**: The model's known approximations MUST be documented where the schedule lives, so a
  reader cannot mistake it for exact.

### Key Entities

- **Credit spread**: how far below benchmark the broker pays on a long balance, floored so credit is
  never negative.
- **Debit spread**: how far above benchmark the broker charges on a borrowed balance.
- **Financing cost**: for a held weight, the annualised rate by which realised carry falls short of
  the benchmark differential. Always a cost, on both sides.
- **Schedule**: the per-currency table of credit and debit spreads, with its source and date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A researcher can state what `carry_cot_mom` earns after financing, and whether it still
  clears the bar it was selected on.
- **SC-002**: Turning financing off reproduces every pre-existing result exactly.
- **SC-003**: For any strategy and universe, the financed run never scores better than the unfinanced
  one.
- **SC-004**: The modelled cost for the currently deployed book agrees with the independently measured
  −2.18%/yr of gross, to within the stated approximations.
- **SC-005**: Every assumption behind the schedule is written where a reader will find it before
  relying on the number.

## Assumptions

- The broker's published schedule at one date is applied across all history. Spreads change over
  time and were certainly different pre-2010; this models "what would this book cost to hold under
  today's terms", not "what it would have cost then".
- Tier-1 spreads are used. Larger accounts receive better debit tiers, so this is conservative for a
  large book and roughly right for the ~1M book actually deployed.
- The zero-interest tranche on the first slice of each currency balance is **not** modelled, because
  it depends on account size, which the framework has no concept of. That omission understates cost.
  Working the other way, rate levels come from FRED rather than IBKR's own benchmark and currently run
  higher for several currencies, which overstates the floored credit shortfall. The two do not cancel
  predictably, so the result is **not a bound in either direction** — it is calibrated against the
  live measurement instead.
- The base currency is USD, matching the existing carry convention.
- Financing is charged on the position actually held, using the same one-day-lagged convention the
  existing simulation uses, so no lookahead is introduced.

## Dependencies

- `docs/financing-spread-findings.md` supplies the schedule and the −2.18%/yr validation target.
- Rate *levels* (not just differentials) are needed for the zero floor; they are already available on
  the `DataView`.
