---
name: project_fx_trend_is_the_diversifier
description: Time-series trend is the missing piece — carry+trend ~doubles Sharpe (~0.5) and halves drawdown; clears the 8-10% bar
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

2026-07-13: Built + hyperopt'd time-series trend (`trend`/`trend_voltarget`; per-currency directional, signal_type a hyperopt Categorical over tsmom/ema/donchian). Merged to main (127 tests).

**Hyperopt (30 samples, train 2520/test 504):** best OOS **signal_type=ema, lookback=108, Sharpe 0.322**, Calmar 0.085, maxDD -23.9%, IS-OOS gap +0.085 (mild overfit). Donchian close 2nd (0.320); TSMOM didn't lead. **Trend standalone Sharpe 0.32 is comparable to carry and FAR stronger than momentum (0.03) / value (0.06)** — the first real non-carry factor.

**Blend diagnostic (risk-parity, /tmp/trend_blend.py):**
- corr(carry, trend) = **-0.096** (negative diversifier). All four mutually negatively correlated: carry-value -0.058, carry-trend -0.136, value-trend -0.110.
- carry+trend (1971-2026): **Sharpe 0.557, Calmar 0.168, maxDD -14.1%** vs carry 0.304/-27.4%. ~doubles Sharpe, halves drawdown. (Trend full-sample 0.409 is hyperopt-selected; honest OOS 0.322 → true blend ~0.46-0.55.)
- carry+value+trend (1997-2026): Sharpe 0.358, maxDD **-10.8%** (lowest).

**Why it matters:** Trend is the crisis-alpha that pays off when carry crashes (unlike momentum/value which were too weak to lift Sharpe — they only cushioned drawdown, see [[project_fx_carry_value_blend]]). **This clears the [[project_fx_return_bar]] 8-10% bar:** carry+trend at Sharpe ~0.5, vol-targeted and levered to ~15-18% vol (the -14% base DD gives room) → ~8-10% return. Value stays in for extra DD cushioning.

**How to apply:** The deployable answer is a **combined carry+trend(+value) blend, vol-targeted** — backlog #3 (combined factor portfolio), now strongly justified and the clear next build. Judge the blend OOS via walk-forward (the risk-parity numbers here are full-sample). Caveats: trend's 0.409 is hyperopt-selected (use ~0.32 OOS); FX trend decayed post-2008 → conservative forward expectations. Don't expect momentum to add (benched). EMA(108) won the signal bake-off; keep the Categorical for future re-tuning.
