---
name: project_fx_cot_positioning
description: "CFTC COT positioning is the FIRST non-price edge in the whole program — contrarian, modern-era Sharpe ~0.7-0.8, cost-robust, uncorrelated to carry. Caveat: modern-only (flips negative pre-2010)."
metadata:
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

**CFTC COT speculative positioning = the first working NON-PRICE lever in the entire FX+crypto program**
(2026-07-16). Every price/factor edge was exhausted (G10 factors dry, ML-vol lost to EWMA, intraday
dead — [[project_fx_intraday_reversion_assessment]]); COT is the first to clear the bar on non-price info.

**Loader:** `forex/data/cftc.py` `load_cot(contract_code)` — CFTC Socrata legacy futures-only report
(dataset 6dca-aqww, FREE, no key), weekly net non-commercial = noncomm_long − noncomm_short, cache-first
parquet, injectable client. Keyed on stable `cftc_contract_market_code` (contract NAMES change across
history: CME↔IMM). `COT_CODES` maps EUR/JPY/GBP/CHF/CAD/AUD/NZD/MXN/ZAR (PLN/HUF/CZK/ILS have no CME
contract → overlay covers G10+MXN+ZAR only). Deep history (majors to 1986). Committed 1759398.

**Signal = contrarian** (fade crowding): 3yr rolling z of net-spec, release-lagged 1wk, sign flipped.
Cross-sectional over the 9. **Phase-2 backtest (weekly, cost-aware):**
- 2018–26: Sharpe **0.71 @4bp / −6% DD** (0.83 gross, 0.77 @2bp, 0.58 @8bp) — cost-robust to ~8–15bp,
  turnover 11×/yr.
- 2010–26: 0.35–0.42 @realistic cost.
- **Uncorrelated to carry (ρ=0.05)** → genuine diversifier for the deployable EM-carry book.

**CAVEAT (real):** modern-ONLY. Forward-return corr flips NEGATIVE in 2000–09 (−0.44 Sharpe; crowding
CONTINUED, not reverted), flat 2010–17, strong only 2018+ (~8yr). Like carry it's an in-regime edge, not
multi-decade robust. The blend with a *diluted 9-ccy carry proxy* looked weak only because that proxy is
dead modern (0.01) — the REAL test is COT + [[project_fx_em_carry_edge]] (both ~0.7-0.8, uncorrelated).

**BLEND WITH REAL DEPLOYABLE BOOK = DECISIVE WIN (2026-07-16).** carry sleeve (real TRADEABLE_CARRY via
build_carry_view, IBKR-daily) + COT sleeve (9 covered ccy), return-level blend, corr −0.01/0.06:
equal-risk mix **Sharpe 0.74→1.05 (full 2015-26) / 0.85→1.06 (2018-26); maxDD −17.8%→−4.8%; Calmar
0.36→0.73**. Lower annRet (6.5%→3.5%) is a DE-LEVER artifact — Sharpe/Calmar scale-free; levered to
carry's ~9% vol the blend gives ~40% more return at same risk + 1/3 the DD. The COT overlay is the single
biggest risk-adjusted improvement to the deployable book found in the program.

**FRAMEWORK STRATEGY BUILT (2026-07-16, commit 302fdf1).** `carry_cot` = risk-parity blend of
`carry` + `positioning` (`strategies/blend.py` CarryCot); `PositioningStrategy` (contrarian dollar-neutral
continuous weights over COT-covered ccy, graceful zero-fallback when uncovered); `forex/features/
positioning.py` (−1×rolling-z, publication-lagged, as-of joined); `DataView.positioning` field;
`build_carry_view(..., with_positioning=True)` auto-loads COT. Discoverable: `positioning` (standalone),
`carry_cot` (blend). Reproduces: `carry_cot` vs `carry` (2018-26, 5bp) Sharpe 0.85→1.03, maxDD
−17.8%→−4.1%, Calmar 0.39→0.87 (full-period Sharpe muted 0.74→0.76 — BlendStrategy dynamic EWMA
risk-parity dilutes over pre-2018 low-signal years, but DD still halves). 238 tests pass.

**WALK-FORWARD VALIDATED (2026-07-16) — carry_cot is the new deployable book.** OOS (train 750d/test
250d, 8 windows, 5bp): carry_cot Sharpe **0.96 vs carry 0.82**, Calmar **0.84 vs 0.38**, maxDD **−4.1% vs
−17.8%**. Per-window carry_cot=[1.02,0.55,1.53,0.99,1.98,−0.21,0.40,1.75] far more consistent than
carry=[0.55,−0.69,1.47,0.47,2.53,0.76,−0.13,2.66] — turns carry's losing windows positive; only gives up
upside in carry's 3 strongest windows (risk-parity de-risk, expected). CLEAN OOS: params fixed generic
defaults (window=156, lag_days=6), fit() no-op, risk-parity causal → no per-window fitting, no overfit.

