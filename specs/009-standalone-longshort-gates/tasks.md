# Tasks: Standalone Long/Short Candidate Gates

**Input**: Design documents from `/specs/009-standalone-longshort-gates/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/interfaces.md](./contracts/interfaces.md)

**Tests**: **REQUIRED** (Constitution III). Here they guard against a *silently wrong answer* rather
than a crash — which is this repo's actual failure mode, and research R1 found a live example before a
line was written. Test tasks precede their implementations.

**⚠️ OUT OF SCOPE — MUST NOT BE TOUCHED**: anything that connects to a broker or needs the IB Gateway
(FR-012); the paper track and launchd agents stopped on 2026-10-14; and any question already closed
with evidence (FR-016 — all FX factors, intraday, the momentum basket, the trend overlay, RSP vs SPY,
prediction markets, box spreads).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Create the six-row candidate register in `strategies/longshort_candidates.py` from [data-model.md](./data-model.md) §1 — plain data, one entry per candidate carrying `id`, `name`, `hypothesis`, `signal_series`, `screen_symbols`, `deploy_instrument`, `shortable_cleanly` and `kill_criterion`, so both gate scripts iterate the register instead of hardcoding six paths (`data_cache/` is already git-ignored, so no ignore task is needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ Blocks US1 and US3.** US2 needs only the loader.

> **This phase is where the harness cost honestly sits.** The spec's checklist flagged that US1's
> "afternoon" is really harness-plus-verdict; putting both shared pieces here rather than inside US1
> makes that visible instead of pretending the first verdict is as cheap as the later ones.

### Free price loader — tests first ⚠️ confirm they FAIL

- [ ] T002 [P] Write a failing test that a response reporting a **non-daily** granularity **raises**, rather than returning data — in `tests/test_yahoo.py`. This is the single most important test in the feature: research R1 measured `range=max&interval=1d` returning **292 monthly bars** for IEF while reporting itself as daily, against **6,093** real daily bars from `period1`/`period2`. Nothing errors in that case, so without this assertion the cheapest failure mode is a plausible number from the wrong bars
- [ ] T003 [P] Write a failing test that the loader returns **adjusted** closes and never raw closes — in `tests/test_yahoo.py` (research R4: every instrument here is a distributing bond/TIPS/credit ETF, so raw closes omit most of the return, which for a carry-like spread *is* the signal)
- [ ] T004 [P] Write a failing test for the cache contract — `force=False` reads an existing parquet, `force=True` refetches and rewrites, and a cached read performs **zero** client calls — in `tests/test_yahoo.py`
- [ ] T005 [P] Write a failing test that a failed fetch returns the cache when one exists and **raises** when none does, and never returns a silently short series — in `tests/test_yahoo.py`

### Free price loader — implementation

- [ ] T006 Implement `load_prices(symbol, cache_dir, force, client, start)` in `forex/data/yahoo.py`, shaped exactly like `forex/data/fred.py` (positional symbol, `cache_dir`, `force`, lazily-imported injectable client, one parquet per symbol), using **stdlib `urllib.request` only — no new dependency** and `period1`/`period2` with `interval=1d`, never `range=max`

### Gate evaluator — tests first ⚠️ confirm they FAIL

- [ ] T007 [P] Write a failing test that a series beating the benchmark in **one** window but losing in the other yields **`reject`**, never `pass` — in `tests/test_gate.py`. This is FR-004's dead-regime-ghost guard and the rule that makes a single good era worthless. **Also assert the window LABELLING**: `validation.distant_window()` returns `(recent, distant)` — recent **first**, which is counterintuitive for its name — so a test must pin which returned slice is the early era. Without it an inverted unpack mislabels every verdict's eras while every other test here still passes, because they check the rule rather than the labels
- [ ] T008 [P] Write a failing test that `borrow_excluded=True` can **never** yield `pass`, capping at `inconclusive` — in `tests/test_gate.py` (research R2: a result that assumes free shorting is not a result)
- [ ] T009 [P] Write a failing test that fewer than two windows yields `inconclusive` — in `tests/test_gate.py` (SC-003)
- [ ] T010 [P] Write a failing test that `holdout_years` is **required** and has no default — in `tests/test_gate.py` (research R3: `distant_window`'s own default of 3 is tuned to the FX sample and would split a 24-year history 3-versus-21, where the distant era is too short to measure and the recent era averages over the regimes the split exists to separate)
- [ ] T011 [P] Write a failing test that cost and financing are applied **before** any metric is computed, and that no public function accepts or returns a gross-of-cost series — in `tests/test_gate.py` (SC-004: there must be nowhere to put a gross figure). **Also assert that a missing or empty benchmark fails** rather than silently producing an absolute-performance verdict — FR-002 makes the comparator mandatory and nothing else checks it
- [ ] T012 [P] Write a failing test that `evaluate()` is pure — same inputs, same `GateVerdict`, no clock and no filesystem — in `tests/test_gate.py`

### Gate evaluator — implementation

- [ ] T013 Implement `evaluate()` plus the `GateVerdict` / `WindowResult` records in `forex/backtest/gate.py`, composing `portfolio.metrics()` and `validation.distant_window(index, holdout_years)` per [contracts/interfaces.md](./contracts/interfaces.md) §B — pure, no I/O, and reusing the existing helpers rather than reimplementing metrics or the split

### Feature-wide guard — the constraint nothing else checks

> Added by the 2026-10-15 `/speckit-analyze` pass, which found FR-012 and SC-005 had **zero**
> verifying tasks. Principle IV is NON-NEGOTIABLE and the plan asserts compliance ("creates no
> execution path"), but an assertion nobody checks is a promise, not a guarantee — and the realistic
> way it erodes is somebody reaching for an existing broker helper to fetch a price mid-implementation.

- [ ] T014 Write a test that **no module added by this feature imports a broker library or any execution path** — assert that `forex/data/yahoo.py`, `forex/backtest/gate.py`, `strategies/longshort_candidates.py`, `strategies/curve_spread.py`, `strategies/macro_spread.py` and both `scripts/gate_*.py` pull in neither `ib_async` nor `forex.run.execution` / `basket` / `futures` / `ibconnect` — in `tests/test_no_broker.py` (FR-012, SC-005). This makes the answer to "does this need the Gateway?" structural rather than remembered

**Checkpoint**: the harness exists and is tested offline. Nothing has been gated yet.

---

## Phase 3: User Story 1 — A verdict on the most promising candidate (Priority: P1) 🎯 MVP

**Goal**: an evidenced standalone verdict on the Treasury curve trade (A3).

**Independent Test**: run `scripts/gate_candidate.py --candidate A3` and read its per-window table and
verdict. Useful even if no other candidate is ever examined.

> **A3 is the best-placed of the six**: a genuine two-leg long/short, financing-efficient because the
> deployment instrument is futures, decades of free signal history, and the one signal *shape* with a
> track record here — slow and non-price-predictive, like carry, unlike every intraday idea that died.

### Tests for User Story 1 ⚠️ write first, confirm they FAIL

- [ ] T015 [P] [US1] Write failing tests for the 2s10s signal and the two-leg weights it implies — sign, scale, and that a flat curve produces no position — in `tests/test_curve_spread.py`
- [ ] T016 [P] [US1] Write a failing **causality** test: the signal at date *t* is unchanged when all data after *t* is truncated — in `tests/test_curve_spread.py` (Constitution II, FR-015)

### Implementation for User Story 1

- [ ] T017 [US1] Implement the 2s10s signal and two-leg weight construction in `strategies/curve_spread.py` — plain functions following the `strategies/trend_book.py` precedent, **not** a `Strategy` subclass (the contract returns *currency* weights and does not fit; Constitution I also forbids adding a registry)
- [ ] T018 [US1] Implement `scripts/gate_candidate.py` per [contracts/interfaces.md](./contracts/interfaces.md) §D — loads cached data, computes net returns, calls `gate.evaluate()`, prints the verdict and per-window table; written so the other candidates reuse it rather than each getting a script
- [ ] T019 [US1] Fetch and cache the inputs (the 2y and 10y yield series, plus the proxy ETF adjusted closes) and run the A3 gate with `holdout_years` set to roughly the midpoint of available history (~12 for a 2002-start series), against a named benchmark. **Record the chosen `holdout_years` and the resulting window boundaries** — it is a per-candidate judgement (research R3 argues against a fixed default), so a verdict is only reproducible if the split that produced it is written down
- [ ] T020 [US1] Record the A3 verdict, stating explicitly that the ETF-proxy screen carries `borrow_excluded=True` and therefore **caps at `inconclusive`**, and that deployment would require Treasury futures — the A2 gate's conclusion was "viable **only** in futures; every ETF implementation loses to cash", so a positive screen informs the futures question rather than answering it (FR-011)

**Checkpoint**: one real verdict exists, with its limits stated rather than implied.

---

## Phase 4: User Story 2 — Kill the data-blocked candidates before building (Priority: P2)

**Goal**: each of the other five ends as `testable` or `dead`, cheaply, before any modelling.

**Independent Test**: run `scripts/gate_data_feasibility.py` and read the table. Delivers value on its
own — it is pure subtraction.

> **This is the highest-value-per-hour work in the feature**, and it is genuinely independent of US1 —
> see Dependencies. Filter 1 of this repo's method exists for exactly this: *free data, or it does not
> get built.*

### Tests for User Story 2 ⚠️ write first, confirm they FAIL

- [ ] T021 [P] [US2] Write failing tests for the feasibility record logic — `testable` / `dead_on_data` / `dead_on_economics` are terminal, each carries the source checked and the usable span, and probes are injected so the test performs no network I/O — in `tests/test_data_feasibility.py`

### Implementation for User Story 2

- [ ] T022 [US2] Implement `scripts/gate_data_feasibility.py` per [contracts/interfaces.md](./contracts/interfaces.md) §C — iterate the register from T001, one cheap probe per candidate, emit the status table, and **build nothing** (FR-005)
- [ ] T023 [P] [US2] Run the **B4** check: compare the index futures basis against round-trip commission at retail scale. Expected `dead_on_economics` — and this is the one candidate where the financing question is naturally clean, since its short leg is the future (research R2)
- [ ] T024 [P] [US2] Run the **B2** probe: is free historical CEF discount/NAV data obtainable at all? Expected `dead_on_data` — this is the binding question and it is answered before any model
- [ ] T025 [P] [US2] Run the **B3** probe: is bulk earnings-date and surprise history obtainable free? Expected `dead_on_data`
- [ ] T026 [P] [US2] Run the **B5 and B6** probes: confirm the FRED spread series and the proxy ETF spans, recording the **granularity the source reported** rather than the one requested (research R1)
- [ ] T027 [US2] Record all five feasibility results. **A candidate returning `testable` when it was expected dead is a finding to write down, not a problem** — the expectation in SC-007 is a prediction, not a target

**Checkpoint**: the remaining work is known and bounded. Expect three of the five to be closed here.

---

## Phase 5: User Story 3 — Verdicts on whatever survived (Priority: P3)

**Goal**: every survivor gets the same treatment A3 got.

**Independent Test**: each survivor has a findings section with the same structure as A3's.

> **Set expectations honestly**: B5 and B6 both need a short ETF leg, which this repo cannot cost
> (research R2). So their realistic outcomes are a **definitive kill** or an honest *"needs borrow
> data"* — `pass` is not available to them, and the tasks below should not be read as hoping for one. A
> definitive kill is still a good afternoon's work: it closes a question.

### Tests for User Story 3 ⚠️ write first, confirm they FAIL

- [ ] T028 [P] [US3] Write failing tests for the shared two-leg macro-spread signal — applied to both the breakeven and the credit series, including the flat-spread no-position case — in `tests/test_macro_spread.py`

### Implementation for User Story 3

- [ ] T029 [US3] Implement `strategies/macro_spread.py` as **one** module serving both B5 and B6, since both are the same shape — a two-leg spread driven by a FRED-published spread series — rather than two near-identical modules
- [ ] T030 [US3] Run the **B5** (TIPS breakeven) gate and record its verdict, with `borrow_excluded=True` stated and the verdict capped at `inconclusive` accordingly
- [ ] T031 [US3] Run the **B6** (credit spread) gate and record its verdict, noting explicitly that its *original* gate asked "does it add anything the basket does not already have?" — the portfolio-contribution question this feature exists to replace — so this is a genuine first standalone test rather than a repeat
- [ ] T032 [US3] **Only if B2, B3 or B4 survived T023/T024/T025**: gate the survivor properly rather than letting it fall through. **B4 is the likeliest surprise survivor** — research R2 found it the cleanest of the six on financing, since its short leg is the future — and SC-001 requires all six to end with a verdict, so a B4 that is *not* killed on economics needs a real gate here. For B2/B3 specifically, run the equal-weight buy-and-hold null of the same names **first**, not last. That null is what killed the momentum basket, and any universe must be built point-in-time — a prior assessment inflated a real +3.2pp/yr effect roughly **4×** through the author's own universe selection

**Checkpoint**: all six candidates resolved.

---

## Phase 6: Polish & Validation

- [ ] T033 Run `.venv/bin/python -m pytest -q` and `ruff check .`; confirm green and no new violations
- [ ] T034 Run [quickstart.md](./quickstart.md) steps 1–4, including the **median-bar-gap check** — a median gap of 1 day proves the granularity guard works; a median near 30 means monthly bars got through and no verdict can be trusted until the loader is fixed
- [ ] T035 Author `docs/standalone-longshort-findings.md` as **one** document with a section per candidate, each carrying the hypothesis, the verdict, the per-window numbers beside the benchmark, the cost and financing basis including whether borrow was excluded, **the `holdout_years` and window boundaries used**, and the reasoning — each rejection reproducible from its section alone (FR-009)
- [ ] T036 Update the backlog rows for all six candidates in `specs/000-baseline/baseline.md` to their resolved state, and update `docs/investable-universe-survey.md` §5 so its Tier A/B table no longer shows these as un-gated
- [ ] T037 Commit and push spec, plan, tasks, code and findings (Constitution V — planning state that exists on one machine does not exist)

---

## Dependencies & Execution Order

```text
Phase 1 (register)
   └─> Phase 2 (loader + evaluator) ── the harness; blocks US1 and US3
        ├─> US1 (P1)  A3 verdict ── MVP
        ├─> US2 (P2)  the cull ── needs only the LOADER, not the evaluator
        │      └─> US3 (P3) scope is determined by US2's results
        └─> Phase 6 (validation + the record)
