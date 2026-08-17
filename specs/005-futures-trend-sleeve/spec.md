# Feature Specification: Cross-Asset Trend Sleeve (Futures)

**Feature Branch**: none — work proceeds on `main`; `specs/005-futures-trend-sleeve/` is the feature identity

**Created**: 2026-08-17

**Status**: Draft

**Input**: Backlog — build the cross-asset trend sleeve in futures, following the A2 gate

## Context

The account has had no equity-uncorrelated return source since `carry_cot_mom` was found to be
destroyed by retail financing. The ETF track is four sleeves that are all, ultimately, long risk
assets: its drawdown is −17.7% and nothing in it helps on a bad day.

The A2 gate ([`cross-asset-trend-findings.md`](../../docs/cross-asset-trend-findings.md)) established
that a cross-asset trend book fills exactly that gap — every era positive, −0.11 correlation to SPY,
and **positive on average on the days the existing book loses most**. Blended at 20% it takes the ETF
track from Sharpe 0.82 to 0.97 and drawdown from −17.7% to −11.8%.

It comes with one hard condition: **futures only.** The same book implemented in margined ETFs
returns −1.5% excess over cash, and unlevered ETFs −1.3%. Leverage must be embedded in the contract,
not borrowed at BM+1.5%.

This is therefore the first feature to trade an asset class the execution engine does not yet
support. `LiveExecution` handles FX and `BasketExecution` handles stocks; futures need a third.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Place and reconcile futures positions safely (Priority: P1)

As the operator, I want a futures executor with the same guarantees as the existing two, so that a
new asset class does not mean new ways to lose money.

**Why this priority**: Nothing else can happen without it, and it is the part where mistakes are
expensive and irreversible.

**Independent Test**: Run a preview against the live account and confirm it computes target contracts
and places nothing; run a placement against a fake broker and confirm the guards fire.

**Acceptance Scenarios**:

1. **Given** a target contract count per market, **When** the executor runs in preview, **Then** it
   connects read-only, reports intended orders, and places nothing.
2. **Given** placement is armed, **When** the account is not a paper account, **Then** it refuses
   unless the live gate is explicitly set.
3. **Given** existing positions, **When** the executor runs again with an unchanged target, **Then**
   it places no orders — reconciliation is by contract identity, as for the other sleeves.
4. **Given** an order fails mid-batch, **Then** the executor attempts a best-effort unwind that never
   itself raises, and re-raises the original error telling the operator to verify positions.
5. **Given** a target that would exceed a per-order or total cap, **Then** it raises **before** any
   order is placed.

---

### User Story 2 - Compute the trend book's target positions (Priority: P2)

As the operator, I want target contract counts derived from the gated construction, so what runs is
what was tested.

**Why this priority**: The signal is settled; this is faithful transcription of it, and it must not
drift from the gate.

**Independent Test**: Feed a known price history and confirm the weights match the gate's
construction, and that integer rounding is applied and reported.

**Acceptance Scenarios**:

1. **Given** price history for the universe, **Then** signals are a 3-lookback ensemble (63/126/252d)
   and weights are inverse-vol across markets, matching the gate exactly.
2. **Given** computed weights and a risk base, **Then** target *contract counts* are integers, and the
   rounding error per market is reported — it is material at this size and must not be hidden.
3. **Given** a market whose rounded target is zero, **Then** that is reported rather than silently
   dropped.
4. **Given** any date, **Then** the signal uses only data available before that date.

---

### User Story 3 - Run it on schedule alongside the other sleeves (Priority: P3)

As the operator, I want the sleeve rebalanced monthly and watched like everything else, so it cannot
fail silently.

**Why this priority**: Completes the loop, and the existing healthcheck already proves the pattern.

**Acceptance Scenarios**:

1. **Given** the installer runs, **Then** a monthly trend rebalance is scheduled and appears in the
   loaded agent list.
2. **Given** a run completes, **Then** it writes a positions CSV like every other sleeve.
3. **Given** the sleeve has not written its CSV within its cadence plus grace, **Then** the
   healthcheck reports it overdue.

---

### Edge Cases

- **Contract roll.** Futures expire. A held position approaching expiry must be rolled to the next
  contract, and a roll must not be mistaken for a signal change.
- **Integer rounding at this size.** At a ~$200k risk base the smallest market rounds to ~1.5
  contracts. Rounding error is large and must be reported, not smoothed over.
