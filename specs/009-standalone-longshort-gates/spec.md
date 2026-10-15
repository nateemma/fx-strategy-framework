# Feature Specification: Standalone Long/Short Candidate Gates

**Feature Branch**: `009-standalone-longshort-gates`

**Created**: 2026-10-15

**Status**: Draft

**Input**: Operator question — are there simpler strategies worth investigating on IBKR: plain
long/short, not sleeves and not anti-correlated portfolio construction? Candidates are Tier A/B of
[`docs/investable-universe-survey.md`](../../docs/investable-universe-survey.md) §5, none of which was
ever gated.

## Why this exists

Six candidates were ranked in August 2026 and never tested. The reason they were never tested is
itself the point: they were ranked by **how much they would add to the existing ETF book**, and
Constitution 1.1.0 later corrected exactly that habit —

> **A candidate MUST first be judged standalone: would this be worth running on its own capital?**
> […] Judging a candidate primarily by "does adding X% improve the current book" anchors every idea
> to what is already deployed, biases toward small incremental satellites, and quietly makes the
> existing book the thing being optimised rather than the question being asked.

So this is not a re-run of a closed search. It is the first application of the standalone bar to a set
of candidates that were shelved under the old one. **B6 is the clearest case**: its recorded gate was
literally *"Does it add anything the basket does not already have?"* — the exact question being
rejected here.

The paper track was stopped on 2026-10-14 and the program is not being resumed. This feature buys
**answers, not infrastructure**: an afternoon per candidate, a written verdict either way, and nothing
that needs a broker.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A verdict on the most promising candidate (Priority: P1)

The operator spends an afternoon and learns whether the Treasury curve trade (A3) is worth anything on
its own capital — with the answer written down well enough that it stays answered.

**Why this priority**: A3 is the best-placed of the six. It is a genuine two-leg long/short, it is
financing-efficient because the deployment instrument is futures, its signal data is free and decades
deep, and it is the one signal *shape* with a track record in this repo — slow and
non-price-predictive, like carry, unlike every intraday idea that died. Doing it first also builds the
small amount of shared machinery (a free price loader, the era-split and cost harness) that every
later candidate reuses, so the second verdict is cheaper than the first.

**Independent Test**: Run the A3 gate end to end and read its findings doc. It delivers a standalone
pass/reject with evidence, and is useful even if no other candidate is ever examined.

**Acceptance Scenarios**:

1. **Given** free yield-curve history and ETF proxy prices, **When** the A3 gate runs, **Then** it
   reports risk-adjusted performance net of cost and financing, in at least two temporally distant
   windows, against a stated benchmark.
2. **Given** a result that is positive on full history but absent in one of the two windows, **When**
   the verdict is written, **Then** it is a **reject** — a single-window edge is a dead-regime ghost.
3. **Given** a positive ETF-proxy screen, **When** the verdict is written, **Then** it states
   explicitly that deployment would require a futures path and is therefore blocked on futures
   history, rather than reading as deployable.
4. **Given** any verdict, **When** it is recorded, **Then** the reasoning and the numbers are in a
   findings doc and the backlog entry is updated.

---

### User Story 2 - Kill the data-blocked candidates before building anything (Priority: P2)

The operator learns, cheaply and early, which of the remaining five candidates cannot be tested at all
because the data does not exist for free — and stops thinking about them.

**Why this priority**: This is the highest-value-per-hour work in the feature and it is pure
subtraction. Two candidates (CEF discount/NAV history, bulk earnings-surprise history) are expected to
die here, and a third (index basis) can likely be killed on economics in about an hour. Filter 1 of
this repo's method exists precisely for this: *free data, or it does not get built*. Doing the cull
before any modelling is what keeps the whole exercise to afternoons.

**Independent Test**: Run the feasibility spike for each of the five and read the resulting table. Each
candidate ends as *testable* or *dead, because <specific missing data>*. Valuable on its own even if no
survivor is then modelled.

**Acceptance Scenarios**:

1. **Given** a candidate whose required history is not obtainable free, **When** the spike runs,
   **Then** it is recorded as rejected on data availability, naming what was missing and where it was
   looked for, and no model is built for it.
