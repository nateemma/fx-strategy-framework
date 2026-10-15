# Gate — does inverse-vol weighting beat fixed weights in the basket? (2026-10-15)

**Verdict: no persistent difference either way. Keep the deployed construction; nothing to change.**
Full-sample the two are a tie (Sharpe **0.84 vs 0.84**). Inverse-vol wins 2006–2015 and loses 2016–2026,
so neither clears the two-era persistence rule. What inverse-vol actually buys is a **GFC-shaped crash
hedge** (+8.6% vs +1.1% through 2007–09), paid for with ~3× the turnover. It bought nothing in 2020 or
2022.

## Where the question came from

The basket (`docs/basket-sleeve.md`) is the closest thing in this repo to buy-and-hold: five ETFs,
long-only, unlevered, rebalanced quarterly. But its weights are not fixed — each quarter they reset to
inverse 60-day vol. A truly fixed allocation (60/40, equal weight, or the basket's own average mix) had
only ever appeared as a comparator, never as a gated candidate. This closes that gap.

## Method

Deployed construction, unchanged: SPY/TLT/IEF/GLD/DBC, `forex.run.basket_weights.inverse_vol_weights`
(60d) evaluated at each quarter-end close, weights drift daily between rebalances, 5bp per unit of
turnover, cash-financed, no cash yield. Adjusted closes from `forex.data.yahoo.load_prices` (cached).
Window **2006-05-17 → 2026-10-15** (DBC constrains the start). Sharpe is return/vol with no risk-free
deduction, matching `docs/rsp-vs-spy-basket.md`. The deployed book's full-sample Sharpe here is 0.84
rather than that doc's 0.87 only because this window runs two months longer.

The average inverse-vol weights reproduce the RSP gate's table exactly (SPY 16.1 / TLT 17.5 / IEF 37.7 /
GLD 14.9 / DBC 13.9), which validates the harness against the deployed sleeve.

**`fixed @ mean-IV` is in-sample:** those weights are only knowable in hindsight. `equal 20%` is the
honest out-of-sample fixed alternative.

## Results

Sharpe (max drawdown):

| Book | Full | 2006–2015 | 2016–2026 | Return/yr (full) | Turnover/yr |
|---|---|---|---|---|---|
| **Inverse-vol (deployed)** | **0.84** (−18.4%) | **0.87** (−11.4%) | 0.81 (−18.4%) | 5.86% | 57% |
| Fixed @ mean-IV weights* | 0.84 (−18.1%) | 0.77 (−15.0%) | 0.90 (−18.1%) | 6.05% | 18% |
| Fixed equal 20% × 5 | 0.80 (−21.0%) | 0.56 (−21.0%) | **1.03** (−18.4%) | 6.77% | 21% |
| Equal × 5, never rebalanced | 0.78 (−22.3%) | 0.53 (−22.3%) | 1.00 (−19.7%) | 6.93% | 0% |
| 60/40 SPY/IEF | 0.79 (−31.6%) | 0.66 (−31.6%) | 0.92 (−21.3%) | 8.47% | 15% |
| 60/40 SPY/IEF, never rebalanced | 0.80 (−27.2%) | 0.68 (−27.2%) | 0.90 (−22.7%) | 9.16% | 0% |
| SPY buy-and-hold | 0.58 (−55.2%) | 0.34 (−55.2%) | 0.85 (−33.7%) | 11.17% | 0% |

Correlation to the deployed basket (full): mean-IV fixed 0.97, equal 20% 0.94, 60/40 0.49, SPY 0.32.

Stress periods, total return:

| Period | Inverse-vol | Fixed mean-IV | Equal 20% | 60/40 | SPY |
|---|---|---|---|---|---|
| GFC 2007-10-09 → 2009-03-09 | **+8.6%** | +1.1% | −4.3% | −31.3% | −54.8% |
| COVID 2020-02-19 → 03-23 | −7.7% | **−4.1%** | −7.7% | −17.6% | −33.4% |
| 2022 | −11.7% | −12.0% | **−9.8%** | −16.8% | −18.2% |

