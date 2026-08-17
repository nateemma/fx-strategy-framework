# Baseline — FX Strategy Framework

**Status page. Updated 2026-08-16.** At-a-glance view of what exists, what is running, what is in
flight, and what remains. Written when the project migrated from Superpowers to Spec Kit; it
consolidates the former `planning/`, `docs/`, and `docs/superpowers/{plans,specs}` trees into one
source of truth; the superseded ones now live under `docs/archive/`.

**Where the code disagrees with a document, the code wins.** Discrepancies found during this
migration are listed explicitly in [Known discrepancies](#known-discrepancies) rather than silently
resolved.

---

## What this project does

A strategy-agnostic research framework for systematic **FX** trading, plus a strategy library built
on it, plus a live-execution stack running both on an IBKR **paper** account.

The framework's contract with a strategy is one atom: **point-in-time data → target currency
weights**. The same `Strategy` object is driven by backtest, walk-forward, a lookahead-bias check,
and hyperopt, so signal logic cannot drift between research and execution. Two packages, one
dependency direction: `strategies → forex`, never the reverse.

Full design reference: `ARCHITECTURE.md`. Results and usage: `README.md`.

---

## Completed

### Framework (`forex/`)

| Piece | Code | State |
|---|---|---|
| `Strategy` contract + discovery | `forex/core/strategy.py`, `core/discovery.py`, `core/compose.py` | Done. Add a strategy by dropping a file; no registry. |
| Point-in-time `DataView` | `forex/core/dataview.py` | Done. `truncate` makes causality structural. |
| Backtest + metrics | `forex/backtest/` | Done. Vectorised, carry accrual framework-side. |
| Walk-forward | `forex/backtest/`, `forex/run/walkforward.py` | Done. |
| Lookahead check | `forex/diagnostics/` | Done. `forex causal-check`. |
| Hyperopt | `forex/run/hyperopt.py` | Done, incl. parallel + progress. |
| Config tiers | `forex/core/config.py` (RunConfig/EnvConfig) | Done. Secrets never in versioned config. |
| Data layer | `forex/data/` (FRED, IBKR spot, CFTC COT) | Done. |
| CLI | `forex/cli.py` | Done. Six modes. |

### Strategy library (`strategies/`)

22 strategies. The deployable book is **`carry_cot_mom`** — risk-parity blend of carry + CFTC COT
positioning + carry-momentum over the deliverable EM-inclusive universe (G10 + MXN/ZAR/PLN/HUF/CZK/ILS).
Walk-forward **Sharpe 1.15, Calmar 1.03, maxDD −2.9%**.

**The factor search is converged and closed** (`docs/strategy-research-backlog.md` is the decision
log). The rule it converged on: carry is the dominant axis, and additional edge comes *only* from
signals orthogonal to carry.

- **In the book:** carry, COT positioning (corr 0.09), carry-momentum (corr 0.03).
- **Rejected as carry-redundant:** value, yield-curve slope, skewness.
- **Rejected as priced/efficient:** regime conditioning, central-bank NLP, all intraday variants.
- **Rejected as documented negatives (kept for reproducibility):** learned vol forecasters
  (HAR / cross-asset / GBM) all lose to a one-parameter EWMA; the carry-drawdown crash overlay loses
  to the static blend.

Do not relitigate these without new *data*; a better model on the same inputs was tested and lost.

### Execution stack

| Piece | Code | State |
|---|---|---|
| FX executor | `forex/run/execution.py` (`LiveExecution`) | Done, paper-validated. Five guards + auto-unwind. |
| ETF executor | `forex/run/basket.py` (`BasketExecution`) | Done. Long-only Stock/SMART; reconciles by conId. |
| Weights | `forex/run/basket_weights.py` | Done, pure + unit-tested. |
| Per-sleeve tracking | `forex/run/basket_track.py` | Done. |
| FX book value | `forex/run/fxbook.py` | Done (2026-08-16). Reads legs + P&L from cash, not positions. |
| FX-only reporting | `forex/run/fxtrack.py` | Done (2026-08-16). Spec `001-fx-only-reporting`; 32 tests. |
| Financing diagnosis | `forex/run/financing.py` | Done (2026-08-16). Spec `002-financing-spread`; 17 tests. |
| Connect-with-retry | `forex/run/ibconnect.py` | Done. Rides through Gateway auto-restart. |
| Scheduling | `scripts/install_schedules.sh` | Partially done — see In flight. |

### Live paper track (account DUQ218063, IB Gateway port 4002)

Running since **2026-07-17**. NAV ~1,005k from 994k at inception.

| Sleeve | Runner | Deployed | Holding |
|---|---|---|---|
| FX book `carry_cot_mom` | `scripts/monthly_paper_rebalance.sh` | Yes | 14 currency legs (cash) |
| Risk-parity basket | `scripts/basket_rebalance.py` | Yes | SPY/TLT/IEF/GLD/DBC, ~298k |
| Treasury bond ladder | `scripts/bond_ladder.py` | Yes | IBTG–IBTL, ~300k |
| Income sleeve | `scripts/income_sleeve.py` | Yes | BIZD/JEPI, ~298k |
| Cash sleeve (SGOV) | `scripts/cash_sleeve.py` | **No** | — built, never run |

**The ETF sleeves are ~90% of NAV**, so whole-account numbers measure the sleeves rather than
`carry_cot_mom`. `scripts/track_report.py` now reports the two separately — but FX statistics are
gated until 20 observations accumulate, and there is currently one.

---

## In flight

1. **FX-only performance reporting — BUILT 2026-08-16, awaiting data.**
   `scripts/track_report.py` now reports the FX book separately (spec `001-fx-only-reporting`).
   Statistics are gated at 20 observations and only one FX-bearing snapshot exists, so the report
   currently runs in levels-only mode. First meaningful reading is several weeks out.
2. **Scheduling is partial.** launchd runs the monthly FX rebalance, the quarterly basket rebalance,
   and the daily NAV snapshot. The bond-ladder, income, and cash sleeves have no schedule.
3. **Financing drag — CONFIRMED against IBKR's published rates.** The book pays its carry rather than
   earning it. Verified 2026-08-16 against IBKR's published tiers: every leg untouched by the recent
   rebalance agrees on a ~13-day accrual window to within 10%, so the paper account reproduces the real
   schedule rather than simulating something cruder. Benchmark carry **+0.21%/yr** becomes a realised
   **−1.96%/yr**; financing costs **−2.18% of gross per year** against a ~3%/yr unlevered expectation.
   Full record: [`docs/financing-spread-findings.md`](../../docs/financing-spread-findings.md).
4. **The 2026-08-01 monthly rebalance silently failed** on a stale `~/Documents/forex` path after the
   repo moved to `~/projects/forex`. The plists were fixed the same day but **the fix has not been
   exercised by launchd** — the 2026-08-12 run was manual. First real test: **2026-09-01**.

---

## Backlog

Ordered by priority. Sizes: S ≈ hours, M ≈ a day, L ≈ multi-day. Run `/speckit.specify` per item
when starting it; do not pre-write specs.

| # | Item | Size | Priority | Notes |
|---|---|---|---|---|
| 1 | Verify the 2026-09-01 scheduled rebalance actually fired | S | High | Nothing alerts on a missed rebalance; `launchd.err` is gitignored and written only on failure. |
| 2 | Alert on a missed/failed scheduled job | S | High | Why the 2026-08-01 failure (In flight #3) went unnoticed for 11 days. |
| 3 | Add a financing-spread term to the backtest | M | **Highest** | No longer conditional — the drag is confirmed contractual. The model charges 3–5bp per trade and nothing for holding, while the real cost is ~2%/yr on gross, so every walk-forward number overstates the edge — including the 1.15 Sharpe the book was selected on. |
| 4 | Re-check universe sizing now that gross exposure has a carrying cost | M | High | A financing term penalises breadth. The EM-inclusive universe was chosen partly for cross-sectional selection; that trade-off now has a cost on the other side. Reopens sizing, not the factor question. |
| 5 | Filter the universe on financing terms, not just rate differential | S | High | NZD publishes 0% credit (spread exceeds benchmark, floored at zero) and ILS 0% on all balances with BM+5% debit — both can only ever cost. Cheap, concrete. |
| 6 | Deploy the cash sleeve (SGOV) | S | Medium | Built, documented, never run; ~96k sits unparked. Keep symbols disjoint from other sleeves. |
| 7 | Schedule bond-ladder / income / cash sleeves | S | Medium | Manual-only today. |
| 8 | Move the FRED API key out of the launchd plist | S | Medium | Cleartext in `com.fx.paper-rebalance.plist` (mode 0600). Violates the EnvConfig-secrets rule. |
| 9 | Fix 21 pre-existing ruff violations | S | Medium | 8 unused imports, 11 over-long lines, 2 empty f-strings. Constitution III mandates the gate. |
| 10 | Refresh `docs/scheduled-paper-track.md` | S | Medium | Still documents `~/Documents/forex` paths throughout. |
| 11 | CI (pytest + ruff on push) | M | Medium | No CI exists; both gates are hand-run. |
| 12 | Stress the FX+basket blend against a synthetic 2008 | M | Low | Recommended in the findings doc before sizing; window has no GFC. |
| 13 | Commodity carry via roll-adjusted data | L | Low | Blocked on paid data (Norgate/Databento). The only commodity signal not yet falsified. |
| 14 | Macro-surprise nowcasting (#8) | L | Low | Blocked: needs a consensus feed. |
| 15 | FX options VRP (#9) / order flow (#10) | L | Low | Blocked: no free/retail data source. |
| 16 | Explicit rebalance marker written at trade time | S | Low | Robust alternative deferred in `specs/001-fx-only-reporting/research.md` R1. Current detection infers rebalances from unsettled-trade counts, which depends on a stable ETF position baseline. |
| 17 | Securities lending (SYEP) | S | Won't do | Assessed net-negative for this book in a taxable account. Revisit only if tax-advantaged or holding hard-to-borrow names. |

**Live deployment** is deliberately *not* on this list as a task. The execution stack is
paper-validated; going live is a decision, not an engineering item, and is gated by Constitution
Principle IV.

---

## Known discrepancies

Found while consolidating. Code is treated as the source of truth.

1. **`docs/scheduled-paper-track.md` documents the wrong repo path.** Every plist and cron example
   says `~/Documents/forex`; the repo is at `~/projects/forex`. This exact staleness caused the
   2026-08-01 missed rebalance. The installed plists are now correct; the doc is not. → Backlog #9.
2. **`docs/scheduled-paper-track.md` says FX "shows as multi-currency cash (so IBKR
   `GrossPositionValue` reads 0)".** That was true when the FX book ran alone. With the ETF sleeves
   deployed, `GrossPositionValue` is ~910k. The underlying claim — FX is cash, not positions — is
   correct and is now encoded in `forex/run/fxbook.py`.
3. **`docs/basket-sleeve.md` states a 50% per-order cap.** The default was raised to 0.6 in
   `forex/run/basket.py` (`docs/archive/planning/final-fixes-report.md`, Fix 1) because IEF's natural inverse-vol
   weight sits near 0.49. The doc was never updated.
4. **`docs/basket-sleeve.md` documents a `basket_positions.csv` header without `complete`.** The
   column was added in Fix 3. Actual header:
   `timestamp, account, symbol, shares, weight, allocation, applied, complete`.
5. **The basket sleeve's deployed allocation is ~298k, not the documented 400k default.** The
   2026-07-18 placement used 298k. Both `docs/basket-sleeve.md` and `docs/archive/planning/basket-sleeve-plan.md`
   describe 400k as the default, which is still the code default — the deployment simply differed.
6. **`docs/archive/architecture-review.md` quotes Sharpe figures (0.32 / 0.50 / 0.52) that do not
   reproduce.** The doc already carries a correction notice: they came from a stale data cache; real
   figures are ~3× lower and the G10 edge is a pre-2010 artifact. Archived as superseded.
7. **`README.md` says "280+ tests"; the suite is 297.** Minor, not tracked separately.
8. **`nav.csv` rows before 2026-08-16 have empty FX columns.** The pre-migration `open_legs` column
   counted ETF stock positions, not FX legs. That history cannot be reconstructed.

---

## Map of the planning material

| Location | Role |
|---|---|
| `specs/000-baseline/baseline.md` | This file. The status page. |
| `specs/NNN-<feature>/` | Per-feature Spec Kit output, created by `/speckit.specify`. |
| `.specify/memory/constitution.md` | Project principles (v1.0.0). |
| `docs/strategy-research-backlog.md` | **Live.** The factor-search decision log. |
| `docs/ibkr-alternative-strategies-findings.md` | **Live.** Why the FX+basket combination is the answer. |
| `docs/income-enhancements.md` | **Live.** Cash-sleeve + securities-lending analysis (Backlog #5, #15). |
| `docs/intraday-fx-assessment-plan.md` | **Live.** Closed-negative intraday record. |
| `docs/basket-sleeve.md` | **Live.** Basket sleeve operating manual (see discrepancies 3–5). |
| `docs/scheduled-paper-track.md` | **Live.** Scheduling operating manual (see discrepancy 1). |
| `MEMORY.md` + `memory/` | Findings not derivable from code or git history. |
| `docs/archive/` | Superseded. Kept for the record, not maintained. |