**REGIME CONDITIONING (#5) DIAGNOSED → REJECTED (2026-07-16).** Does a macro risk-off gate (VIX/credit
top-tercile) help carry? The regime→carry relationship FLIPS: long G10 history (has crashes) risk-off =
carry CRASHES (2008 −20% all risk-off days → gate helps); deployable EM window (2015-26, no crash) risk-off
= carry's BEST (Sharpe risk-OFF 1.19 vs ON 0.45; carry_cot 1.67 vs 0.23 → gate CUTS the best periods). So a
de-risking gate is return-harmful in-regime (vol-target failure again, "always-on beats timed"), tail-
protective only vs crashes this window can't validate, REDUNDANT (carry_cot diversification already cut DD
−17.8%→−4.1%), and built on a sign-flipping/era-unstable relationship (ML would overfit). Crash protection =
diversification, not a timed gate. Don't build the conditioning overlay. See [[project_fx_always_on_beats_timed]].

**BEST BOOK = `carry_cot_mom` @ 252d (2026-07-16, commit 8ec9c74).** Added a 3rd sleeve: carry-momentum
(basket on the 12-month CHANGE in the rate differential — is carry widening?), orthogonal to carry (0.04)
AND COT (−0.16). Lookback ROBUSTNESS-validated (swept 63-378d: broad plateau 189-378d, 63d too noisy;
252d = mid-plateau canonical 12mo horizon, principled not sweep-chased). WF (750/250, 5bp): **carry_cot_mom
Sharpe 1.15 / Calmar 1.03 / maxDD −2.9%** vs carry_cot 0.96/0.84/−4.1% vs carry 0.82/0.38/−17.8% — dominates
on every metric. `strategies/carrymom.py` + `CarryCotMom` blend. Value REJECTED (0.39-redundant with COT);
momentum ADDED (orthogonal). Deepened-COT/cross-market/regime/NLP all closed-negative (see backlog).

**FACTOR-SEARCH SYNTHESIS (the durable rule):** carry is the DOMINANT axis; additive edge comes ONLY from
signals ORTHOGONAL to carry. WORKED (in the book): COT positioning (corr 0.09), carry-momentum (0.03).
REJECTED as carry-REDUNDANT: value (0.39 vs COT), yield-curve slope (carry-corr, wrong sign), skewness
(0.41 vs carry) — all carry in disguise, each DILUTES the book. REJECTED as PRICED: regime conditioning,
central-bank NLP (FOMC tone lexicon works but tone→FX is priced, sell-the-news), intraday everything.
**Rule for any future factor: check return-correlation to carry FIRST.** Full ledger: docs/strategy-
research-backlog.md.

**DEPLOYED ON IBKR PAPER + SELF-TRACKING FORWARD TRACK (2026-07-17).** carry_cot_mom placed on paper acct
DUQ218063 (NAV ~$994k, 13 legs; baseline 2026-07-17) via the validated CLI path — first live-path placement
of the blend, all guards + odd-lot warning + min-order skip worked. Infra (all committed/pushed, origin/main
@ 8fed3c3): `scripts/monthly_paper_rebalance.sh` (refreshes IBKR spot + FRED rates + CFTC COT via
`refresh_track_data.py`, then places; reconciles — turnover 0.756→0.015 validated), `scripts/snapshot_nav.py`
→ nav.csv (daily NAV equity curve; FX = cash so track NetLiquidation, GrossPositionValue=0),
`scripts/track_report.py` (return/Sharpe/DD vs the ~1.15 backtest), `scripts/install_schedules.sh`
(one-command launchd install: monthly rebalance 1st 09:00 + daily NAV snapshot 21:00, bakes $FRED_API_KEY).
Doc: docs/scheduled-paper-track.md. Both launchd agents installed + test-fired OK. **Monthly reminder trigger
`trig_0129htofdRrG6PFb6KtcxZmy`** fires 2nd of month 09:30 UTC → fresh session runs track_report + pushes a
summary. GOTCHA: launchd can't see .zshrc, so FRED_API_KEY is baked into the plist (installer handles it).
Diffuse 3-sleeve book has flippy MARGINAL legs (NZD/ILS/AUD churn on each refresh; NZD/ZAR often skipped
sub-min-order ~1.5% NAV unhedged) — conviction legs stable; a min-weight floor is a possible future cleanup.

**REMAINING (deliberately not done):** the LIVE (real-money) gate — allow_live + U-account + live port — is
a separate future decision; judge the paper track on realized Sharpe vs ~1.15 after MONTHS first. Data-gated
research threads still open: macro-surprise (#8, needs consensus feed), FX options VRP (#9, IBKR options
history too thin), cross-currency basis (orthogonal candidate, data hard). Don't re-run any closed check.
