# Feature Specification: VIX Carry Satellite Sleeve

**Feature Branch**: none — work proceeds on `main`; `specs/007-vix-carry-sleeve/` is the feature identity

**Created**: 2026-08-19

**Status**: Draft

**Input**: Backlog — VIX carry as a ≤10% satellite sleeve, per the A1 gate

## Context

The A1 gate ([`vix-carry-findings.md`](../../docs/vix-carry-findings.md)) gave a **conditional pass**:
the volatility curve is in contango 92% of days, gating a short-vol position on `VIX3M > VIX` improves
every era on both instruments, and a ≤10% sleeve lifts the ETF track from Sharpe 0.88 to 0.97 with
slightly better drawdown.

Two conditions came with it, and they shape this spec more than the upside does:

1. **It is not a diversifier.** +0.58 correlation to SPY, and on the ETF book's 20 worst days it
   averages −1.89% and is positive only 5% of the time. This is return enhancement bolted onto equity
   beta, sized small enough that its tail does not dominate. It cannot substitute for the trend sleeve.
2. **The instrument has never seen the event that defines the strategy.** SVXY moved from −1x to −0.5x
   on 2018-02-28, the week *after* the blowup that terminated XIV; its predecessor lost 83% in a single
   day. The contango gate would have been out for that day but was fully *in* for Brexit (−26.4%). The
   gate is a real improvement, **not** a tail guard.

It does pass the financing filter cleanly — a long-only cash ETF, no margin, no borrow — which is why
it is worth anything at all at retail terms.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Decide whether to be in the trade today (Priority: P1)

As the operator, I want the position decided by the gated rule the A1 work validated, so what runs is
what was tested.

**Independent Test**: Feed known VIX/VIX3M values and confirm the target is the allocation in contango
and zero in backwardation.

**Acceptance Scenarios**:

1. **Given** VIX3M above VIX, **When** the sleeve runs, **Then** the target is the full allocation.
2. **Given** VIX3M at or below VIX, **Then** the target is zero — the sleeve stands aside.
3. **Given** the term structure from a prior session, **Then** the decision uses only data available
   before the position is taken.
4. **Given** stale data, **Then** the sleeve refuses to act rather than trading on an old signal.

---

### User Story 2 - Hold or flatten safely (Priority: P2)

As the operator, I want positions placed with the same guards as every other sleeve, and no trading
when already in the right state.

**Acceptance Scenarios**:

1. **Given** contango and no position, **Then** it buys to the allocation.
2. **Given** backwardation and a position, **Then** it sells the whole position.
3. **Given** contango and a correct position already held, **Then** it places **no orders**.
4. **Given** a non-paper account, **Then** placement is refused without the explicit live gate.
5. **Given** a single-symbol sleeve, **Then** the per-order cap does not make placement impossible —
   the defect that made the cash sleeve unplaceable until it was fixed.

---

### User Story 3 - Run daily and be watched (Priority: P3)

As the operator, I want the sleeve evaluated every trading day and covered by the healthcheck.

**Acceptance Scenarios**:

1. **Given** the installer runs, **Then** a daily agent is scheduled before the US open.
2. **Given** an applied run, **Then** a positions record is written like every other sleeve.
3. **Given** the sleeve going quiet, **Then** the healthcheck reports it overdue.

---

### Edge Cases

- **A signal flip on a day the market is closed** — the sleeve must be a no-op, not an error.
- **Data published with a lag.** The term-structure series are daily closes posted after the session;
  the decision must use the most recent *available* value and know how old it is.
- **A flip while already flat, or already held** — both are no-ops and must place nothing.
- **The allocation exceeding available cash** — this sleeve is cash-funded and must not create margin.
- **Repeated flips in a volatile week** — turnover is a real cost and must be visible in the record.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The target MUST be the full allocation when the term structure is in contango and zero
  otherwise, using the rule the A1 gate validated.
- **FR-002**: The decision MUST use only data available before the position is taken.
- **FR-003**: The sleeve MUST refuse to act when the term-structure data is older than a stated
  tolerance, rather than trading on a stale signal.
- **FR-004**: The sleeve MUST place no orders when the held position already matches the target.
- **FR-005**: Placement MUST carry the same guards as the other sleeves: preview by default, explicit
  confirmation, paper-account check with an explicit live gate, and a never-raising unwind.
- **FR-006**: A single-symbol allocation MUST NOT be blocked by the per-order cap.
- **FR-007**: The sleeve MUST be cash-funded and MUST NOT borrow on margin.
- **FR-008**: Each applied run MUST write a positions record consistent with the other sleeves.
- **FR-009**: The sleeve MUST be schedulable daily and covered by the healthcheck.
- **FR-010**: The signal logic MUST be unit-testable offline with no broker and no network.
- **FR-011**: Every run MUST report the term-structure values behind its decision, so a surprising
  position can be explained without re-deriving it.

### Key Entities

- **Term structure**: near and three-month volatility indices; contango when the longer exceeds the nearer.
- **Signal**: in or out — this sleeve has no partial position.
- **Allocation**: the cash amount held when in the trade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On any day, the operator can see the term-structure values and why the sleeve is in or out.
- **SC-002**: A run with an unchanged decision places zero orders.
- **SC-003**: The sleeve never holds a position while the curve is in backwardation, beyond one
  trading day's execution lag.
- **SC-004**: The sleeve never uses margin.
- **SC-005**: Realised flips per year can be counted from the record and compared with the ~5–15
  expected from the gate.

## Assumptions

- **SVXY is the instrument**, at its current −0.5x leverage. It is a long-only cash ETF and therefore
  financing-clean, which is the entire reason this is viable at retail terms.
- **A one-session execution lag** exists that the gate did not model: it used the prior close's term
  structure against the same day's return, whereas live the position is taken at the next open. The
  effect is small for a signal that flips ~5–15 times a year, but it is a real difference and the
  realised record is what settles it.
- **Sizing is set at deployment**, not in code, as with every other sleeve. The gate supports up to
  10% of the ETF track; the tail argues for the lower end.
- The term-structure indices are available from the existing free data source with the existing key.

## Dependencies

- Free daily volatility indices (near-term and three-month).
- `BasketExecution` for placement, as the cash and income sleeves already use.
- Scheduling and healthcheck machinery from feature 004.

## Out of Scope

- Any leveraged or short position in a volatility ETP. Long SVXY only — shorting VXX would require
  borrow, which reintroduces the financing problem this sleeve exists to avoid.
- Options-based volatility strategies. The A1 gate found put-writing to be the same trade in different
  clothing, with a worse tail.
- Treating this as a diversifier. It is not, and it does not reduce the book's need for the trend sleeve.
