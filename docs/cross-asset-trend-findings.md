# Cross-Asset Trend (Managed Futures) — Gate Findings (2026-08-17)

Backlog A2. Gated before building, as every prior idea was.

**Verdict: PASS — and it is the equity-uncorrelated sleeve the book has been missing. But it is only
viable implemented in FUTURES. Every ETF implementation, levered or not, loses to cash.**

---

## 0. A correction to the survey

[`investable-universe-survey.md`](./investable-universe-survey.md) claimed only the *commodity* leg of
trend had been tested. **That was wrong.** The 2026-07 assessment tested cross-asset TSMOM directly and
recorded: *"~0% modern, −32% COVID whipsaw"*, equity correlation −0.03.

What that record contains, though, is the interesting part. **Correlation −0.03 is exactly the property
the book lacks.** So the live question was never "is trend uncorrelated" — that was settled — but
"can a properly-constructed version earn a positive return while keeping it?" A −32% COVID whipsaw is
an implementation signature, not a signal verdict: a vol-targeted book de-risks *into* rising vol.

## 1. Construction, fixed by convention rather than searched

16 liquid ETFs across four sleeves — equity (SPY, EFA, EEM, IWM), bonds (TLT, IEF, SHY, LQD), FX (UUP,
FXE, FXY), commodities (DBC, GLD, SLV, USO, DBA) — 2007-03 to 2026-08.

Three-lookback ensemble (63/126/252d), inverse-vol risk parity across markets, book-level vol target,
monthly rebalance, 5bp cost, weights lagged so nothing sees its own day. **No parameter was searched.**

## 2. The signal works, and every era is positive

| Era | ann | vol | Sharpe | maxDD |
|---|---|---|---|---|
| full 2007–2026 | +6.8% | 9.0% | 0.78 | −21.1% |
| GFC 2008–2012 | +5.3% | 9.8% | 0.57 | −9.8% |
| quiet 2013–2017 | +7.0% | 7.9% | 0.90 | −7.8% |
| 2018–2021 (COVID) | +7.8% | 8.2% | **0.95** | −8.4% |
| modern 2022–2026 | +8.4% | 10.2% | 0.84 | −21.1% |

**No COVID whipsaw** — that era is the best in the sample. The difference from the prior test is
construction: vol targeting, a lookback ensemble, monthly rather than frequent rebalancing, and
breadth. All four sleeves contribute positively on their own (bonds 0.61, commodity 0.39, equity 0.31,
FX 0.28), and the combined 0.78 sits well above any of them — the diversification is doing the work,
which is what a real CTA looks like.

**Robustness:** across six lookback configurations, full-sample Sharpe runs 0.61–0.85 and modern 0.49–1.43
— all positive, a broad plateau rather than a spike. The chosen (63/126/252) is *mid*-plateau, not the
best available: (126/252/504) gives 0.85/1.17 and (252) alone gives 1.43 modern. The headline is
conservative, not cherry-picked.

## 3. It is genuinely uncorrelated — the property VIX carry could not provide

| | trend | VIX carry (A1) |
|---|---|---|
| correlation to SPY | **−0.08** | +0.58 |
| correlation to the basket | +0.17 | +0.23 |
| **mean on the basket's 20 worst days** | **−0.12%** | −1.89% |
| **positive on those days** | **50%** | 5% |

On the days that decide a drawdown, trend is *flat* — it neither rescues nor compounds. That is what
diversification actually looks like, and it is the first thing found since FX carry that has it.

## 4. Then the financing filter, and it is brutal

The vol-targeted book is **levered: mean gross 2.51× NAV, pinned at the 3× cap 94% of the time.**
A diversified trend book has low natural vol (~4.3% at 1×), so reaching a 10% target requires
leverage — and on ETFs, leverage means margin.

Excess return over 3-month T-bills, which is the only comparison that matters:

| Implementation | full 2007–2026 | **modern 2022–2026** |
|---|---|---|
| vol-targeted ETFs, no financing charged | +5.3% | +4.2% |
| **vol-targeted ETFs, IBKR retail (218bp on gross)** | **−0.4%** | **−1.5%** |
| **unlevered ETFs (1.0×, no margin at all)** | +0.8% | **−1.3%** |
| **vol-targeted FUTURES (~25bp)** | **+4.6%** | **+3.6%** |

Read the modern column. **Levered ETFs at retail lose to cash. Unlevered ETFs also lose to cash** —
de-levering removes the financing cost but removes the return with it. Only the futures
implementation clears the bar.

This is the FX story repeating exactly: Sharpe 0.78 → 0.17 once retail financing is charged. The
difference is that trend has an escape route FX carry did not — futures, where leverage is embedded
in the basis at roughly the risk-free rate.

## 5. What it does to the actual book

Blending a futures-financed trend sleeve into the existing inverse-vol ETF basket:

| | ann | Sharpe | maxDD |
|---|---|---|---|
| basket alone | +5.9% | 0.82 | −17.7% |
| basket + 10% trend | +6.0% | 0.89 | −14.7% |
| basket + 20% trend | +6.0% | 0.95 | **−12.2%** |
| basket + 30% trend | +6.1% | 0.99 | **−10.7%** |

Return barely moves; **drawdown falls monotonically, −17.7% → −10.7%.** That is diversification paying
for itself rather than return being bought with risk — and it is precisely what A1 could not do, where
drawdown was unmoved.

## 6. Honest limits

- **The signal evidence is from ETF proxies; the recommended implementation is futures.** Futures track
  the same underlyings, so the gap is smaller than usual — but it is a gap, and it has not been tested.
- **The ~25bp futures financing figure is an assumption**, unlike the 218bp retail figure, which was
  measured against IBKR's published schedule.
- **The 3× leverage cap binds 94% of the time**, so the result depends on that choice. A 2× cap would
  give less return and less financing; the cap was set by convention, not fitted, but it is a live
  parameter and not a neutral one.
- **Free futures history is the known obstacle.** Yahoo `=F` continuous series carry roll-gap artifacts
  — the exact problem that made commodity carry untestable — and IBKR will not backfill futures
  history without a market-data subscription (A1's gate found 7 daily bars on the VX front month).
- **Trend is a crowded, widely-published strategy.** Every era here is positive, which is reassuring,
  but 2007–2026 contains no pre-GFC period and CTA returns have decayed over longer horizons.
- ETF selection is mildly survivorship-flavoured: 16 large, long-lived index ETFs, chosen by asset-class
  coverage rather than performance, but all of them still exist.

## 7. Recommendation

1. **Pursue this, in futures.** It is the best candidate the program has found since EM carry, and the
   only one that improves the book's drawdown rather than its return.
2. **Do not implement it in margined ETFs.** That version loses to cash. This is the single most
   important sentence here — the obvious, easy implementation is the one that does not work.
3. **Buy the market-data subscription.** A CME/CFE feed is a trivially small cost against a sleeve that
   cuts book drawdown by five points, and it also unblocks the futures data problem generally.
4. **Micro futures make it feasible at this account size.** MES/MNQ/M2K/MYM, micro Treasuries, micro FX
   and micro metals give the granularity a ~$200k sleeve needs.
5. **Execution work is real but patterned.** A futures executor would be the third after `LiveExecution`
   (FX) and `BasketExecution` (stocks); the guard/reconcile/rollback shape is established.
6. **Size around 20%** of the ETF track on this evidence — that is where drawdown improvement is
   substantial and the sleeve is still small enough that its own −21% drawdown is survivable.

## Reproduce

Free data throughout: Yahoo daily adjusted closes for the 16 ETFs, FRED `DGS3MO` for the cash
comparison. No broker connection required.
