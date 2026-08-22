# LEAN Data Gate — Findings (2026-08-17)

Spec `006` phase 1. Can QuantConnect/LEAN supply the futures history that blocks the trend sleeve,
and at what cost?

**Verdict: FAIL — and that is a good outcome. Do not migrate to LEAN for this.**

The gate found a better answer to the underlying problem: **IBKR's own market-data subscription costs
~$5/month and works with code that already exists.** The LEAN route requires an account, a paid
dataset marketplace of undisclosed price, Docker, and a new translation layer — to obtain the same
thing.

---

## What was actually asked (T001–T004)

### T001 — Does the LEAN CLI run locally without a cloud subscription? ✅ Yes

`lean 1.0.228` installs cleanly via `uv` and runs. Docker is required only for the backtest/research
engine, **not** for data operations, so a data-only workflow needs no daemon. Docker 29.4.1 is
installed on this machine but its daemon is stopped.

### T002 — Does it carry the eight markets? ⚠️ Cannot be determined without an account

`lean init` and the dataset catalogue both require QuantConnect credentials. The public dataset pages
are JavaScript applications behind a login; coverage per market is not publicly legible.

### T003 — Roll convention? ⚠️ Same

The crux question — adjusted, unadjusted, or individual contracts — could not be answered without an
account. This was the question that mattered most, since an unadjusted continuous series is what made
commodity carry untestable and would have left the trend gate no better validated.

### T004 — Cost, and local download? ⚠️ Paid marketplace, price behind a login

`lean data download` describes itself as **"Purchase and download data directly from QuantConnect"**.
QC Datasets is a paid marketplace; the price for futures is not published outside the product.

Usefully, the CLI also front-ends **many third-party providers**:

> Interactive Brokers · Oanda · Polygon · IQFeed · FactSet · AlphaVantage · ThetaData · **Databento**
> · TradeStation · Alpaca · Tastytrade · Bybit · dYdX · Webull …

**Databento** is notable: it is the roll-adjusted futures source the commodity-carry work already
identified as necessary. But that is a paid provider reachable directly from Python — LEAN adds
nothing to it except a wrapper.

---

## The finding that changes the answer

While pricing the alternatives, IBKR's own market-data fees turn out to be trivial:

| IBKR market data (non-professional) | USD/month |
|---|---|
| US Futures Value Bundle PLUS *(L2 add-on — **not** what is wanted; requires the base bundle)* | 5.00 |
| CME Real-Time (L1) | 1.55 |
| CBOT Real-Time (L1) | 1.55 |
| CME Real-Time (L2) | 12.10 |
| **US Securities Snapshot and Futures Value Bundle** *(L1 CBOT/CME/COMEX/NYMEX — **this is the one**)* | **10.00** |

The eight trend markets span CME (M2K, MES, M6E, M6A), CBOT (ZT, ZF, ZC) and NYMEX (MCL). Either
three individual L1 subscriptions (~$4.65) or the **US Securities Snapshot and Futures Value Bundle at
$10.00/month** covers all of them.

**The blocker that stopped spec `005` is a ten-dollar-a-month subscription.**

> **CORRECTION (2026-08-21).** This section originally named the *US Futures Value Bundle PLUS* at
> $5.00/month. That product is wrong for this purpose. Per IBKR footnote 5 it is a **depth-of-book (L2)
> add-on that requires** the $10 base bundle — the portal auto-adds the base when you tick PLUS. The
> base bundle alone (footnote 2) carries **top-of-book L1 for CBOT, CME, COMEX and NYMEX**, which is all
> a daily-bar strategy needs. Correct purchase: **the $10 base bundle only, without PLUS.**
>
> Two further conditions surfaced with it:
> - **Footnote 3 — US Futures data requires US Futures Trading Permissions on the account.** This account
>   has never traded futures, so this is a separate enablement and is probably the real hurdle.
> - **Footnote 4 — the $10 is waived above $30/month in commissions.** This book will not reach that; a
>   monthly FX rebalance plus quarterly sleeve runs is nowhere near. Budget the full $10.