```

- **US2 is genuinely independent of US1, and cheaper.** The spec ordered US1 first because it delivers
  a real verdict, not because of a technical dependency. **If the goal is to spend the least time
  before knowing how much work remains, run US2 first** — it needs only the loader and it is expected
  to close three candidates in an afternoon.
- **US3's scope is unknown until US2 runs**, and may be nearly empty.
- US1 and US3 both need the full Phase 2.

### Parallel Opportunities

- T002–T005 (loader tests) and T007–T012 (evaluator tests) are all parallel within their files.
- T023–T026 (the four probes) are independent of each other and parallel.
- T015–T016 (A3 tests) are parallel.
- Once Phase 2 is done, US1 and US2 can proceed concurrently.

---

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + US1.** That is one evidenced verdict on the candidate with the only real
prior, plus a harness the other five reuse.

**Then US2**, because it is pure subtraction and bounds everything that follows.

**Then US3**, whose size US2 determines.

> **The success criterion that most constrains this work is SC-007**: at least three of six rejected on
> data or economics within hours each, and *a feature where everything "needs more investigation" has
> failed*. The tasks are deliberately arranged so the cheap kills are reachable early — T023–T026 are
> four probes that can close three candidates without a line of modelling code.

> **And the one that most constrains the implementation is SC-004**: no figure is reported gross of
> cost and financing. T011 enforces it structurally by leaving nowhere to put a gross number, and T008
> enforces the honest-limit rule that follows from it. Neither should be weakened to make another test
> pass.

## Notes

- `[P]` = different file or independent content, no dependency on an incomplete task.
- Verify each test fails before implementing; a test that passes immediately is testing the wrong thing.
- Nothing in this feature connects to a broker, needs the Gateway, or places an order.
- A candidate is not finished when its number is computed — it is finished when its verdict is written
  down. The rejections are the most valuable output here.
