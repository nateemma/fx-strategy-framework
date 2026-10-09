# Baseline — FX Strategy Framework

**Status page. Updated 2026-10-09 (c).** At-a-glance view of what exists, what is running, what is in
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
| Financing diagnosis | `forex/run/financing.py` | Done (2026-08-16). Spec `002-financing-spread`; 21 tests. |
| Financing in the backtest | `forex/backtest/financing.py` | Done (2026-08-16). Spec `003-financing-in-backtest`; `--financing`; 20 tests. |
| Scheduled-job healthcheck | `forex/run/health.py` | Done (2026-08-16), **corrected 2026-10-09**. Spec `004`, then `008-outage-detection`: it proved liveness from a watched file's mtime, and a failing run's traceback refreshed its own proof — it reported `ok` for the 2026-10-01 rebalance that placed nothing. Now asserts on success-only artifacts, every job states why a failure cannot write its own, and the report names broker reachability. 36 tests. |
| Gateway watchdog | `forex/run/gateway_watchdog.py` | Done (2026-10-09). Spec `008`; 11 tests. Probe-only agent `com.fx.gateway-watchdog`, every 300s, alerts after 2 consecutive misses and at most hourly. **Never starts, kills, or logs in** — cold start stays with `local.ibc-gateway`. |
| Connect-with-retry | `forex/run/ibconnect.py` | Done. Rides through Gateway auto-restart. |
| Scheduling | `scripts/install_schedules.sh` | Partially done — see In flight. |

### Live paper track (account DUQ218063, IB Gateway port 4002)

Running since **2026-07-17**. NAV **~990k** from 994k at inception (2026-10-09) — i.e. **−0.4%**,
after a −1.9% stretch through the September outage below.

| Sleeve | Runner | Deployed | Holding |
|---|---|---|---|
| FX book `carry_cot_mom` | `scripts/monthly_paper_rebalance.sh` | Yes | 14 currency legs (cash) |
| Risk-parity basket | `scripts/basket_rebalance.py` | Yes | SPY/TLT/IEF/GLD/DBC, ~268k (trimmed 2026-08-20 to fund VIX carry) |
| Treasury bond ladder | `scripts/bond_ladder.py` | Yes | IBTG–IBTL, ~300k |
| Income sleeve | `scripts/income_sleeve.py` | Yes | BIZD/JEPI, ~298k |
| Cash sleeve (SGOV) | `scripts/cash_sleeve.py` | Yes | SGOV 845 (~85k), placed 2026-08-16 |
| VIX carry satellite | `scripts/vix_carry_sleeve.py` | Yes | SVXY 491 (~30k), placed 2026-08-20. Daily, contango-gated. |

**The ETF sleeves are ~90% of NAV**, so whole-account numbers measure the sleeves rather than
`carry_cot_mom`. `scripts/track_report.py` now reports the two separately — but FX statistics are
gated until 20 observations accumulate, and there is currently one.

---

## In flight

1. **FX-only performance reporting — BUILT 2026-08-16, awaiting data.**
   `scripts/track_report.py` now reports the FX book separately (spec `001-fx-only-reporting`).
   Statistics are gated at 20 observations and only one FX-bearing snapshot exists, so the report
   currently runs in levels-only mode. First meaningful reading is several weeks out.
2. **Scheduling is complete.** launchd runs the monthly FX rebalance, one quarterly job covering all
   four ETF sleeves, the daily NAV snapshot, and a daily healthcheck — all installed and verified
   running under launchd (2026-08-16).
