# Phase 0 Research: Standalone Long/Short Candidate Gates

**Date**: 2026-10-15. Four questions, all resolved by probing the actual sources rather than reasoning
about them — this program's own rule, and it earned its keep: three of the four answers were unwelcome
and two would have produced confidently wrong results.

---

## R1 — Is the free price source usable, and how deep?

**Decision**: fetch with explicit `period1`/`period2` plus `interval=1d`, read **`adjclose`**, and
**assert that the response's reported granularity is actually daily**. Cache one parquet per symbol,
exactly as `fred.py` does.

**Rationale**: the obvious call is a trap. Requesting `range=max&interval=1d` returns a response that
*claims* to be daily and is actually **monthly**:

| Symbol | `range=max&interval=1d` | `period1/period2&interval=1d` |
|---|---|---|
| IEF | **292 bars** from 2002-07-31 | **6,093 bars** from 2002-07-30 |
| SHY | 292 | 6,093 |
| TLT | 292 | 6,093 |
| TIP | 275 (from 2003-12-31) | — |
| HYG | 235 (from 2007-04-30) | — |

The `range=max` form silently coarsens the interval. Nothing errors. A daily strategy backtested on
292 monthly bars would have produced a plausible-looking number with no indication anything was wrong —
exactly the "free data source that silently changes shape" edge case the spec lists. The response
carries `meta.dataGranularity`, which reads `1d` on the correct call, so **the loader must assert on
that field**; it is the only cheap guard against silently receiving the wrong thing.

Usable depth, measured: **~24 years of daily history (2002→present)** for the Treasury ETFs, 2003 for
TIP, 2007 for HYG. Enough for a genuine era split on all three macro-spread candidates.

**Alternatives considered**:

- *`yfinance`.* Rejected: a new dependency wrapping the same endpoint, with its own breakage history,
  to save ~20 lines. One documented JSON shape with an asserted granularity field is more inspectable.
- *`range=max` for convenience.* Rejected on the measurement above. It is the trap, not the shortcut.
- *IBKR historical bars.* Rejected outright — FR-012. It would also reopen the Gateway, which is the
  thing that was just shut down.

---

## R2 — Can the existing financing model cost these candidates? (**Mostly no**)

**Decision**: **The repo's financing model does not cover a short equity leg, and the plan must not
pretend otherwise.** Use `DEBIT_SPREAD["USD"]` = **1.5% over benchmark** for a margined long, treat
futures legs as financed at ≈ risk-free, and for any **short ETF leg** report the result as an
**upper bound** with borrow cost excluded and stated as excluded.

**Rationale**: `forex/backtest/financing.py` is keyed by **currency** — `CREDIT_SPREAD` and
`DEBIT_SPREAD` map `USD`, `EUR`, `JPY`, … to spreads over benchmark, because it was built to cost
multi-currency *cash balances* for the FX book. A long/short in US ETFs has one currency and two
instruument legs, so:

| Leg type | Costable today? | With what |
|---|---|---|
| Margined USD long | **Yes** | `DEBIT_SPREAD["USD"]` = BM+1.5%, the published tier-1 rate |
| Futures long or short | **Yes** | ≈ risk-free, embedded in the basis — the survey's §2 insight |
| **Short ETF / stock** | **No** | Stock borrow is name-specific, time-varying, and **absent from this repo entirely** |

This is a real constraint and it reshapes the candidates:

- **A3 (2s10s)** is unaffected where it matters. Its *deployment* instrument is Treasury futures, both
  legs financed at ≈ risk-free. The ETF-proxy screen does involve a short leg, so the screen inherits
  the upper-bound caveat — which compounds the A2 lesson that an ETF screen cannot validate a futures
  strategy anyway.
- **B5 (TIPS breakeven)** and **B6 (credit)** as ETF pairs each need a short leg. Their verdicts
  therefore cannot be final as ETF pairs; a pass would mean "worth pricing properly in futures or with
  real borrow data", not "viable".
- **B4 (index basis)** is a futures-versus-cash trade by construction, so the short side is the
  futures leg and this is the one candidate where the financing question is naturally clean.

**Why not just assume a borrow rate**: a single assumed constant would be an invented number driving a
verdict, and this program's recorded failures are mostly invented or inherited numbers (the ~$5
subscription, the survivorship-inflated RSP premium, the "data is the blocker" futures diagnosis).
Reporting an explicit upper bound is honest and still decision-useful: if a candidate fails *even
without* borrow cost, it is dead with certainty, and three of these candidates are expected to fail
that way.

**Alternatives considered**: extending `financing.py` with an equity-borrow model — rejected as out of
scope and unfundable from free data; scraping borrow rates — no free historical source, and it would
be a data gate of its own.

---

## R3 — Does `distant_window()` give a usable era split here? (**Not with its default**)

**Decision**: reuse `validation.distant_window()` but **pass `holdout_years` explicitly per
candidate**, choosing roughly the midpoint of the available history. Do not rely on the default.

**Rationale**: the function splits at `index.min() + holdout_years`, default **3**:

```python
cutoff = idx.min() + pd.DateOffset(years=holdout_years)
distant = slice(0, n_distant)      # the first `holdout_years`
recent  = slice(n_distant, len(idx))
```

That default was sized for the FX sample. Against 24 years of ETF history it would make "distant"
2002–2005 and "recent" 2005–2026 — an 3-versus-21-year split, where the "distant" era is too short to
measure anything and the "recent" era averages across the regimes the split exists to separate. For a
2002–2026 history the honest split is near 2014, i.e. `holdout_years≈12`.

**Alternatives considered**: writing a new balanced-split helper — rejected, the existing function does
the job once parameterised, and a second splitter would be a place for the two to disagree. Using
`walk_forward()` instead — rejected for this purpose: walk-forward tests parameter stability over time,
whereas the requirement here (FR-004) is specifically *two temporally distant windows*, which is a
different question and the one that catches a dead-regime ghost.

---

## R4 — Close or adjusted close?

**Decision**: **adjusted close, always**, and the loader should not expose raw close as the default.

**Rationale**: every candidate here trades bond, TIPS or credit ETFs, which pay most of their total
return as distributions. SHY, IEF, TLT, TIP, HYG and LQD all distribute monthly. Using raw closes
would understate long-leg returns by roughly the entire yield — for a *carry-like* spread trade that is
not a small error, it is the signal. `adjclose` is present in the response (verified on IEF/SHY/TLT).

**Alternatives considered**: close plus a separately-fetched distribution series — strictly more work
for the same number, and another free-data dependency to gate.

---

## What the research changed about the plan

- The loader gained a **mandatory granularity assertion** (R1). Without it the feature's cheapest
  failure mode is a silent wrong answer, which is worse than no answer.
- Three candidates (**A3's screen, B5, B6**) now carry a **structural caveat** rather than a clean
  verdict path (R2). B4 became the cleanest of the six on financing, having started as the one most
  likely to die on economics.
- The era split is **parameterised per candidate** rather than defaulted (R3).
- No `NEEDS CLARIFICATION` remains.
