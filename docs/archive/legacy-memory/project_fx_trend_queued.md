---
name: project_fx_trend_queued
description: Time-series trend-following queued as the next FX factor (after value/blend verdict)
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

2026-07-12: User approved building **time-series trend-following** as the next FX factor, after the value + carry+value-blend verdict is in. Prompted by a "top quant forex algorithms" list (retail/ATFX source, but carry + trend backbone is sound).

**Critical distinction:** time-series trend (trend-follow EACH pair on its own = absolute momentum, EMA/ADX/Donchian breakout) is a DIFFERENT factor from the CROSS-SECTIONAL momentum already built and benched ([[project_fx_momentum_verdict]], Sharpe ~0.07). The weak cross-sectional result does NOT condemn time-series trend.

**Why:** Time-series trend is the CTA staple (Moskowitz–Ooi–Pedersen "time-series momentum"), historically stronger in FX because it rides big **dollar** macro trends (2014–15, 2022) and is **crisis-alpha** — low/negative correlation to carry, positive convexity in dislocations. It's also the strongest answer to the original "what runs in a bear market instead of cash" question, and diversifies the carry/value book. Caveat: FX trend has decayed since ~2008 and needs volatility/large moves (bleeds in quiet ranges).

**How to apply:** When value/blend is judged, brainstorm→spec→build time-series trend as a `Strategy` (per-pair absolute-momentum / breakout signal; likely a directional or long/short-vs-dollar book, NOT the cross-sectional rank-and-basket shape). This is backlog #11 promoted. Judge on OOS Sharpe AND correlation-to-carry (its diversification value is the point, like value). Also on the retail list: single-pair RSI/Bollinger mean reversion = SKIP (win rate ≠ Sharpe, negative skew); pairs/cointegration stat-arb (AUD/NZD) = real but capacity-limited/crowded, different shape (bilateral spread) — a maybe-later, see [[project_xsectional_reversion]].