## Comparison

| | IBKR subscription | LEAN / QC datasets |
|---|---|---|
| Cost | **$10/month, published** | Paid, undisclosed |
| Works with existing code | **Yes — `005` is built and tested** | No — needs a loader and translation layer |
| New tooling | **None** | LEAN CLI, Docker, a QC account |
| Roll convention | Individual contracts; continuous series built explicitly | Unknown |
| Ongoing maintenance | None | A second data path to keep working |

There is no dimension on which the LEAN route wins for this problem.

## What this does not close

LEAN remains the right answer to two questions it was never in the running for here:

1. **Asset classes the framework cannot express.** Its atom is "point-in-time data → target currency
   weights", which cannot represent options or prediction-market strategies. That limitation is real
   and unaddressed by any subscription.
2. **Roll-adjusted commodity history.** Still blocked (Tier C1). If that is ever pursued, Databento
   is the source — reachable directly from Python, with LEAN optional rather than required.

## Addendum — can the $5 be pre-justified for free? (2026-08-17)

Attempted, and the answer is **no** — but the attempt was worth it.

Yahoo carries free front-month continuous futures for all eight markets (`ES=F`, `ZT=F`, `6E=F`,
`CL=F`, …), most back to 2001. Running the gate construction unchanged on those, against the ETF
proxies over the same window:

| | ann | Sharpe | maxDD |
|---|---|---|---|
| ETF proxies | +7.0% | **0.95** | −16.8% |
| Yahoo futures (unadjusted) | +1.7% | **0.25** | −25.7% |

A large divergence. I split it by asset group expecting roll-gap contamination to explain it —
financials have a small basis, commodities a large one, so financials should have agreed:

| | futures | ETF |
|---|---|---|
| financials only (ZT ZF M6E M6A MES M2K) | 0.13 | 0.77 |
| commodities only (MCL ZC) | 0.03 | 0.61 |

**They did not agree, and that framing of the diagnostic was wrong.** The contamination is not the
size of individual roll *gaps*; it is that an unadjusted front-month series **truncates each
contract's convergence at the splice**, so the carry a real position earns never appears in the price
series at all. That applies to every futures market in proportion to its basis, financials included,
and it compounds over nine years. It is the same defect recorded for commodity carry — *"roll gaps
**are** the signal with flipped sign"* — appearing here as a systematic return drag.

**So free continuous futures data cannot settle this question**, and no amount of care with it will.
That is a structural property of the data, not a limitation of the test.

What the exercise *did* establish, because these are correlation properties and survive the artifact:

- the two implementations correlate **+0.74**;
- the futures version's diversification holds — **−0.15** to SPY, **−0.13** to the basket, and
  **+0.32%** on the basket's 20 worst days, positive 60% of the time (ETF version: +0.38%, 55%).

The *diversification* case survives. The *return level* in the actual instrument is genuinely open,
and that is precisely what the subscription buys an answer to.

## Addendum — the subscription question is CLOSED: do not buy (2026-08-21)

Probed the live Gateway (read-only) instead of continuing to reason from documentation. **The premise of
this whole gate was wrong.**

**The subscription was purchased, and it works.** The operator bought the bundle before this probe ran
— which is *why* data returns at all. All eight markets deliver **live** L1 (`marketDataType=1`, no
entitlement error, `usfuture` farm connected). SPY by contrast throws error 10089 "requires additional
subscription", consistent with the base bundle carrying snapshot equities but streaming futures. The
purchase did exactly what it advertises.

> **Correction.** This addendum first claimed futures data "already works without any subscription" and
> recommended not buying. That was wrong on both counts — the data was flowing *because* of the
> purchase. What follows was measured **with the entitlement active**, which makes it stronger evidence,
> not weaker.

> ⚠️ **One variable still open.** US Futures **Trading** Permissions were still pending when this ran
> (market-data entitlement and trading permission are separate approvals). Depth is unlikely to be
> gated on the trading permission, but re-run the probes once it lands before treating the numbers as
> final.

