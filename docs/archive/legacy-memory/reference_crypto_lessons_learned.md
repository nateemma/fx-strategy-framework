---
name: Lessons carried over from the crypto/freqtrade program (methodology + hard-won findings)
description: The transferable methodology and empirical lessons from the prior crypto ML trading program (freqtrade repo). Read this at the start of any FX-modeling work — it encodes what actually works (regime/structural interventions, distant-window validation, point-in-time causality, judge on P&L) and the traps (price-only ceiling, learnability != edge, phantom fills, fill-model artifacts flipping conclusions). Full detail lives in the freqtrade project's memory and us_spot_market_study.md.
metadata:
  node_type: memory
  type: reference
---

Context: the user ran a long, rigorous crypto ML trading program (freqtrade repo at
`~/Documents/freqtrade`, strategies under `user_data/strategies/`). The FX project
(`~/Documents/forex`) is a deliberate pivot that reuses that program's METHODOLOGY and is
motivated by its FINDINGS. Full detail: the freqtrade project memory dir
`/Users/philprice95/.claude/projects/-Users-philprice95-Documents-freqtrade/memory/` and the
summary doc `~/Documents/freqtrade/user_data/strategies/us_spot_market_study.md`.

## Methodology that transfers 1:1 (use it here)
- **Judge on out-of-sample P&L / risk-adjusted return, NEVER on model accuracy.** Learnability
  (high MCC/ρ/R²) repeatedly did NOT equal a profitable trade after stops, fees, and execution.
  The highest-learnability configs often traded worse.
- **Distant-window validation is load-bearing.** Two ADJACENT walk-forward windows share a regime
  and give false persistence. Always validate on a temporally-DISTANT era before believing an edge.
  This killed a day-of-week "effect" and a stop-tuning "win", and is the ONLY reason the funding
  signal earned credibility (it didn't flip across 2024/25/26). The forex plan bakes this in.
- **Point-in-time causality.** Every signal must use only data available at that timestamp. In crypto
  this was causal lagging of daily→intraday; in FX it's release-date stamping of macro data (CPI
  lags weeks, COT is Friday-for-Tuesday). The forex data layer's `asof_join(pub_lag_days)` enforces it.
- **Model phantom fills BEFORE trusting any backtest.** Standard backtests fill at candle price
  regardless of volume. Liquidity-aware sizing (cap to a fraction of candle volume, reject dust)
  deflated crypto results massively: FundingCarry +23.7% -> +6.6% (~73% of trades un-fillable);
  cross-sectional reversion was ~92% one illiquid coin and a liquid-only subset LOST money.
- **Staged cheap-gates.** signal-check -> cheap retrain -> full expensive chain. Don't spend deep
  compute on an idea that fails a 5-minute check. The FX plan gates each strategy phase this way.
- **Backtest ≡ live parity.** The live signal path must be byte-identical logic to the backtest.
  A crypto `config.json` timeframe silently overrode the strategy attribute (15m ran where 1h was
  intended). For FX, the `ib_async` execution client must share the backtest's signal code path.

## Empirical findings that MOTIVATE the FX pivot
- **OHLCV price-only prediction has a hard information ceiling (Spearman ρ≈0.15).** Hand-crafted
  indicators, an 85-indicator battery, AND learned CNNs on raw OHLCV all converged on the same
  ceiling — it's an information limit, not a modeling failure. You cannot out-model it on the same
  inputs. **The only lever is NEW information (order flow, funding, macro), not a better model.**
  => In FX: do NOT predict major-FX direction from price/TA (an even more efficient market). Use
  rates/macro/positioning/vol. This is the single most important carry-over.
- **Every crypto strategy family reduced to ZEC** — one illiquid alt's rare violent pumps were the
  ONLY real alpha across mean-reversion, funding, cross-sectional reversion, and momentum. The edge
  was concentration + illiquidity, not the strategy. "Edge lives where you cannot cheaply trade."
  => FX majors are deeply liquid, so this wall is far weaker — a reason the pivot is attractive.
- **US-spot structural walls:** no shorting, thin liquidity, OHLCV-only. The genuinely attractive
  edges (funding-reversion, market-neutral spreads) are market-neutral and need a leverage/short
  venue. IBKR spot/FX + the carry trade sidesteps some of this; the market-neutral versions still
  want shorting (perps/futures).
- **Survivorship bias inflates magnitude.** Current-survivor universes overstate returns; crypto
  momentum's headline leaned on it. FX majors are NOT survivorship-biased (persistent instruments,
  decades of clean data) — another reason the pivot is sound.

## Traps that cost real time (avoid re-learning)
- **Fill-model artifacts can FLIP a conclusion.** A "-17% catastrophic" momentum result was a pure
  artifact of single-candle fillability + phantom turnover fees; corrected (accumulate fills over the
  hold window, fees on real trades) it was +114%. LESSON: reason carefully about your OWN backtest
  accounting; a surprising result is often a bug in the simulator, not the market.
- **Bias tools false-positive on external-data / cross-sectional strategies.** freqtrade
  `lookahead-analysis` flagged a causal strategy because it read files directly (bypassing the
  DataProvider). PROVE causality with a truncation-invariance test (recompute the signal on data cut
  at t, diff the overlap = zero) rather than trusting the tool.
- **More features / bigger models made OOS WORSE** on low-SNR targets — flexibility buys overfitting,
  not edge. Prefer parsimony; add capacity only when it demonstrably helps OOS.
- **The wins were STRUCTURAL/regime interventions, not better predictors.** A BTC>SMA regime gate and
  a per-coin trend filter improved risk-adjusted returns; direction-prediction levers all failed.
  => In FX, the flagship is a carry strategy with an ML CRASH-AVOIDANCE overlay (a regime/risk model),
  NOT an FX direction predictor. This mirrors what actually worked.

## Behavioral preferences (the user has corrected these repeatedly)
- When diagnostics show a problem, answer "what would FIX it", not "should we abandon the approach".
- Present options once, then implement what's chosen — don't relitigate.
- Diagnose before tuning: print what the model/backtest is actually doing before changing knobs.
- No instrument-specific hardcoded constants/branches; underperformers get structural fixes.

## Rare, real signal worth remembering (crypto Study 7)
Funding-rate reversion was the ONE orthogonal signal that survived distant-era validation
(era-persistent +0.6..0.8pp) — a NON-price data source. It underperformed on US spot only because of
long-only beta + illiquidity, not because the signal was false. The FX analog (carry, and a
crash-avoidance overlay on it) is the seed of the current project.
