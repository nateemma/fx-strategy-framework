# Intraday FX Strategy Assessment Plan

Staged, cost-first assessment of a set of candidate intraday FX approaches, filtered through
this environment's proven priors. Created 2026-07-16.

## The lens: what this environment has already established

- **Intraday (15-min) directional is a cost-dominated loser here.** ema/tsmom/donchian at 15-min
  were *every* config negative Sharpe (−1.9 to −20.5), worse at shorter lookbacks. 15-min FX ≈
  random walk after spread. (`project_fx_intraday_ibkr_track`)
- **The one deployable edge is cross-sectional and slow** — rank-by-yield carry, monthly. Rank-based
  long/short is what survives. (`project_fx_em_carry_edge`)
- **Shorting is native in FX** (short EUR/USD = long USD) — removes the wall that killed every crypto
  spot stat-arb idea. Biggest reason some ideas are *more* testable here than in the crypto work.
- **Distant-era validation is non-negotiable** — an effect holding in two adjacent windows but
  flipping in a third is our standard failure mode (the day-of-week lesson).
- **Data on hand:** IBKR intraday MIDPOINT bars (prices only — *no real volume*; FX is OTC), FRED
  daily. **No news feed, no order flow.**
- **Annualize intraday with `bars_per_year`, NOT ×252** (the framework `metrics` hardcode 252).

## Idea triage

| # | Idea | Verdict | Rationale |
|---|---|---|---|
| 5 / ML1 | Currency-strength ranking | **Test first** | Cross-sectional rank = the only thing that works here; native to our per-currency USD panel. |
| 2 | Mean-reversion after vol spike | Test | FX intraday genuinely mean-reverts; testable on price alone (2 ATR + RSI extreme). |
| 9 | Cointegration / stat-arb | Test | Robust version of lead-lag; shorting available; majors liquid. Needs half-life/ADF + distant-era. |
| 8 | Correlation lead-lag | Low prior | We ran this (BTC→alt): coincident, not leading. Subsumed by #9 (the residual is the real question). |
| 1 / 3 / 10 | Session / vol-expansion breakout | One conditioned test each | Our negative was *unconditioned* trend; session-conditioning is the untested wrinkle, low expectation. |
| 6 | HTF-bias trend pullback | Low prior | Counter to "always-on beats timed"; only the pullback-entry is novel. |
| 7 | VWAP reversion | **Blocked (data)** | Needs real volume; IBKR FX has none. Cannot build honestly. |
| 4 | News trading | **Infeasible** | No news feed, sub-second latency, not cleanly backtestable. |
| ML2/3/4 | Regime / prob-forecast / meta-model | **Defer** | Meta-layers needing ≥2 base edges first. Prob-forecast is NNPredict re-framed (quality decouples from P&L). |

## Primary horizon

**1h is primary** — far enough from the spread-dominated 15-min regime where we already found nothing,
while still intraday. 15-min kept as a secondary/robustness cut.

## Phased plan (cheap gates first)

### Phase 0 — Data + harness  ← IN PROGRESS
- [ ] Fetch multi-year intraday panel for the 8 majors (per-currency vs USD: EUR, GBP, JPY, CHF, CAD,
      AUD, NZD) — 1h (primary, ≥2y) and 15-min (secondary, ≥1y) MIDPOINT bars via `fetch_intraday`,
      cached to `data_cache/ibkr/`.
- [ ] Confirm span/bar-count per code; note IBKR history caps.
- [ ] Session-tag helper: label each bar Asian / London / NY / overlap by UTC hour.
- [ ] Pin an honest cost model (majors ~0.5–1 pip spread), expressed in bps for the framework.

### Phase 1 — Cost-blind signal checks (kills most before any backtest)
- **Currency strength — DONE 2026-07-16 (1h, 2y, 7 majors).** Cross-sectional rank-IC is *uniformly
  negative* (t −3.5..−7.8), sign-stable across both year-halves → strength **reverts, not persists**.
  Momentum premise REJECTED; signal is cross-sectional reversion. Phase-2 cost taste: gross Sharpe
  1.4–1.7 but cost-dominated at 1h — fast versions net −21 (5796 reb/yr); slowest (24h look / 12–24h
  hold) net only +0.44/+0.49 @1bp and NEGATIVE @2bp. **Always-on cross-sectional reversion is too
  turnover-heavy to survive realistic cost.** → pivot to *selective* reversion (below).
- **Vol-spike reversion — DONE 2026-07-16 (1h, 2y).** After a standardized extreme move (|z|>2..3
  over a 48h vol window), forward fade return is tiny: hit-rate 51–54%, mean 0.5–1.7 bp/event. **Every
  config net-NEGATIVE after 2bp** (best: relative thr=3/h=24 = +1.66bp, −0.34 net). Conditioning on
  extremes does NOT sharpen the reversion above the spread. Selective reversion FAILS the cost gate too.
  → two reversion mechanisms now sub-cost at 1h; the 1h dislocation is smaller than the round-trip spread.
- **Cointegration — DONE 2026-07-16 (1h, 2y, 21 major pairs, Engle-Granger DF + half-life).** Only 2/21
  pass EG 5%: EUR/CHF (t −4.52) and GBP/CHF (t −3.77) — both CHF crosses (SNB-management artifact), not a
  general property. Their half-lives are 231h / 299h = **10–12 DAYS, not intraday**. No intraday
  cointegration edge. (DF significance is largely N=12k; ρ≈−0.003/hr is economically weak.)

## CONCLUSION — intraday reversion line CLOSED (2026-07-16)
All three reversion mechanisms give NO tradeable intraday edge on majors: (1) always-on cross-sectional
— gross 1.7 Sharpe, net-negative at cost; (2) vol-spike selective — sub-spread per event; (3)
cointegration — exists only in CHF crosses, reverts over ~10 days. Fully consistent with the program:
the only FX edges here are SLOW (monthly carry). Intraday on liquid majors is cost-dominated.

**Lead (non-intraday):** EUR/CHF & GBP/CHF show weak/slow mean-reversion (~10-day half-life, amplitude
≫ cost) — a candidate for a SLOW swing strategy in the "slow wins" family, NOT intraday. Caveats: CHF-
concentrated (2 pairs), likely SNB artifact, in-sample β, 2024–26 only → needs distant-era (pre-2024)
validation + de-concentration scrutiny before it is more than a lead.

**Not pursued:** session-conditioned breakout (low prior given 3/3 reversion + prior trend negative);
ML meta-layers (deferred — need a base edge first). VWAP (no volume) and news (no feed) remain blocked.

### Phase 2 — Cost-aware backtest
Framework `backtest` with the Phase-0 spread on Phase-1 survivors only.

### Phase 3 — Distant-era + walk-forward
≥3 temporally-separated windows, judged on **walk-forward P&L**, not in-sample metrics.

## Priority order
currency-strength → vol-spike reversion → cointegration → (one) session-conditioned breakout.

**Honest expectation:** the cross-sectional ideas (currency-strength, cointegration) are the real EV;
the intraday-directional ones are tested mainly to confirm/deny with the session wrinkle, at low prior.