**The subscription did not solve the problem. The blocker is history retention, and money cannot buy it.**

| Market | Front-month bars | CONTFUT continuous series |
|---|---|---|
| MES / M2K | 294 (from 2025-06) | 480 — from 2024-09 |
| M6E / M6A | 110 (from 2026-03) | 298 — from 2025-06 |
| ZT / ZF | 160 (from 2026-01) | ~405 — from 2025-01 |
| ZC | 670 | 1175 — from 2021-12 |
| MCL | 701 | 704 — from 2023-10 |

`reqContractDetails(includeExpired=True)` returns only **8 contracts per market, earliest expiry
2025-12** — about eight months of expired-contract retention. That is IBKR's *contract database* limit,
which a market-data subscription does not affect. A back-adjusted series long enough to re-run the A2
gate needs years of expired contracts; they are not there to be bought.

**Consequences:**

1. **The bundle is bought and delivers live futures L1 — but not usable history.** This is precisely the
   exit criterion this gate wrote in advance: *"If only a couple of years come back, the subscription has
   not solved the problem."* It came back with two. Keep it only for a scoped purpose (see 5); otherwise
   cancel — billing is not prorated, so a cancellation still runs to the 1st.
2. **The A2 gate cannot be re-run on IBKR futures data.** An era split needs ≥2 temporally distant
   windows; two years of micros is one window. Forcing it would be the short-window overfit the method
   exists to prevent.
3. **The sleeve cannot run today regardless.** `MIN_HISTORY` is 315 bars; M6E and M6A have 298. It would
   refuse on 2 of 8 markets and run unvalidated on the rest.
5. **There is one good use for the month already paid for: spec `005` T028** — the single-contract test
   order, fill, reconcile and flatten. That validates the `FuturesExecution` guard set on a real account,
   needs only live quotes, and is independent of signal validation. Both prior sleeves had guard bugs
   that surfaced only on first real placement.
4. **This consolidates two blockers into one purchase decision.** Futures trend validation and commodity
   carry (Tier C1) both now need **Databento** roll-adjusted history. That is the real question, and it
   has a real price — unlike the $10 this gate spent three documents recommending.

**Method note.** Two successive recommendations here were wrong from documentation alone: the product
(PLUS is an L2 add-on, not the base bundle) and then the premise (entitlement, not retention). One
read-only probe against the live Gateway settled both. Probe the system before pricing the fix.

## Recommendation

1. ~~**Buy the US Securities Snapshot and Futures Value Bundle ($10/month)**~~ — **SUPERSEDED, do not buy.** See the 2026-08-21 addendum above: data already works, and the binding constraint is history retention, which no subscription fixes. Original text: re-run `scripts/trend_sleeve.py`. The
   practical test is immediate: today all eight markets return 0 bars, so the sleeve refuses. If bars
   appear, spec `005` phase 6 is unblocked.
   **The first thing to check is history depth, not the strategy.** IBKR's retention for *expired*
   futures contracts is limited, and a back-adjusted series long enough to re-run the gate needs them.
   If only a couple of years come back, the subscription has not solved the problem and Databento
   becomes the real question — cancel and reassess rather than forcing a short-window result.
2. **Do not migrate to LEAN.** Migration-plan stages 1–5 are closed on this evidence. The framework
   stays.
3. **Verify two things at subscription time**, since neither could be settled from documentation:
   - That **non-professional** status applies (it is a self-certification about how you trade, and it
     is the difference between $1.55 and $145 per exchange).
   - That an **L1 real-time** entitlement actually returns *historical* daily bars through the API.
     It should, but the cheap empirical test is simply to re-run the preview.
4. **Keep the LEAN CLI installed** in its scratch environment. It cost nothing, and it is the fastest
   route to Databento if commodity carry is ever revisited.

## Cost of this gate

About an hour, no money, no changes to the repo beyond documentation. It closed a proposed migration
and replaced it with a $10/month purchase — which is what a gate is for.