2. **Given** a candidate whose data is obtainable, **When** the spike runs, **Then** it is recorded as
   testable with the source and the usable history span noted.
3. **Given** a candidate that is cheap to kill on economics rather than data, **When** the spike runs,
   **Then** the economic check is enough and no full model is built.
4. **Given** any spike, **When** it finishes, **Then** it has consumed hours rather than days.

---

### User Story 3 - Verdicts on whatever survived (Priority: P3)

Each candidate that cleared the data gate gets the same standalone treatment A3 got, reusing the same
harness.

**Why this priority**: Last because its size is unknown until Story 2 runs, and it may be empty. If the
expectation holds, this is two macro spreads (TIPS breakeven, credit) and possibly nothing else.

**Independent Test**: Each surviving candidate produces a findings doc with the same structure as A3's.

**Acceptance Scenarios**:

1. **Given** a surviving candidate, **When** its gate runs, **Then** it is judged on the same standalone
   bar, era split, and cost-and-financing basis as A3 — not on what it adds to any portfolio.
2. **Given** a cross-sectional long-only candidate, **When** it is judged, **Then** it is compared
   against equal-weight buy-and-hold of the same names, and that comparison is run **before** any
   fancier construction.
3. **Given** all candidates resolved, **When** the feature closes, **Then** every one of the six has a
   recorded verdict and none is left in an ambiguous state.

---

### Edge Cases

- **Positive gross, negative net.** The documented way strategies die here: the FX book went from
  Sharpe 1.15 to 0.17 on financing alone. A long/short in cash instruments finances *both* legs
  (~2%/yr of gross, longs credited below benchmark and shorts charged above). Any candidate reported
  gross-of-cost is not a result.
- **Passes full history, fails the era split.** A dead-regime ghost. Must reject.
- **Beats a cap-weighted benchmark but loses to equal-weight of the same names.** This killed the
  momentum basket and must be the first comparison for any cross-sectional idea, not the last.
- **Survivorship bias in a constructed universe.** A prior assessment inflated a real +3.2pp/yr effect
  roughly **4×** through the author's own universe selection. Any CEF or earnings universe must be
  built point-in-time or the result is void.
- **An ETF-proxy screen that cannot be deployed as screened.** The cross-asset trend gate concluded
  "viable **only** in futures — every ETF implementation loses to cash". A proxy screen informs; it
  does not validate.
- **A free data source that silently truncates or changes shape.** A short or partial history that
  looks complete would produce a confident wrong answer.
- **A candidate that is neither clearly alive nor clearly dead.** It must still be written up as
  inconclusive *with the reason*, rather than left open — an unresolved candidate is how a closed
  question gets relitigated.

## Requirements *(mandatory)*

### Functional Requirements

**The bar**

- **FR-001**: Each candidate MUST be judged on whether it would be worth running **on its own
  capital**. Contribution to the existing ETF book MUST NOT be the criterion, and MUST NOT be the
  reason for a rejection.
- **FR-002**: Each candidate MUST be compared against a stated, simpler alternative — at minimum
  holding cash at the risk-free rate, and for cross-sectional candidates equal-weight buy-and-hold of
  the same names. Beating nothing is not a pass.
- **FR-003**: Every reported performance figure MUST be net of trading cost **and** net of the holding
  and financing cost implied by its instrument. Gross-of-cost figures MUST NOT be reported as results.
- **FR-004**: Each candidate MUST be evaluated across at least **two temporally distant windows**, and
  an edge appearing in only one MUST be rejected.

**Cheap gates first**

- **FR-005**: Each candidate MUST pass a data-feasibility check **before** any modelling, and a
  candidate whose required history is not obtainable free MUST be rejected at that point without
  further work.
- **FR-006**: A candidate that can be killed on economics with an order-of-magnitude check MUST be
  killed that way rather than modelled.
- **FR-007**: Each candidate MUST have a stated kill criterion that can be evaluated within hours.

**The record**

- **FR-008**: Each of the six candidates MUST end with a written verdict — pass, reject, or
  inconclusive — carrying the evidence and the reasoning, not just the conclusion.
