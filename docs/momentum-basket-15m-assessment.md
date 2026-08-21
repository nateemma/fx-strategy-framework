# Assessment — `MomentumRegimeBasket15m` (freqtrade crypto) transplanted here (2026-08-21)

Reviewed at the operator's request: `~/Documents/freqtrade/user_data/strategies/Basket/MomentumRegimeBasket15m.py`.
Question asked: *would that general approach be useful here?*

**Verdict: no as a strategy, and the one component worth testing was tested and failed.** The signal is
already-rejected ground, the timeframe is doubly-rejected ground, and the genuinely clever part — the
accumulating liquidity-aware fill model — solves a problem this repo does not have. The one idea that
looked transferable (the per-holding trend filter) was gated below and **loses to simply holding cash**.

---

## What the strategy actually is

Four separable ideas, worth judging separately rather than as one thing:

| # | Component | What it does |
|---|---|---|
| S1 | **Cross-sectional top-N momentum** | 90-day trailing return, rank, hold the top 3, equal-weight |
| S2 | **Market regime gate** | flat unless BTC > its daily SMA(100) |
| S3 | **Per-holding trend filter** | a held coin must also be above its *own* SMA(50), else drop it to cash |
| S4 | **Accumulating, liquidity-capped fills** | 15m candles, hourly rebalance, each add ≤ 10% of that candle's quote volume, accumulating toward target over many candles rather than one fill |

The author is explicit that S4 is the load-bearing mechanic — a single next-candle fill capped to one
candle's liquidity returns −17%, and the edge only appears once fills accumulate. The file's own caveats
are honest: survivorship bias inflates the magnitude, the sample is ~2 years / one cycle.

## S1 + S2 — already gated here, and rejected

`docs/investable-universe-survey.md` §4 and `docs/ibkr-alternative-strategies-findings.md` row 5 record
this exact family, tested 2026-07 on ETFs:

> **Momentum rotation's crypto magic does NOT transfer.** Frequent rebalancing *hurts* on liquid ETFs
> (weekly Sharpe 0.54 < monthly 0.61 — whipsaw). The crypto winner leaned on survivorship + illiquid-alt
> concentration + extreme dispersion, none of which exist in efficient ETFs.

Result: ~6–7%/yr at Sharpe ~0.6, correlation 0.5 to the deployed book — i.e. it does not beat the basket it
would replace. S2's ETF analogue (SPY > SMA200) is the most-published and most-decayed timing rule there is.
Under the standalone-first rule (Constitution v1.1.0), the question is *"would this be worth running on its
own capital?"* — a Sharpe-0.6 long-only equity-correlated rotation is not.

## S4 — sound engineering, wrong problem

The accumulation model is a correct diagnosis of a real crypto failure: on illiquid alt pairs the target
position exceeds what a candle can absorb, so a one-shot fill model is fiction and a one-shot *real* fill
captures nothing. It is the same class of error this program records globally as *"lookahead-clean ≠
realistic"*.

**It is not binding on anything this repo trades.** The deployed sleeves hold SPY / TLT / IEF / GLD / DBC,
BIZD / JEPI, SGOV and SVXY, at $30k–$300k per sleeve — against tapes measured in hundreds of millions to
billions per day. The largest single position in the account is roughly a rounding error on its own ADV.
The one place granularity *does* bite is the futures trend sleeve, but that is integer-contract rounding
(`target_contracts` already reports it), not liquidity — accumulation does not help, and micro contracts
are liquid.

Worth keeping in mind if the universe ever moves to single-name equities, CEFs (Tier B2), or
prediction markets — the ForecastEx rejection was *precisely* a liquidity rejection ($49/day median).

## S3 — the one testable idea, gated here

This is the component with the strongest claim in the source file: requiring each held asset to be above
its own SMA cut crypto maxDD ~40% → 23% *while raising return*. It is worth taking seriously here because
it attacks the deployed basket's actual weakness — a −18% drawdown and 0.42 equity correlation — and it is
financing-favourable (moving to cash *reduces* gross exposure, so filter 5 points the right way).

**Construction.** Baseline = the deployed sleeve exactly: quarterly-rebalanced inverse-60d-vol basket of
SPY/TLT/IEF/GLD/DBC, long-only, cash-financed, 2006-05 → 2026-08 (free Yahoo adjusted closes, includes the
GFC). Overlay = identical, except an asset's slice moves to T-bills on any day it closed below its own
SMA(N) as of the **prior** session. Freed weight is not redistributed. 5bp per unit traded; cash earns ^IRX.