## Reading it

1. **Full-sample tie.** Holding the same average mix at fixed weights matches inverse-vol's Sharpe with a
   third of the trading. The two are the same portfolio at 0.97 correlation.
2. **Not persistent in either direction.** Inverse-vol wins the first era (0.87 vs 0.56 for equal
   weight), fixed weights win the second (1.03 / 0.92 vs 0.81). By the two-era rule neither has an edge;
   picking fixed weights today would be a bet that the 2016–2026 regime continues.
3. **Inverse-vol's value is one crash shape.** In 2008 vol spiked in equities and commodities while
   Treasuries rallied, so the reweight leaned into the hedge. In 2022 stocks and bonds fell together and
   it helped nothing; in March 2020 the quarterly cadence was too slow to matter.
4. **60/40 sells drawdown for return.** About +2.5pp/yr over the basket at ~1.7× the drawdown, and −31%
   through the GFC with no gold or commodities to offset.
5. **Not rebalancing cost nothing** over this window — the drift went toward equities in a bull market.
   That is a regime fact, not a property of buy-and-hold.

## What would reopen this

A reason to expect 2016–2026 conditions to persist (it would favour fixed weights and lower turnover),
or a change to the rebalance cadence — a monthly inverse-vol book might have caught March 2020, which
quarterly could not. Neither is tested here.

## Reproduction

Run from the repo root with `PYTHONPATH=. .venv/bin/python <script>`:

```python
import numpy as np
import pandas as pd

from forex.data.yahoo import load_prices
from forex.run.basket_weights import inverse_vol_weights

SYMS = ["SPY", "TLT", "IEF", "GLD", "DBC"]
COST = 0.0005
px = pd.concat([load_prices(s) for s in SYMS], axis=1).dropna()
rets = px.pct_change().iloc[1:]
rets = rets[rets.index >= px.index[0] + pd.Timedelta(days=100)]  # room for the 60d lookback
qends = set(rets.groupby(rets.index.to_period("Q")).apply(lambda r: r.index[-1]))


def run(target_fn, rebalance=True):
    """Daily drifting weights; reset to target at quarter-end close (target sees data up to that close)."""
    w = target_fn(rets.index[0] - pd.Timedelta(days=1)).reindex(rets.columns, fill_value=0.0)
    out, turn = [], 0.0
    for d, r in rets.iterrows():
        port = float((w * r).sum())
        w = w * (1 + r) / (1 + port)
        cost = 0.0
        if rebalance and d in qends:
            tgt = target_fn(d).reindex(rets.columns, fill_value=0.0)
            t = float((tgt - w).abs().sum())
            cost, turn, w = t * COST, turn + t, tgt
        out.append(port - cost)
    s = pd.Series(out, index=rets.index)
    s.attrs["turn"] = turn / (len(s) / 252)
    return s


def iv(d):
    return inverse_vol_weights(px[px.index <= d], 60)


def fixed(weights):
    s = pd.Series(weights, dtype=float)
    return lambda d: s / s.sum()


iv_ret = run(iv)
mean_iv = pd.DataFrame([iv(d) for d in sorted(qends)]).mean()  # in-sample by construction
books = {
    "inverse-vol": iv_ret,
    "fixed @ mean-IV": run(fixed(mean_iv)),
    "equal 20%": run(fixed({s: 1 for s in SYMS})),
    "60/40": run(fixed({"SPY": .6, "IEF": .4})),
    "60/40 no rebal": run(fixed({"SPY": .6, "IEF": .4}), rebalance=False),
    "equal no rebal": run(fixed({s: 1 for s in SYMS}), rebalance=False),
    "SPY": run(fixed({"SPY": 1}), rebalance=False),
}
# Stats per era: CAGR from compounded equity, vol = std·√252, Sharpe = CAGR/vol, maxDD on equity.
```