- **No market-data subscription.** Without one, historical bars are unavailable — the A1 gate found
  7 daily bars on a VX front month. The sleeve cannot compute signals in that state and must fail
  clearly rather than trading on nothing.
- **Margin.** Futures consume margin. The executor must not push the account toward a margin call;
  available funds must be checked before placing.
- **A market with no position** (signal flat) is a valid state, not an error.
- **Partial fills** must leave the reported state honest, as with the other sleeves.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST place, reconcile, and unwind futures positions with the same guard set
  as the existing executors: preview by default, explicit confirmation to place, paper-account check
  with an explicit live gate, per-order cap enforced before any placement, reconciliation by contract
  identity, and a never-raising rollback.
- **FR-002**: Reconciliation MUST NOT trade when the target is unchanged.
- **FR-003**: Target positions MUST be computed by the construction the A2 gate validated —
  3-lookback ensemble, inverse-vol risk parity, vol target, monthly rebalance.
- **FR-004**: Targets MUST be whole contracts, and the rounding error per market MUST be reported.
- **FR-005**: The signal MUST use only information available before the date it is applied.
- **FR-006**: The system MUST roll positions before contract expiry, and a roll MUST NOT be treated
  as a change in signal.
- **FR-007**: The system MUST refuse to trade when price history is insufficient to compute the
  signal, rather than trading on a degraded signal.
- **FR-008**: The system MUST check available margin before placing and refuse if placement would
  breach a configured floor.
- **FR-009**: The sleeve MUST write a positions record on each applied run, consistent with the other
  sleeves.
- **FR-010**: The sleeve MUST be schedulable by the existing installer and watched by the existing
  healthcheck.
- **FR-011**: All position-sizing and signal logic MUST be unit-testable offline with no broker
  connection.
- **FR-012**: The universe MUST be the eight granularity-feasible markets identified by the gate, and
  changing it MUST be a deliberate, recorded decision rather than a silent edit.

### Key Entities

- **Market**: a futures contract series (e.g. micro Russell), with its multiplier, exchange, and the
  ETF proxy used to validate it.
- **Signal**: per-market trend direction in [−1, +1], from the lookback ensemble.
- **Target**: whole contracts per market, from signal × inverse-vol weight × risk base.
- **Roll**: replacing a near-expiry contract with the next, at unchanged signal.
- **Risk base**: the notional capital the vol target is computed against — 20% of the ETF track.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A preview against the live account produces target contracts for all eight markets and
  places nothing.
- **SC-002**: Re-running with an unchanged target places zero orders.
- **SC-003**: Reported rounding error per market is visible in every run.
- **SC-004**: The realised sleeve's correlation to the ETF basket can be measured from recorded data
  once enough history accrues, and compared against the gate's +0.06.
- **SC-005**: No run can place an order on a non-paper account without the explicit live gate.
- **SC-006**: The healthcheck reports the sleeve overdue if it misses its cadence.

## Assumptions

- **Reallocation, not addition.** The sleeve is funded by trimming the ETF sleeves ~20%, which is what
  the blend result measured. Adding it on top of an unchanged book would raise total portfolio risk
  and would not reproduce the measured drawdown improvement.
- **Risk base ~20% of the ETF track (~$200k).** At that size the worst market rounds to ~1.5
  contracts — coarse but workable. Below ~$150k the construction degrades badly.
- **The eight-market universe** (micro Russell, micro Dow, 2y and 5y notes, micro EUR and AUD, micro
  crude, corn) was selected for contract granularity and *outperformed* the full sixteen in the gate.
  That is a fortunate result, not a designed one, and it should be re-checked if the universe changes.
- **A market-data subscription is required** and is a prerequisite, not part of the build.
- **The signal evidence is ETF-proxy.** Futures track the same underlyings, but the implementation has
  not been tested on futures data. The first months of live data are the test.
- Futures financing is assumed at ~25bp against retail margin's ~218bp. That figure is an assumption;
  the realised basis is measurable once positions exist.

## Dependencies

- A CME/CBOT/NYMEX market-data subscription on the account. **Blocking** — without it there is no
  price history and no signal.
- The existing guard/reconcile/rollback pattern in `forex/run/execution.py` and `forex/run/basket.py`.
- The scheduling and healthcheck machinery from features 004.

## Out of Scope

- Replacing or retiring the FX book. It stays as the forward record.
- The full sixteen-market universe. Recorded as a future option if the sleeve grows.
- Any live-money deployment. This is the paper account, and Constitution IV governs.