### Full sample

| | ann | vol | Sharpe | maxDD | corr SPY | turnover |
|---|---|---|---|---|---|---|
| baseline | 5.99% | 7.03% | **0.86** | −18.46% | 0.32 | 1.4×/yr |
| SMA(50) | 3.91% | 5.34% | 0.74 | −14.63% | −0.03 | 20.0×/yr |
| SMA(100) | 4.81% | 5.51% | 0.88 | −12.04% | −0.03 | 12.3×/yr |
| SMA(200) | 4.88% | 5.63% | 0.88 | −9.75% | −0.02 | 9.2×/yr |

### Era split — this is where it fails

| | 2006–2015 Sharpe | 2016–2026 Sharpe |
|---|---|---|
| baseline | **0.89** | 0.84 |
| SMA(50) | 0.54 | 0.96 |
| SMA(100) | 0.67 | **1.11** |
| SMA(200) | 0.86 | 0.90 |

The improvement appears in **one** of two temporally distant windows. Filter 2 requires both. The
parameter that wins the modern era (SMA-50/100) is the worst in the earlier one, and vice versa — there is
no window good in both, which is the signature of fitting a regime rather than finding an edge.

**Costs are not the explanation.** Re-run at 0bp, SMA(100) still scores 0.78 vs baseline 0.90 in 2006–2015.
The failure is regime, not friction. (Friction is real anyway: 12–20×/yr turnover on a sleeve that
currently turns over 1.4×.)

### The decisive test: is it anything more than de-levering?

Average invested exposure under the overlay is ~63%. So compare against the null of simply holding **63%
basket / 37% T-bills, statically**, which costs nothing and requires no signal:

| | static 63/37 | SMA(100) overlay |
|---|---|---|
| full Sharpe | **1.00** | 0.88 |
| 2006–2015 Sharpe | **0.97** | 0.67 |
| 2016–2026 Sharpe | 1.03 | **1.11** |
| 2022 return | −6.8% | **−1.3%** |
| COVID 2020 return | +5.1% | **+8.1%** |

**The null wins.** Most of what the overlay delivers is de-risking, and a static cash weight delivers it
more cheaply and more consistently. The overlay's genuine, non-replicable contribution is confined to
**stock–bond joint drawdowns** — 2022 (−1.3% vs −6.8% vs the full basket's −11.8%) and COVID. That is tail
insurance for one specific scenario, priced at ~120bp/yr of return and 10× the turnover.

**Rejected.** Not on cost, and not on the modern era — on persistence, and on losing to a null that
requires no signal at all.

### Incidental observation, not a recommendation

The static 63/37 null out-Sharpes the fully-invested basket (1.00 vs 0.86) across both eras. That says the
deployed sleeve sits above its Sharpe-maximising risk level in a sample where bills paid well — a *sizing*
observation, not a strategy, and it is sensitive to the rate environment. Recorded so it is not
rediscovered as a finding.

## What the source file does better than this repo

Nothing that changes what to build, but one thing worth naming: its causality argument is empirical and
strong — a truncation-invariance test recomputing the signal with future data removed, zero changed cells
across 76,867 candles × 75 pairs at four cut points. That is the right way to answer a false-positive
lookahead warning. This repo enforces the same property *structurally* (`DataView.truncate`,
`assert_causal`, Constitution II), which is stronger because it survives refactoring — but the empirical
test is the correct fallback wherever a signal is computed outside the framework.

## Summary

| Component | Transfers? | Why |
|---|---|---|
| S1 cross-sectional momentum | **No** | Gated 2026-07: ~6–7%, Sharpe 0.6, corr 0.5 — loses to the basket it would replace |
| S2 regime gate | **No** | SPY>SMA200 is the most-decayed timing rule in the literature |
| S3 per-holding trend filter | **No** — gated above | Not persistent across eras; loses to a static 63/37 cash split |
| S4 accumulating liquidity-capped fills | **Not applicable** | Correct fix for illiquid alts; every instrument here is orders of magnitude more liquid than the position |

Reproduction: `scratchpad/fetch_etf.py`, `scratchpad/trend_overlay_gate.py` (argv[1] = cost in bp).
Data: Yahoo chart API, free.
