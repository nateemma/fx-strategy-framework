---
name: project_fx_carry_value_blend
description: "G10-spot factor stack caps ~Sharpe 0.33 (carry-dominated); value hedges the drawdown but doesn't lift Sharpe"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

2026-07-12: Built + hyperopt'd value (BIS REER deviation). Value best OOS Sharpe **0.084** (window=42/4/4), robust (IS-OOS gap -0.003). Ran a carry+value+momentum blend diagnostic on the **value-active window 1997-2026** (must clip: value trades 0.0/flat pre-REER-1994, and simulate returns 0.0 not NaN, so an un-clipped blend is diluted by pre-1994 zeros — a real confound to avoid).

**Findings (risk-parity, 1997-2026):**
- Correlations low/negative: carry↔value **-0.058**, carry↔mom -0.216, value↔mom -0.120. Genuinely independent factors.
- carry alone: Sharpe 0.332, Calmar 0.093, maxDD -27.4%.
- **carry+value: Sharpe 0.330 (UNCHANGED), Calmar 0.128 (+38%), maxDD -12.2% (HALVED).**
- momentum (daily): Sharpe -0.41 on recent window — craters the 3-way blend (0.057). Stays benched ([[project_fx_momentum_verdict]]).

**Interpretation:** Value adds **no Sharpe** (weak standalone + ~zero corr) but is a genuine **carry-crash hedge** — it's short the overvalued high-yielders carry crashes on, so it halves the drawdown / lifts Calmar. The hedge is somewhat concentrated in the 2008 carry crash (genuine but episode-heavy). Value = the **survivability / leverage-capacity leg**, not a return leg.

**Why it matters (updates [[project_fx_return_bar]]):** Both value and momentum came in ~0.06-0.08 vs literature ~0.35, so the projected "blend lifts Sharpe to ~0.46" **did NOT happen**. The **G10-spot cross-sectional factor stack caps ~Sharpe 0.33** (carry-dominated). Vol-targeted carry+value ≈ ~3.5-4% at 10% vol, or 8% only at ~20% vol / ~40% DD — **short of the 8-10% / Sharpe-0.8 bar with rank-and-basket factors alone.**

**How to apply:** Deployable core = **carry + value** (best Calmar, half the drawdown of carry-alone). The bar gets cleared NOT by more cross-sectional factors (that well is dry on G10 spot) but by: (1) the **ML carry-crash/vol overlay** (backlog #4 — already lifts carry 0.30→0.40, and enables safe leverage on the drawdown-hedged core); (2) **time-series trend** ([[project_fx_trend_queued]], crisis-alpha, different shape); (3) **EM carry** (wider differentials, crash/illiquidity risk). Don't build more rank-basket factors expecting a Sharpe lift. Diagnostic script was throwaway /tmp/blend_diag.py (clip to value-active window via `value_r.ne(0).idxmax()`).
