# Feature Specification: Futures History via LEAN

**Feature Branch**: none — work proceeds on `main`; `specs/006-lean-futures-data/` is the feature identity

**Created**: 2026-08-17

**Status**: Draft

**Input**: Stages 0–1 of [`lean-migration-plan.md`](../../docs/lean-migration-plan.md)

## Context

The futures trend sleeve (spec `005`) is built and tested but cannot run: IBKR returns **0 bars** for
all eight markets without a market-data subscription, and the sleeve correctly refuses to trade on
that. Separately, the A2 gate's evidence is ETF proxies while its recommended implementation is
futures — an acknowledged, unclosed gap.

Both are the same missing input: **futures price history**.

QuantConnect/LEAN can supply it without an IBKR subscription. This feature obtains that data and
nothing else. It is explicitly **not** a framework migration — see
[`platform-decision.md`](../../docs/platform-decision.md) for why that would trade real assets for no
gain.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find out whether the data exists at all (Priority: P1)

As the researcher, I want a written answer on whether LEAN carries usable futures history for the
eight markets, so the question closes either way without building anything.

**Why this priority**: This is the entire decision. If the data is absent, unadjusted, or expensive,
nothing else in this feature should be built — and that outcome costs an afternoon.

**Independent Test**: Read the gate document and know whether to proceed.

**Acceptance Scenarios**:

1. **Given** the eight markets, **When** the gate runs, **Then** it records coverage and start date
   per market.
2. **Given** the data, **Then** the gate states whether it is roll-adjusted or whether individual
   contracts allow an honest continuous series to be built.
3. **Given** the offering, **Then** the gate records the cost and whether local download works without
   a cloud subscription.
4. **Given** any of those failing, **Then** the gate records a clear negative and the feature stops.

---

### User Story 2 - Get futures history into the framework (Priority: P2)

As the researcher, I want futures history cached in the form the framework already reads, so existing
tooling works on it unchanged.

**Why this priority**: Only worth doing once US1 passes.

**Acceptance Scenarios**:

1. **Given** a successful gate, **When** the loader runs, **Then** daily history for each market is
   cached locally and readable offline thereafter.
2. **Given** cached data, **Then** the framework reads it without knowing LEAN exists.
3. **Given** a market whose data is missing or short, **Then** the loader reports it rather than
   silently returning a truncated series.
4. **Given** the data, **Then** its roll convention is recorded alongside it, because an unadjusted
   series would invalidate any result built on it.

---

### Edge Cases

- **Unadjusted continuous series.** The failure that made commodity carry untestable. If the data is
  unadjusted and individual contracts are unavailable, it is unusable for this purpose and must be
  reported as such rather than used.
- **Partial coverage** — some markets back to 2007, others much shorter. The gate must report per
  market, since the construction needs a common window.
- **Data that requires a paid subscription to download** — a legitimate outcome, but it must be
  costed before commitment, not discovered afterwards.
- **A market absent entirely**, requiring a substitute or a smaller universe, which would mean
  re-running the A2 gate on the changed universe.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The gate MUST record, per market, whether daily history exists and from what date.
- **FR-002**: The gate MUST record the roll convention, and MUST treat an unadjusted continuous series
  as a failure for this purpose.
- **FR-003**: The gate MUST record cost and whether local download works without a cloud subscription.
- **FR-004**: The gate MUST produce a written negative if the data is unusable, and the feature MUST
  stop there.
- **FR-005**: The loader MUST cache history locally in the format the framework already reads, and be
  offline thereafter.
- **FR-006**: The framework MUST NOT gain a dependency on LEAN; the loader is a translation layer.
- **FR-007**: Missing or short data MUST be reported, never silently truncated.
- **FR-008**: The loader MUST be unit-testable offline against fixtures, with no network.

### Key Entities

- **Market**: one of the eight trend markets, with its LEAN identifier and its framework symbol.
- **Roll convention**: how the continuous series was constructed, or that it was not.
- **Coverage**: per-market start date and observation count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader can tell from the gate document whether futures history is obtainable, at what
  cost, and with what roll convention — without running anything.
- **SC-002**: If the gate passes, the A2 trend gate can be re-run on futures data using the existing
  construction unchanged.
- **SC-003**: The framework reads the cached data with no knowledge of its origin.
- **SC-004**: A stopped feature — the gate failing — leaves the repo exactly as it was, plus a
  recorded negative.

## Assumptions

- LEAN CLI runs locally in Docker and can download data without a cloud subscription. **Unverified** —
  it is the first thing the gate checks.
- Daily bars suffice. The trend construction is monthly-rebalanced; intraday data is not needed.
- The eight-market universe is fixed by spec `005`. If a market is unavailable, that changes the
  universe, which means re-running the A2 gate rather than quietly substituting.
- Cost is unknown. The docs did not make pricing legible, so no budget is assumed.

## Dependencies

- Docker, for the LEAN CLI.
- A QuantConnect account, possibly free.

## Out of Scope

- Any framework migration, strategy porting, or execution through LEAN. See
  [`lean-migration-plan.md`](../../docs/lean-migration-plan.md) stages 3–5, which are conditional and
  in one case explicitly declined.
- Re-running the A2 gate. That is the *next* feature, and only if this one passes.