- **FR-009**: Rejections MUST record what was measured and why it failed, in enough detail that the
  question stays closed without being re-run.
- **FR-010**: The backlog entry for each candidate MUST be updated to its resolved state.
- **FR-011**: Where a candidate's screen instrument differs from its deployable instrument, the verdict
  MUST say so and MUST NOT present the screen as a deployable result.

**Constraints**

- **FR-012**: Nothing in this feature may connect to a broker, require the IB Gateway, or place an
  order. The paper track is stopped and stays stopped (Constitution IV).
- **FR-013**: All data MUST come from free sources, and MUST be cached locally so a verdict can be
  reproduced without refetching.
- **FR-014**: Analysis logic MUST be testable offline with no network — the suite stays hermetic
  (Constitution III).
- **FR-015**: Point-in-time discipline MUST hold wherever a universe or a signal is constructed: no
  instrument may be selected using information unavailable at the time (Constitution II).
- **FR-016**: Questions already closed with evidence MUST NOT be re-opened: all FX factors
  (carry/value/slope/skew/regime/NLP/learned vol), intraday variants, the momentum basket on IBKR
  stocks and crypto, the per-holding trend overlay, RSP vs SPY, prediction markets, and box spreads.

### Key Entities

- **Candidate**: one of the six, with its survey ID (A3, B2, B3, B4, B5, B6), its hypothesis, the
  instruments that would screen it, the instruments that would deploy it, and its kill criterion.
- **Data-feasibility verdict**: testable / dead-on-data, with the source checked and the usable history
  span.
- **Standalone verdict**: pass / reject / inconclusive, with net-of-cost risk-adjusted performance per
  window, the benchmark it was measured against, and the reasoning.
- **Era split**: the two or more temporally distant windows a candidate was measured in, and its result
  in each.
- **Findings record**: the durable document per candidate, plus its backlog entry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **All six** candidates end with a recorded verdict. Zero are left in an ambiguous or
  in-progress state.
- **SC-002**: No candidate consumes more than **one working day** before producing either a verdict or
  an explicit kill.
- **SC-003**: Every candidate that survives its data gate is reported in **at least two** temporally
  distant windows. Zero single-window verdicts.
- **SC-004**: **Zero** performance figures are reported gross of cost and financing.
- **SC-005**: **Zero** broker connections are required at any point, and the paper track remains
  stopped throughout.
- **SC-006**: Every rejection is reproducible from its findings doc alone — a reader can see what was
  measured and why it failed without re-running anything.
- **SC-007**: At least **three** of the six are expected to be rejected on data availability or
  economics within hours each. A feature where everything "needs more investigation" has failed.

## Assumptions

- **The standalone bar is "beats the simpler alternative, net, in both eras."** No absolute Sharpe
  threshold is imposed, because the repo's own practice is comparative: the momentum basket died by
  losing to equal-weight of its own names, and RSP died by losing to SPY. A candidate that cannot beat
  holding T-bills or holding the same names passively is a reject regardless of its absolute number.
- **Free data means FRED plus a free equity/ETF price source.** FRED covers the macro signals (curve,
  breakevens, credit spreads) with decades of history and the key is already configured. Equity and ETF
  prices come from a free public source; prior equity work in this repo used one successfully, though
  only through throwaway scripts, so a reusable cached loader is the single piece of shared
  infrastructure this feature needs.
- **An afternoon per candidate is the budget**, and the kill criteria exist to enforce it. The operator
  has stopped pursuing the program; this is a bounded look at shelved ideas, not a restart.
- **Expected outcome is mostly rejections.** B2 and B3 are expected to die on data, B4 on economics.
  That is a successful outcome, not a failed one — the value is in closing them with evidence rather
  than leaving them as perpetual maybes.
- **Nothing here deploys.** A pass means "worth a real build later", not "trade it". Going live remains
  a separate gated decision and this feature creates no execution path.
- Out of scope: paid data (Databento and the futures-history problem remain unresolved and block the
  deployment path for any futures candidate), resuming the paper track, and any change to the
  deployed-but-now-stopped sleeves.
