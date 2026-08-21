---
name: project_fx_intraday_reversion_assessment
description: "Intraday FX assessment (2026-07-16): all 3 reversion mechanisms give no tradeable intraday edge on majors; only slow edges survive. CHF-cross slow-reversion is the lone lead."
metadata:
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

Assessed a GitHub/AI list of intraday FX ideas against this program's priors. Full doc:
`docs/intraday-fx-assessment-plan.md` (fx-strategy-framework repo). Data: IBKR 1h MIDPOINT, 7 majors
vs USD, 2y (2024-07→2026-07); cost ~1bp/side. **Intraday reversion line CLOSED — no tradeable intraday
edge on liquid majors:**
- **Currency-strength MOMENTUM rejected** — cross-sectional rank-IC uniformly NEGATIVE (t −3.5..−7.8,
  sign-stable both halves): strength REVERTS intraday, not persists.
- **Always-on cross-sectional reversion:** gross Sharpe 1.4–1.7 REAL, but cost-dominated — fastest nets
  −21 @1bp (5796 reb/yr); slowest (24h look/12–24h hold) net only +0.44/+0.49 @1bp, NEGATIVE @2bp.
- **Vol-spike selective reversion:** after |z|>2..3, forward fade is tiny (hit 51–54%, 0.5–1.7bp/event);
  every config net-negative after 2bp. Conditioning on extremes does NOT beat the spread.
- **Cointegration (21 pairs, Engle-Granger DF+half-life):** only EUR/CHF (t −4.52) & GBP/CHF (t −3.77)
  pass 5%, both CHF crosses (SNB artifact); half-lives 231h/299h = **~10–12 days, NOT intraday**.

- **Session breakout (London-open range break) — also failed:** continuation hit 48.7% @+3h (below
  coin-flip) / 51.4% session-end, <1bp/event, net-negative every exit. Session-conditioning doesn't
  rescue breakout. → EVERY testable intraday idea now run, all negative; plan fully closed.

**Meta-confirmation:** the ONLY edges in the whole FX+crypto program are SLOW/cross-sectional (monthly
carry — [[project_fx_em_carry_edge]]). Intraday directional AND reversion on majors are cost-dominated
(trend was negative even gross — [[project_fx_intraday_ibkr_track]]). Blocked-not-tested: VWAP (no FX
volume), news (no feed). Deferred: ML regime/meta-layers (need a base edge first).

**CHF-cross slow-reversion lead — CHASED + REFUTED (2026-07-16).** Built EUR/CHF & GBP/CHF daily from
FRED (1999–2026), tested BOTH raw-cross rolling-z AND proper rolling-β (no-look-ahead) cointegration
reversion, era-split across the 2011–15 SNB floor + Jan-2015 de-peg. Result: NO tradeable edge in any
modern free-float era — EUR-CHF Sharpe 0.11/0.07 (2016-26 / 2018-26), GBP-CHF 0.06/−0.01, all with
−11..−21% drawdowns and a de-peg tail (full-sample worst days −6.4%/−4.9%). The screen's DF significance
was an N=12k artifact + the SNB-floor stationarity (untradeable: tiny vol during peg, catastrophic
de-peg), exactly as flagged. GBP-CHF full-sample 0.38 is entirely pre-2016 (dead). **Lead closed — the
whole intraday+reversion FX line yields nothing; only slow cross-sectional carry survives.** Don't re-run.
