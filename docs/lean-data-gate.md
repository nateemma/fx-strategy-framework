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
| **US Futures Value Bundle PLUS** | **5.00** |
| CME Real-Time (L1) | 1.55 |
| CBOT Real-Time (L1) | 1.55 |
| CME Real-Time (L2) | 12.10 |
| US Securities Snapshot and Futures Value Bundle | 10.00 |

The eight trend markets span CME (M2K, MES, M6E, M6A), CBOT (ZT, ZF, ZC) and NYMEX (MCL). Either
three individual L1 subscriptions (~$4.65) or the **US Futures Value Bundle PLUS at $5.00/month**
covers all of them.

**The blocker that stopped spec `005` is a five-dollar-a-month subscription.**

## Comparison

| | IBKR subscription | LEAN / QC datasets |
|---|---|---|
| Cost | **~$5/month, published** | Paid, undisclosed |
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

## Recommendation

1. **Buy the US Futures Value Bundle PLUS (~$5/month)** and re-run `scripts/trend_sleeve.py`. The
   practical test is immediate: today all eight markets return 0 bars, so the sleeve refuses. If bars
   appear, spec `005` phase 6 is unblocked.
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
and replaced it with a $5/month purchase — which is what a gate is for.