3. **The FX book is viable at institutional financing and dead at retail.** Charging IBKR's published
   spreads takes `carry_cot_mom` from **Sharpe 1.15 / +3.03%/yr** to **0.17 / +0.44%/yr**. Inverting
   the model: it needs **~95bp all-in** (a third of retail's 289bp) to clear Sharpe 0.8; at 50bp it
   runs 0.97. **Borrowing is ~65% of the cost and is the negotiable side** — fixing only that reaches
   0.76. A bigger IBKR account does not help: EM debit spreads do not tier at any plausible size, and
   the best USD tier only reaches 0.31. **The binding constraint is the financing relationship, not
   the signal** — so further strategy work cannot fix it. Full analysis:
   [`docs/financing-spread-findings.md`](../../docs/financing-spread-findings.md).
4. **Financing drag — CONFIRMED against IBKR's published rates.** The book pays its carry rather than
   earning it. Verified 2026-08-16 against IBKR's published tiers: every leg untouched by the recent
   rebalance agrees on a ~13-day accrual window to within 10%, so the paper account reproduces the real
   schedule rather than simulating something cruder. Benchmark carry **+0.21%/yr** becomes a realised
   **−1.96%/yr**; financing costs **−2.18% of gross per year** against a ~3%/yr unlevered expectation.
   Full record: [`docs/financing-spread-findings.md`](../../docs/financing-spread-findings.md).
5. **The 2026-08-01 monthly rebalance silently failed** on a stale `~/Documents/forex` path after the
   repo moved to `~/projects/forex`. The plists were fixed the same day. **RESOLVED — launchd has now
   exercised the fix twice:** `track.log` carries a `2026-09-01T16:00:04Z` entry (09:00 PDT, i.e. the
   timer, not a human) and the 2026-10-01 job also fired on time, failing only on the Gateway outage in
   item 6. Backlog #1 closed.
6. **A 25-day Gateway auth outage, 2026-09-13 to 2026-10-08 — the worst operational failure so far.**
   IBKR expired the auto-restart tokens at the 03:00 restart on 09-13; IBC's token-based "Re-starting
   session" path cannot answer that, so the Gateway sat on the login dialog for 25 days and only an
   operator login on 10-08 08:16 cleared it. **Cost:** the 2026-10-01 monthly FX rebalance and quarterly
   sleeve rebalance both fired on time and placed **nothing** (connection refused, 6 retries each), and
   `nav.csv` lost 25 days — unrecoverable, since point-in-time account values cannot be re-fetched.
   Caught up by hand on 10-08/10-09: FX book rebalanced (turnover 0.715, 10 orders), then basket, income,
   cash, and finally the ladder once its bug (item 7) was fixed. **Two monitoring gaps let it run that
   long, both now Backlog #19–#20 — **both fixed 2026-10-09** by spec `008-outage-detection`.** The same
   failure recurred on 2026-09-06 and was cleared the same day, so expect the *root cause* roughly
   fortnightly — it is a credential expiry only a human login can clear — but it should now be reported
   within ~10 minutes rather than discovered by asking. The 2026-10-08 success marker was backfilled from
   `track.log` so the first reading is honest rather than a false OVERDUE.
7. **`quarterly_sleeves.sh` could not rebalance the ladder sleeve, and said it could — FIXED 2026-10-09.**
   It called `bond_ladder.py` with no `--symbols`, so the script's `SHY,IEI,IEF` default applied while the
   deployed ladder is `IBTG–IBTL`. Had it ever connected it would have orphaned ~300k of iBonds, bought
   ~200k of SHY+IEI, and sold the **basket's** IEF out from under it (reconcile is by conId account-wide).
   Latent since `80b16c3` and never fired, because the ladder step has never completed under the
   quarterly job — placed by hand in July, connection-refused in October. Fixed by pinning
   `LADDER_SYMBOLS`; verified with a stub-`python` run of the real script. `bond_ladder.py`'s default is
   **still** `SHY,IEI,IEF`, so a bare manual invocation remains dangerous → Backlog #21.

---

## Backlog

Ordered by priority. Sizes: S ≈ hours, M ≈ a day, L ≈ multi-day. Run `/speckit.specify` per item
when starting it; do not pre-write specs.

| # | Item | Size | Priority | Notes |
|---|---|---|---|---|
| 1 | ~~Verify the 2026-09-01 scheduled rebalance actually fired~~ | S | **Closed** | **It fired.** `track.log` has a `2026-09-01T16:00:04Z` (09:00 PDT) entry, which is the timer rather than a human; 2026-10-01 fired on time too. Original note: The healthcheck is installed and will flag a miss by 2026-09-04. It cannot tell a scheduled run from a manual one, so confirm `track.log` carries a **09:00** entry — that is what proves launchd fired rather than you. |
| 2 | Re-run the factor search with `--financing` on | L | **Medium** | Downgraded from High: financing is now known to be the binding constraint, so this is for correctness of the record, not to find a better book. A pre-financing Sharpe of 1.3 would still only reach ~0.3 at retail. |
| 3 | Revisit deployment if financing terms change | — | Watch | The number to remember is **95bp all-in**. Below that the book is a Sharpe ~0.8 proposition and the repo is ready for it. Not actionable at current capital. |
| 4 | ~~Filter the universe on financing terms~~ | S | **Closed** | Tested during 003: G10-only is *worse* (Sharpe −0.37 vs 0.17). The expensive legs are the profitable legs. Narrowing is not the fix. |
| 5 | ~~VIX carry satellite~~ | M | **Done** | Deployed 2026-08-20 at \$30k (SVXY 491), funded by trimming the basket 298k → 268k. Spec `007`; daily contango gate; healthcheck watching. Return enhancement, NOT diversification — the book still lacks an equity-uncorrelated sleeve. |
| 6 | ~~Futures market-data subscription~~ | S | **Done — and it did not unblock #7** | Bought by the operator; verified 2026-08-21 delivering **live** L1 on all eight markets (`mdType=1`, `usfuture` connected). But the history it delivers is ~2 years on the micros (M6E/M6A from 2025-06) and `includeExpired` returns only 8 contracts back to 2025-12 — measured *with* the entitlement active. That is this gate's own pre-written exit criterion, met. **Trading permission LANDED — verified 2026-10-09** by read-only `whatIfOrder` (MESZ6 initMargin +$2,471.96, commission $0.61; ZTZ6 +$1,378.78 / $1.51; both `PreSubmitted`, no permission error), and the data bundle is still live and real-time (`usfuture` connected, `mdType=1`). **T028 was run on 2026-10-09 and passed** — 1 MES placed, filled, reconciled and flattened through `FuturesExecution`; details in `specs/005-futures-trend-sleeve/tasks.md`. **That was the last thing this subscription could buy, so it is now CANCELLABLE** — the sleeve stays blocked on Databento history either way. Billing is not prorated, so cancel at the period boundary. The product is the **US Securities Snapshot and Futures Value Bundle at \$10.00/month** — *not* the \$5 "Futures Value Bundle PLUS", which is an L2 add-on that requires the \$10 base. `docs/lean-data-gate.md`. |
| 7 | Trend sleeve live validation (spec `005` phase 6) | M | **Blocked** (T028 done) | **T028 passed 2026-10-09** — the executor is validated against the live paper account, so Phase 6's only non-data task is closed. Everything else is blocked on *data depth*, not the $10. The A2 gate cannot be re-run on IBKR history (2 years of micros = one era, no split), and the sleeve refuses today anyway — `MIN_HISTORY` is 315 bars, M6E/M6A have 298. Needs Databento roll-adjusted history, the same purchase as #11. |
| 8 | ~~Box-spread financing~~ | S | **Closed** | Gated 2026-08-19: solves a problem this book does not have. Cannot rescue FX carry (0.42 vs the 0.80 bar, because a box borrows USD and the cost is in the foreign legs), and levering the ETF basket destroys Sharpe at any financing rate. Revisit only if a high-Sharpe cash strategy worth levering appears. `docs/box-spread-findings.md`. |
| 9 | ~~Prediction markets (ForecastEx)~~ | S | **Closed** | Gated 2026-08-20. Data is the best of any candidate — free daily CSVs, ~2y deep, settlement prices included — but median traded contract turns over **$49/day** and only 8% of contracts trade at all. Rejected on liquidity. Calibration unresolved; three filter definitions gave three answers and the first was my own selection bias. `docs/prediction-markets-findings.md`. |
| 10 | Stress the FX+basket blend against a synthetic 2008 | M | Low | Recommended in the findings doc before sizing; window has no GFC. |
| 11 | Commodity carry via roll-adjusted data | L | Low | Blocked on paid data (Norgate/Databento). The only commodity signal not yet falsified. **Now shares its blocker with #7** — one Databento decision unblocks both, which changes the cost/benefit of that purchase. |
| 12 | Macro-surprise nowcasting (#8) | L | Low | Blocked: needs a consensus feed. |
| 13 | FX options VRP (#9) / order flow (#10) | L | Low | Blocked: no free/retail data source. |
| 14 | Explicit rebalance marker written at trade time | S | Low | Robust alternative deferred in `specs/001-fx-only-reporting/research.md` R1. Current detection infers rebalances from unsettled-trade counts, which depends on a stable ETF position baseline. |
| 15 | Securities lending (SYEP) | S | Won't do | Assessed net-negative for this book in a taxable account. Revisit only if tax-advantaged or holding hard-to-borrow names. |
| 17 | ~~Momentum basket on IBKR stocks or crypto~~ | S | **Closed** | Gated 2026-08-25 from the freqtrade `MomentumRegimeBasket15mFast` review. **Crypto:** IBKR/PAXOS offers 11 coins; restricted to them the strategy returns 12.7% at Sharpe 0.49 — identical to holding BTC — and P3 goes +1094% → −9.2%. The edge lived in the illiquid-alt tail IBKR does not list. **Equities:** on a de-biased large-cap universe every lookback loses to equal-weight buy-and-hold of the same names (lb=14 Sharpe 0.51, lb=90 0.74, vs EW 1.04 and SPY 0.86). Fast lookbacks are the *worst* on liquid names. **Follow-ups:** the BTC regime gate does nearly all the work (ablating it takes crypto 47.2%→3.7%), so this is a trend-timing overlay, not a momentum basket; and **small caps do carry more dispersion (8.3% vs 5.8%) but still lose** — at 15bp the best variant scores 0.50 against the same universe's equal-weight 0.86, and at 30bp it goes negative with a −91% drawdown. **Universe search closed:** measured dispersion-per-cost across 7 liquid universes — industry/thematic ETFs rank best (137 vs crypto's 59) and still lose (0.66 vs their own EW 0.73 and SPY 0.93). **No regime gate helps outside crypto** (SPY/IWM/own-EW all within noise; on ETFs *no* gate ties). Crypto needs a strongly-trending dominant factor AND a high-dispersion tail levered to it; gate alone gives 9.3%, cross-section alone 3.7%, both 47.2%. `docs/momentum-basket-ibkr-assessment.md`. |
| 18 | ~~Equal-weight (RSP) equity leg in the basket~~ | S | **Closed** | Gated 2026-08-25. Null: the two baskets correlate **0.993** and SPY is marginally better full-sample (0.87 vs 0.83). Inverse-vol gives equities only 16% weight / 20% of risk, so the index choice is diluted 5:1 before it reaches the portfolio. RSP also costs 11bp/yr more. The prompting observation (EW +12pp/yr in the lost decade) was **my own survivorship bias inflating a real +3.2pp/yr effect ~4×**; RSP's actual premium is 2003-09 only and negative since 2016. `docs/rsp-vs-spy-basket.md`. |
| 16 | ~~Per-holding trend overlay on the basket~~ | S | **Closed** | Gated 2026-08-21 from the freqtrade `MomentumRegimeBasket15m` review. Moving each ETF's slice to cash when it trades below its own SMA cuts maxDD (−18.5% → −9.8%) and equity correlation (0.32 → −0.03), but the Sharpe gain appears in only one of two eras and **loses to a static 63/37 basket/T-bill split** that needs no signal at all. Genuine benefit is confined to stock-bond joint drawdowns (2022: −1.3% vs −11.8%). `docs/momentum-basket-15m-assessment.md`. |
| 19 | ~~Healthcheck must assert success, not file freshness~~ | S | **Done 2026-10-09** | Spec `008-outage-detection` US1. `paper-rebalance` now watches `fx_rebalance_status.csv`, written by the runner only after its `set -euo pipefail` block closes; every `Job` carries `success_evidence` naming the mechanism that makes its artifact success-only, asserted by a test. Original note: **It reported `paper-rebalance` "ok" for a run that placed nothing.** `forex/run/health.py` watches a watched file's mtime, and a *failure traceback writes to that same file* (`track.log`), so a failed job refreshes its own liveness proof. `basket-rebalance` only showed OVERDUE because it watches `basket_positions.csv`, which a failure never touches. Fix: assert on a success marker in the log, and add a live port-4002 reachability probe. CLAUDE.md calls this "the channel that cannot be suppressed" — today it can be. Direct cause of In-flight #6 running 25 days. |
| 20 | ~~Gateway login supervision — liveness of IBC is not liveness of port 4002~~ | M | **Done 2026-10-09** | Spec `008-outage-detection` US2. New `com.fx.gateway-watchdog` agent probes port 4002 every 300s and exits, so its timer cannot be starved the way the exec-based supervisor's was. Alert-only by operator decision; `local.ibc-gateway` is untouched and keeps cold start, so nothing can start a second Gateway. Detection goes from 25 days to ~10 minutes. Original note: `local.ibc-gateway` gates on the IBC process, and IBC stayed alive for the entire outage (pid 2091, 40 days), so launchd never restarted the job and **the 120s port check never ran once**. The supervisor fixed IBC *exiting* (commit `bb6a431`); it cannot see IBC *alive but not logged in*. Fix: move the port check to its own launchd job independent of the IBC process, and/or kill a Gateway that is up but not listening. Note the root cause is unfixable by design — IBKR expiring auto-restart tokens requires a manual login — so the goal is **alerting in hours, not weeks**. |
| 21 | `bond_ladder.py` default symbols are a live trap | S | Medium | The default is `SHY,IEI,IEF`; `IEF` collides with the basket sleeve, and reconcile is by conId account-wide. In-flight #7 fixed the *caller*; a bare `python scripts/bond_ladder.py --confirm` still does the damage. Either drop `IEF` from the default or make `--symbols` required. |
| 22 | IB Gateway 10.45 is desupported 2026-12-15 | S | Medium | Error 2172 on every connect: "version 1045.1 needs to be upgraded, as it will be desupported on 20261215". A dated deadline on the component that has already cost 25 days of downtime. Upgrading also re-opens the IBC/`config.ini` path, so do it deliberately rather than under pressure. |
| 23 | Make the scheduled jobs patient about a logged-out Gateway | S | **High** | `connect_with_retry` gives up after 6 attempts over ~1 minute. For a job that runs once a month that is absurdly impatient: on 2026-10-01 it turned a transient login gap into a **missed rebalance** rather than a late one. A backoff measured in hours would have let the 10-01 job place once the Gateway came back. Independent of IBKR and entirely within our control — the cheapest remaining resilience win. Referenced from `docs/platform-decision.md`. |

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
9. **`docs/lean-data-gate.md` summarises the futures subscription as "~$5/month" at line 8; the correct
   product is $10.00/month.** The body already carries the 2026-08-21 correction (the $5 "US Futures
   Value Bundle PLUS" is an L2 add-on that *requires* the $10 "US Securities Snapshot and Futures Value
   Bundle"), but the summary line and the docs-map entry were never updated. Anyone pricing the decision
   from the summary gets it wrong by half.
10. **`nav.csv` has an unrecoverable 25-day hole, 2026-09-13 to 2026-10-08.** See In-flight #6. Any FX
   statistics computed across that boundary are measuring two windows joined by a gap, not a series.

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
| `docs/investable-universe-survey.md` | **Live.** What the account can trade, what has been investigated, and what is worth doing next. |
| `docs/financing-spread-findings.md` | **Live.** Why the FX book needs institutional financing. |
| `docs/vix-carry-findings.md` | **Live.** A1 gate: VIX carry is real but is equity beta, not a diversifier. |
| `docs/cross-asset-trend-findings.md` | **Live.** A2 gate: cross-asset trend passes, but only in futures. |
| `docs/platform-decision.md` | **Live.** Why IBKR stays, why LEAN is research-only, and why capital is the real constraint. |
| `docs/lean-migration-plan.md` | **Closed.** Staged LEAN plan; declined at stage 0. |
| `docs/lean-data-gate.md` | **Live.** Why LEAN was declined, and the **$10/month** IBKR subscription (US Securities Snapshot and Futures Value Bundle) that supplies futures quotes. Its own summary line still says "~$5/month", corrected in the body at the 2026-08-21 note — see discrepancy 9. |
| `docs/box-spread-findings.md` | **Closed.** Box financing rejected: the book has nothing worth levering in cash instruments. |
| `docs/prediction-markets-findings.md` | **Closed.** ForecastEx rejected on liquidity ($49/day median). Contains a reusable warning about filters that delete losers. |
| `docs/rsp-vs-spy-basket.md` | **Closed.** Why the basket's equity leg stays SPY, and the survivorship correction that prompted it. |
| `docs/momentum-basket-ibkr-assessment.md` | **Closed.** Momentum basket on IBKR stocks/crypto rejected; contains the equal-weight null that should be run against any future cross-sectional idea. |
| `docs/momentum-basket-15m-assessment.md` | **Closed.** Why the freqtrade 15m momentum-basket approach does not transfer, and the trend-overlay gate that rejected its one testable component. |
| `docs/basket-sleeve.md` | **Live.** Basket sleeve operating manual (see discrepancies 3–5). |
| `docs/scheduled-paper-track.md` | **Live.** Scheduling operating manual (see discrepancy 1). |
| `MEMORY.md` + `memory/` | Findings not derivable from code or git history. |
| `docs/archive/legacy-memory/` | **Archive.** 25 memories stranded at the pre-move `~/Documents/forex` path. Historical; superseded by the docs of record. |
| `docs/archive/` | Superseded. Kept for the record, not maintained. |
