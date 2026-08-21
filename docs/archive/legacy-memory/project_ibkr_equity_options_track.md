---
name: project_ibkr_equity_options_track
description: "IBKR equity/ETF/options track — staged feasibility sprint for a ~10%-at-controlled-risk engine. Gate #1 (options VRP income) FAILED: it's equity-lite, not low-risk. Basket/cross-asset/factors gates pending."
metadata:
  node_type: memory
  type: project
  originSessionId: e1399a6e-effc-415c-9b11-ad051d604f86
---

**Third IBKR-adjacent investigation (2026-07-17): what OTHER IBKR offerings can generate ~10% at
CONTROLLED risk?** After crypto ([[project_ibkr_crypto_derivatives_track]]) and commodities
([[project_commodities_track]]) both closed negative. Goal = ~10% return, drawdown materially below equity's
(target <~15-20%), alive in the modern/deployment regime. Staged free-data gate per candidate, then deep-dive
survivors. 4 candidates, ordered: (1) options VRP income, (2) diversified rebalanced ETF basket [user's idea],
(3) cross-asset trend/carry via futures, (4) systematic equity factors.

**KEY BAR DECISION (user push, 2026-07-17):** orthogonality-to-the-FX-book is NOT a pass/fail gate — a
strategy that clears the STANDALONE bar earns its place regardless of FX correlation (demoted to a Phase-2
sizing/tiebreaker bonus). The correlation that matters for the RISK goal is **to equity beta / the S&P**
(is the low drawdown real, or untested crash exposure?) and among the surviving sleeves themselves.

**GATE #1 — OPTIONS VRP INCOME = FAILED (2026-07-17).** Free CBOE benchmark strategy indices via Yahoo
(^PUT put-write, ^BXM buy-write; ^BXMD/^BXY/^CLL/^CNDR NOT on Yahoo — need CBOE CSVs). PUT/BXM 30yr history.
- Modern regime it LAGS equity on return AND Sharpe: RECENT15+ PUT 8.0%/Sh0.52, BXM 7.4%/Sh0.62 vs S&P-TR
  13.8%/Sh0.82. The "put-write beats S&P risk-adjusted" story is a 2000s twin-crash ARTIFACT (2000s: PUT
  +4.8%/Sh0.39 vs S&P −0.9%/Sh0.07); in the 2010s+ bull, capping upside to collect premium just costs return.
- NOT low-risk: maxDD −37% (PUT) / −40% (BXM); corr to S&P 0.81/0.88. It's EQUITY-LITE (beta + short-vol
  overlay), not an uncorrelated low-risk engine — bleeds in the crashes you're avoiding.
- STRUCTURAL (why no cleverness fixes it): the vol-risk-premium IS payment for bearing crash risk — can't
  collect ~10% of it AND avoid the tail (same coin). Harvest fully → ~8%/−40%DD; collar the tail (CLL) →
  ~5-6%/lower DD. No ~10%-at-low-risk point on the short-vol curve. The one lever (sell vol only when rich) =
  TIMING, which is a program-law loser ([[project_fx_always_on_beats_timed]]).
- Silver lining: VRP shines in high-vol/CRISIS regimes (2000s) → legitimate conditional/crisis diversifier,
  NOT a primary ~10% engine. Script: scratchpad `vrp_gate.py`.

**GATE #2 — DIVERSIFIED REBALANCED BASKET = PARTIAL PASS (low-risk ~7% engine; NOT 10%-at-low-risk).**
Total-return (adjusted-close) ETF backtest, quarterly rebal, exact units mechanic, common 2007-26 window.
Script: scratchpad `basket_gate.py`.
- **User's literal EW-SECTORS idea gives ZERO risk reduction:** 9 sector SPDRs equal-weight → CAGR 10.2% but
  vol 18.6%, maxDD −52%, corr-to-S&P **0.99**. It's just the S&P (small-cap tilt). Diversification must come
  from ASSET CLASSES, not equity sectors. Killed.
- **Cross-asset baskets are a real win but ~7% not 10%:** all-weather (30SPY/40TLT/15IEF/7.5GLD/7.5DBC),
  RP inverse-vol [SPY,TLT,IEF,GLD,DBC], EW-4 [SPY,TLT,GLD,DBC] → Sharpe **0.74-0.82 (beats equity 0.63)**,
  maxDD **~−25% (half of equity's −55%)**, equity-corr **0.44-0.51** (genuinely diversifying + would diversify
  the FX book). Held up in 2008 (all-weather −15%, RP −23% vs SPY −52%). But UNLEVERED CAGR only 6.9-7.6%.
- **10%-at-low-risk FAILS:** to reach 10% needs ~1.4x leverage → drawdown back to ~−35% (equity-like) + ~5%
  borrow drag. Same return/risk-are-linked tension as VRP, milder. Best variants = RP / EW-4 (highest recent
  Sharpe ~0.9, most 2022-robust).
- **2022 caveat (honest):** stocks+bonds fell together → ALL baskets hurt, all-weather WORST (−20%, heavy long
  bonds). Stock-bond diversification is regime-dependent; commodity/gold inclusion (RP, EW-4 at −13%) more robust.

**KEY EMERGING INSIGHT (after 2 gates):** NO single premium gives "10% without huge risk" — 10% IS a risk
premium. Path to ~10%-at-CONTROLLED-risk = COMBINE uncorrelated ~0.8-Sharpe sleeves + modest leverage. User
already owns a perfect ingredient: carry_cot_mom (Sharpe ~1.15, ~ZERO equity corr). Basket (0.8 Sharpe, 0.45
equity-corr) + FX book (uncorr to stocks AND basket) → blend could hit ~10% at LOWER DD than either alone.
"Portfolio Sharpe is the bar" ([[project_fx_return_bar]]) cashing out. The RP/EW-4 basket is a CONFIRMED
low-corr sleeve worth keeping regardless.

**GATE #3 — CROSS-ASSET TREND = FAIL standalone (2026-07-17).** 10-ETF diversified TSMOM (SPY/EFA/EEM/TLT/
IEF/DBC/GLD/VNQ/HYG/LQD), 12mo signal, vol-targeted L/S, weekly, script `trend_gate.py`. GENUINELY uncorr to
equities (−0.03 full / +0.06 recent) and POSITIVE in 2008 (+2.9% vs SPY −25.6%) — real crisis alpha. BUT
standalone DEAD modern (RECENT15+ CAGR 0.1%, Sharpe 0.05) and WHIPSAWED −32% in COVID H1-2020 (12mo signal
can't handle a 5-wk V-crash). Its crisis job is already done — better, no whipsaw — by the bonds/gold INSIDE
the gate-#2 basket, so no separate slot. (Caveat: real LEVERED managed-futures did far better in 2022 via
short bond futures; unlevered ETF proxy understates that — but modern standalone return still ~0.)

**GATE #4 — EQUITY FACTORS = FAIL (2026-07-17).** Ken French free factor library (1963-2026, gold standard),
market-neutral factors, script `factor_gate.py`. Premia DECAYED post-2010: diversified 5-factor combo Sharpe
~1.0-1.2 pre-2010 → **0.10 (2010s) / 0.03 (RECENT15+)**. Only MOM (0.27-0.34) & RMW/quality (0.25-0.27) faintly
alive; HML/value DIED (−0.30 in 2010s), CMA/SMB dead-negative. Market-neutral IS low-corr (−0.14 recent) but
NO modern return. Long-only factor ETFs (MTUM/VLUE/QUAL) = Mkt+tilt = equity beta (~0.95 corr, −50% DD) =
fails 'low risk' like EW-sectors. (Combo CAGR/DD printed garbage = unit-std scaling artifact; Sharpes valid.)

**EXPANDED-BASKET TEST (2026-07-17, script `basket_expanded.py`):** user asked to add TIPS/EMbonds/REIT/intl +
US size/style/growth-dividend/foreign equity baskets. FINDINGS: (A) all-equity style-diversified basket
(large/mid/small/value/growth/div/foreign/EM/REIT) = **just the S&P** (0.97 corr, −55% DD) — diversifying
WITHIN equities does nothing. (B) COUNTERINTUITIVE: adding "more asset classes" (EMbonds/REIT/intl) to the RP
basket made it WORSE (corr 0.48→0.75, DD −21%→−30%) because EMbonds/REIT/foreign-equity are equity-correlated
— more tickers ≠ diversification; it's uncorrelated RISK that matters (govt bonds, gold, trend), not ticker
count. (C) The simple tight risk-WEIGHTED 5-asset basket [SPY,TLT,IEF,GLD,DBC inverse-vol] stays the winner
(Sharpe 0.80, −21% DD, +9.9% COVID). Managed-futures sleeve = modest tail help (best 2022) but return drag +
COVID whipsaw. Dollar-weighting toward equity (60/40 style) keeps corr 0.90 — must RISK-weight, not dollar-weight.

**MOMENTUM-ROTATION TEST (2026-07-17, script `momentum_rotation.py`) — the crypto-basket analog, user's "last
idea".** Relative-strength + dual-momentum rotation across 12 asset-class ETFs. Real strategy (~6-7%, Sharpe
0.6, −21% DD, 0.5 equity-corr) but does NOT beat the RP basket (Sharpe 0.6 < 0.80) and lagged modern bull.
CRITICAL: the crypto winning ingredient — FREQUENT rebalance — HURTS on liquid ETFs (weekly Sharpe 0.54 <
monthly 0.61, whipsaw); confirms the crypto result was survivorship + illiquid-alt concentration + extreme
dispersion, none of which exist in efficient ETFs (the edge was the MARKET, not the rotation). Nugget:
CONCENTRATED dual-mom top-1 is very uncorrelated (0.24) and printed +21% in 2022 (rotated to energy) — a
higher-octane crisis-alpha diversifier, but standalone weak (Sharpe 0.43, −33% DD).

**INVESTIGATION COMPLETE — VERDICT (2026-07-17): no single strategy gives '~10% without huge risk' (10% IS a
risk premium). Only survivor across 5 candidates = the DIVERSIFIED RISK-PARITY BASKET [SPY,TLT,IEF,GLD,DBC
inverse-vol] (Sharpe 0.8, −21% DD, 0.48 equity-corr) as a low-risk ~6-7% sleeve. Ranking: basket (PASS) >>
momentum-rotation (works, ~0.6, doesn't beat basket) >> VRP/trend/factors (FAIL).**

**COMBINATION TEST DONE (2026-07-17) — THE ANSWER, and it WORKS. Script `combination_test.py`.** Real
carry_cot_mom daily returns from the forex backtest engine (`backtest(...,5bp)` → Result.returns) + RP basket
[SPY,TLT,IEF,GLD,DBC inverse-vol], common window 2015-10→2026-07. FX 3.1%/2.6%vol/Sh1.22/−2.9%DD; basket
8.9%/9.1%vol/Sh0.98/−19%DD; **corr +0.09** (≈uncorrelated). Equal-risk blend (each→10%vol, 50/50):
**11.0% ret / 7.4% vol / Sharpe 1.48 / −8.7% DD.** Scaled to ~10% CAGR: **10.3% / 6.6% vol / Sharpe 1.54 /
−8.1% DD, EVERY full year positive (worst −1.2%), +3% in 2022** (vs SPY −18%). = "~10% without huge risk",
by COMBINATION not a single strategy — ~75% of equity return at ~1/4 the drawdown, ~2× the Sharpe.
CAVEATS: window 2015-26 (no 2008; FX spot history limit); FX Sharpe 1.22 in-sample (WF 1.15) so blend ~1.4
honest; leverage concentrated in FX sleeve (~3.8x its 2.6% natural vol — normal for low-vol FX carry), basket
~unlevered, portfolio-level ~1x. WALK-FORWARD confirmed (2026-07-17): OOS FX Sharpe 1.14, blend Sharpe 1.52 /
10.5% CAGR / −7.3% DD / every year non-negative. Findings doc COMMITTED: `docs/ibkr-alternative-strategies-
findings.md` (main @ 66d2575).

**BASKET SLEEVE BUILT + DEPLOYED LIVE ON PAPER (2026-07-17), merged to main @ 27d357c.** Subagent-driven build
(impl/basket-sleeve, haiku impl / sonnet review / opus final review, 3 tasks + hardening, 274 tests pass, ff-
merged). New code: `forex/run/basket_weights.py` (inverse_vol_weights + target_shares, pure), `forex/run/
basket.py` (`BasketExecution` — long-only Stock/SMART executor mirroring LiveExecution's guards: confirm-to-
place, DU-account check, per-order-cap PRE-PASS max_order_frac=0.6, min_order_usd skip, reconcile-by-conId
anti-overtrade, best-effort rollback that never raises), `forex/run/basket_track.py` (per-sleeve CSV log),
`scripts/basket_rebalance.py`/`.sh` (runner, default PREVIEW, --confirm arms), `docs/basket-sleeve.md`.
Universe [SPY,TLT,IEF,GLD,DBC] inverse-vol, $400k, quarterly. **LIVE-VALIDATED on paper acct DUQ218063 (port
4002):** preview → $10k test (all 5 filled) → $400k reconciled UP from the $10k (orders=target−current, NOT
doubling → anti-overtrade confirmed live) → positions verified (SPY87/TLT1123/IEF1757/GLD96/DBC1385,
GrossPositionValue $399,855). Buying power ample ($964k avail, FX book ties up only $21k margin, reports as
cash). Opus final review: NO Critical (placement path sound); #4 reconcile-sleep(1.5) kept consistent with
validated FX pattern (confirmed live). NOT pushed to origin (local main only). FOLLOW-UPS: (1) quarterly
launchd schedule for basket_rebalance.sh (parallel to FX monthly); (2) tracking nuance — snapshot_nav.py now
captures COMBINED NAV incl. ETFs (GrossPositionValue no longer 0); track_report attributes to FX book, so
per-sleeve attribution needs the new basket_positions.csv. **INFRA DONE (2026-07-17):** pushed to origin/main (@ 20fb5d7); **quarterly basket rebalance SCHEDULED** —
`scripts/quarterly_basket_rebalance.sh` (--confirm --allocation 400000, reconcile-only, no FRED key) wired
into `install_schedules.sh` as launchd `com.fx.basket-rebalance` (1st of Jan/Apr/Jul/Oct 09:30, offset from FX
monthly 09:00); installed + plist-validated + loaded.

**INCOME-SUSTAINABILITY GATE RUN (2026-07-17) — user goal = ~10% CASH income WITHOUT eroding principal
(option a).** Script scratchpad `income_gate.py`: split each income vehicle's total return (Yahoo adjclose)
from its price path (close) to separate REAL income from RETURN-OF-CAPITAL. RULE CONFIRMED: sustainable cash
draw ≈ TOTAL RETURN; any fund distributing > its TR erodes principal (negative price CAGR).
- **RoC TRAPS (high yield, shrinking principal — AVOID):** REM mortgage-REIT (9.8% yield / price −10.8%/yr /
  TR −1.0% — hands you cash while losing money), RYLD (11.5%/−5.8%/5.7%), BIZD BDC (9.7%/−3.4%/6.3%), QYLD
  (10.9%/−2.7%/8.2%), PFF preferreds (6.2%/−2.6%/3.7%), HYG/JNK HY-credit (~6-7%/−1.5-2%/~5%). All also carry
  −38 to −78% drawdowns.
- **SUSTAINABLE income (yield covered by earnings):** **JEPI the standout — ~9% cash yield, price +2%/yr,
  TR 11.1%, maxDD only −14%.** DIVO (5.9%/+6.7%/12.5%), SCHD (3.5%/+9.8%/13.3% — fully sustainable but LOW cash
  yield). VYM/DVY ~3.5% cash but −57/−63% DD (equity beta).
- **VERDICT:** the ONLY vehicle giving ~9% REAL (non-RoC) cash income = JEPI-type covered-call funds = gate #1's
  VRP in an income label — equity-beta, and history is 2020+ (NEVER seen a real bear; the −14% DD is untested;
  QYLD was once the darling too, now a RoC trap). TRUE principal-safe 10% cash income does NOT exist; honest
  low-risk sustainable ceiling ~6-8%; ~9% means the covered-call/equity-beta/untested-tail bet.
- **DESIGN (converges with the total-return answer):** best income book = BLEND a JEPI-type covered-call income
  sleeve (~9% current cash, equity-beta) with the uncorrelated FX+basket book (draw its ~10% TR to cash) →
  ~10% cash at LOWER risk than JEPI alone (FX cushions the VRP/equity tail). Same combination principle.
  NEXT if pursued: size a JEPI/DIVO income sleeve into the FX+basket book; test blended cash-yield vs drawdown.

**INCOME-SLEEVE SIZING (2026-07-17, scratchpad `income_sizing.py`):** target ~8% total = sustainable cash draw;
structure = FX (margin overlay) + basket/JEPI/cash (cash pool). Frontier at ~8%: Low-beta (−3.8%DD, 4.3% cash,
0.80 eqcorr), Balanced (−5.3%DD, 4.9% cash, 0.87), Income-max (−6.8%DD, 5.9% cash, 0.89). KEY: adding JEPI
pushes book equity-corr to ~0.8-0.9 (vs FX+basket combo's 0.11) — JEPI's 9% cash IS equity beta. Current cash
tops ~5-6% (rest of the 8% draw = realized gains). Low in-window DD partly benign 2020-26 window (JEPI tail
untested). RECOMMENDED Balanced (~$219k JEPI / trim basket to ~$200k / FX ~$447k notional / ~$576k cash). NOT
placed — held per user. Note: nothing about carry_cot_mom or framework code touched (verified git-clean).

**REGIME / HEDGE-SLEEVE INVESTIGATION (2026-07-17) — CONCLUSION: leave the 2-sleeve core AS-IS, add nothing.**
User explored regime-adaptive & bull/bear specialist sleeves. Scripts: scratchpad `four_sleeve.py`,
`bear_gated.py`, `bear_exit.py`, `bear_robust.py`.
- **"Adjust the amount by regime" (continuous, not binary):** same tilt→zero problem. The distinction that
  matters = RESPONSIVE (tilt by realized vol/corr — WORKS, already in the book via basket inverse-vol weighting)
  vs PREDICTIVE (forecast bull/bear — FAILS). Continuous-ness doesn't rescue a predictive signal.
- **4-sleeve (add bull=SPY + bear=trend, always-on):** did NOT beat the 2-sleeve combo (full Sharpe 1.58→1.44).
  SPY bull-sleeve = redundant equity beta (0.68 corr to basket, raised eqcorr to 0.72). Trend bear-sleeve helped
  2022 (0.44→0.90) but whipsawed the FAST crashes (2018 1.08→0.00, COVID 1.06→0.27) and dragged the bull.
- **Bear-GATED short-SPY (flat in bull, short only when SPY<200dma):** on 2015-26 looked like the BEST result —
  full Sharpe 1.58→1.63, DD −7.0%→−4.7%, and it IMPROVED the fast crashes (skips the "long-into-crash" leg).
  Asymmetric 50-day exit (enter<200dma, cover>50dma) looked best.
- **ROBUSTNESS CHECK 2000-2026 OVERTURNED IT (the decisive test).** The 50-day exit was OVERFIT to the recent
  window: in the REAL slow multi-bounce bears it churns on bear-market rallies — dot-com 2000-02 symmetric-200
  made +12.8% but 50-day LOST −7.8%; GFC symmetric +11.6% vs 50-day +4.1%. No stable best exit (20d won
  2000-02/2008, 50d won 2022 — fitting each bear's noise). Standalone the bear sleeve is a COSTLY hedge
  (2000-26: −0.18 Sharpe, and it LOST money summed across all 7 "bears" −9%, because most 200dma "bears" are
  whipsaws not sustained declines; its 2 real-bear wins < its 4 false-alarm losses).
- **Real value = modest crash insurance only:** SPY 100% (CAGR 8.2%/Sh0.51/−55%DD) vs SPY+15%-hedge (7.0%/0.54/
  −44%DD) → cuts DD −11pp, Sharpe +0.03, at ~1.2% CAGR cost, over the full history incl. 2008. Insurance with a
  real premium, NOT alpha. If ever used: SYMMETRIC 200-day exit (robust; fast exits overfit), small, un-tuned.
- **DECISION: don't add.** Crash protection already handled structurally by the basket's bonds/gold + FX's ~0
  equity corr. Reconfirms program laws: "always-on beats timed" + distant-window validation is load-bearing
  (the cheap 2000-26 check caught an overfit the 2015-26 window hid). P/E = planning/expectations gauge only,
  useless as a regime/exit trigger (slow, ~0 short-horizon power; exit needs the FASTEST signal, PE is slowest).

**MERGER-ARB GATE (2026-07-17) — NO (arbitraged down to ~cash). Script `mergerarb_gate.py`.** Assessed the
premium via packaged funds (MERFX Merger Fund 1989+, MNA IQ ETF, MERIX). DECAYED: CAGR 7.8% (1990s) → ~3.5%
(recent) as capital flooded in; Sharpe held ~0.9-1.0 only because vol is tiny (~3.5%). KILLER: premium OVER
CASH compressed to ~1.5-2% (RECENT15+ MERFX 3.5% vs T-bills 1.9%); at today's ~4% T-bill yield you take
deal-break risk (−15% DD) for ~1-2% above risk-free. Absolute ~3.5% too low to serve the ~8% income goal
(dilutes). Genuine crisis diversifier (2008 MERFX +0.5% vs SPY −44%; COVID −0.6%; 2022 +0.8%) BUT only +0.45
equity-corr (deal breaks cluster in risk-off) + ~0 to bonds. DIY doubly-gated: free structured M&A deal data
doesn't exist (SEC EDGAR filings free but unstructured/NLP-heavy; SDC/Bloomberg/Dealogic institutional-paid),
AND a retail DIY book would UNDERPERFORM the ~3.5% fund (execution costs + fat-tailed break risk at low
diversification). Verdict: not worth it — same "famous edge competed away" pattern as everything else.

**RESEARCH-PHASE STATUS (2026-07-17):** systematic-STRATEGY space now thoroughly mapped — crypto, commodities,
equity/ETF/options (VRP, basket, trend, factors, momentum-rotation), FX carry, income vehicles, regime/hedge
overlays, merger-arb — all closed except the DEPLOYED carry_cot_mom + RP basket combo (the durable winner).
New-alpha well is largely DRY. Remaining VALUE = income-enhancement + implementation, NOT new strategies:
(1) Stock Yield Enhancement (securities lending) = free incremental yield on holdings; (2) Treasury/bond ladder
= ~4-5% safe income foundation for the cash buffer; (3) implement the designed JEPI/basket/cash income sleeve.
Remaining RESEARCH frontier is DATA-GATED (needs paid feeds): macro-surprise (consensus-estimate feed), FX
options VRP (IBKR history thin), cross-currency basis. IBKR's new 2026 features (prediction markets Kalshi/CME/
ForecastEx, AI/agentic trading, stablecoin funding) are NOT systematic-edge sources.

**INCOME-ENHANCEMENTS SPEC + SGOV FEATURE (2026-07-18, pushed origin/main @ 4780007).** Spec
`docs/income-enhancements.md` (go-live/real-money plan): (1) **SGOV for the cash buffer = small clean win**
(~4.3%, STATE-TAX-EXEMPT vs IBKR-cash taxable ~4%, auto-rolling, liquid) — worth doing; a manual T-bill ladder
earns ~same + more work (only to lock rates vs cuts). (2) **Securities lending (SYEP) = marginal-to-net-NEGATIVE
for THIS book — defer:** holdings are general-collateral (tiny ~0.1-0.5% fee) AND dividend PIL tax drag (lent
shares' dividends become ordinary-income payments-in-lieu, losing qualified treatment) can exceed the fee in a
TAXABLE account; enroll only if tax-advantaged (IRA) or holding hard-to-borrow stocks. These are REAL-money
features (paper earns neither) + IBKR already auto-pays ~4% on idle cash, so net uplift is small — tax/rate
optimization, NOT new return; does NOT move the ~8% income target (that's still JEPI+basket+realized-FX).
BUILT: `scripts/cash_sleeve.py` — parks a target USD in SGOV via BasketExecution (single symbol → weight 1.0,
all guards/reconcile/rollback reused), default preview, --confirm arms, client_id 26. Hermetically verified
(single-symbol weight=1.0, 274 tests pass); LIVE preview deferred (Gateway was down 2026-07-18). NOT placed.
NOTE: basket_positions.csv left UNTRACKED deliberately (runtime account data → public repo = don't version).

**BOND-LADDER: reported + implemented (2026-07-18, pushed origin/main @ 80b16c3).** A Treasury ladder's TOTAL
return ~= a constant-maturity Treasury ETF blend (proxy with SHY 1-3y/IEI 3-7y/IEF 7-10y). Performance
(scratchpad `bond_ladder.py`): income+defense BETA not alpha; forward yield ~4.2% (2002-26 CAGR 2-3% understates
it — ZIRP-dragged). Duration = the only dial AND risk: short ladder (1-3y) Sharpe 1.30 / maxDD −5.7% / 2022
−3.9% (near cash); intermediate (1-10y) hedges equity harder (2008 +8.6% vs short +6.3%) but 2022 −9.6%; IEF
2022 −15.2%. Equity-corr −0.2 to −0.3 (real hedge in 2008/2020 but BROKE in 2022 — stocks+bonds fell together).
Held-to-maturity edge: par at each rung → never REALIZE interim MtM loss (principal-certain), same total return.
Fits as the income/defensive foundation; short ladder ≈ the SGOV cash sleeve extended. IMPLEMENTED: BasketExecution
gained `equal_weight=True` (1/N per rung, not inverse-vol); `scripts/bond_ladder.py` (default SHY,IEI,IEF or pass
iBonds IBTF/IBTG/... for a true principal-returning ladder), client_id 27. Hermetically verified + suite 281.
Reuses cash-sleeve/basket pattern. NOT placed. LIVE PREVIEW VALIDATED (2026-07-18, after clearing the competing
session): equal 1/3 weights, correct sizing.
**IMPORTANT ARCHITECTURAL GOTCHA the preview caught: SLEEVES MUST USE DISJOINT SYMBOL SETS.** Every sleeve
reconciles BY CONID AGAINST THE WHOLE-ACCOUNT POSITION, so two sleeves sharing a ticker FIGHT over it. The
default SHY/IEI/IEF ladder overlaps the basket's IEF (basket holds 1757; ladder target 1066 → ladder would SELL
691 IEF out of the basket, then next basket rebalance buys it back — forever). FIX: run the ladder with
NON-overlapping ETFs — best = iBonds defined-maturity Treasuries (IBTG..IBTL = 2027-2032, a true principal-
returning ladder, none in the basket): `bond_ladder.py --symbols IBTG,IBTH,IBTI,IBTJ,IBTK,IBTL`; or SHY,IEI,GOVT
(GOVT not in basket). RULE: keep each sleeve's symbols disjoint (FX pairs / basket SPY,TLT,IEF,GLD,DBC / cash
SGOV / ladder iBonds). The reconcile-by-conId can't tell "basket IEF" from "ladder IEF".
Also: Error 162 "Trading session connected from a different IP" (blocked ALL historical data earlier) = a
competing IBKR login (phone IBKR Mobile from 2FA, or web portal) holding the market-data line — log those out;
not a code issue. TRADES and MIDPOINT both work once the line is free.

**LADDER PLACED (2026-07-18) — ~$300k iBonds IBTG,IBTH,IBTI,IBTJ,IBTK,IBTL (2027-2032 Treasury ladder, equal
1/6), STAGED PreSubmitted (market closed at placement → 6 BUY orders queued, 0 filled, Complete=False). User
chose to LEAVE them to fill at the next open (DAY market orders held PreSubmitted for next session). Disjoint
from basket — no conflict. VERIFY FILLS NEXT SESSION; if any expired, re-run `bond_ladder.py --symbols
IBTG,IBTH,IBTI,IBTJ,IBTK,IBTL --allocation 300000 --confirm` during RTH (reconciles, safe). iBonds letter=Dec
maturity year (IBTF=2026 near-cash so dropped; IBTG=2027..IBTL=2032). LESSON: place during RTH so market orders
fill immediately (after-hours → PreSubmitted/staged). Account now: FX carry + RP basket $400k + iBonds ladder
$300k (staged); ~$294k cash remaining. Income sleeve (JEPI) + SGOV cash sleeve still NOT placed (on hold).

**MUNI-BOND ANALYSIS (2026-07-18, scratchpad `muni_compare.py`) — CA muni WINS after-tax for a CA high earner
in a TAXABLE account, but LOSES the crash-hedge role.** Tax assumptions (confirm w/ advisor): fed 37% + CA
13.3% + NIIT 3.8%, SALT-capped. After-tax factors: CA muni 1.00 (fully exempt), natl muni 0.867 (pay CA),
Treasury 0.592 (pay fed+NIIT, state-exempt). AFTER-TAX YIELD (recent income): **CMF (CA muni) 2.9% > MUB
(natl) 2.7% > SGOV 2.5% > SHY 2.2% > IEI 2.1%** — CA munis beat the Treasury ladder by ~0.8%/yr after tax;
CMF taxable-equivalent = 6.4%. BUT THE CATCH: munis DON'T hedge equity crashes like Treasuries — 2008 GFC
CMF +1.9% vs IEI +9.9%/IEF +13.5%; COVID Mar-2020 CMF −2.2% vs IEI +4.3% (the muni liquidity freeze — munis
FELL while Treasuries rallied); equity-corr CMF +0.16 / MUB +0.22 vs IEI −0.13 (munis mildly equity-correlated,
credit/liquidity risk). Pre-tax munis are also more volatile / worse Sharpe (CMF 8.4% vol / Sh 0.43 vs IEI
4.1% / 0.71) — the appeal is 100% the tax break. STRUCTURE GAP: no clean CA-specific defined-maturity ladder
(CMF = single blended fund ~5-6y, not rungs; national muni iBonds = fed-exempt only, still pay CA). VERDICT:
for after-tax INCOME in a taxable account CA munis (CMF) win; for CRASH-HEDGE Treasuries win; split accordingly.
REAL-MONEY + TAXABLE only (zero benefit on paper/IRA — which is why the paper ladder is correctly Treasuries/iBonds).

**INCOME-PREMIA THEORY + DIVERSIFIED INCOME BOOK (2026-07-18, scratchpad `income_blend.py` + `income_book.py`).**
Theory: sustainable income = pay for a risk/illiquidity; the premia (term/credit/VRP/illiquidity/carry/equity/
real-asset). KEY EMPIRICAL: high-yield "income" is mostly EQUITY/CREDIT RISK in disguise — ARCC (BDC/private
credit) −51% in 2008 / −79% full DD / 0.64 eq-corr; BIZD 10%y/−55%DD; PBP(cov-call) 12%y/−43%DD; VNQ −63% 2008;
all 0.6-0.93 equity-corr. Only muni/Treasury/cash held up (CMF +2% 2008/corr 0.04; IEF +13%/−0.29). "Private
credit low vol" = volatility-laundering (infrequent marking hides the risk). Diversifying across income premia
ALONE isn't enough (equal-wt 6-premia blend still −34%DD / 0.86 corr — they're all economic risk). The real
lever = anchor with GENUINELY uncorrelated assets: govt bonds, gold, and FX CARRY (which user owns).
**SIZED + IMPLEMENTED the diversified income book (2026-07-18):** FX carry (uncorr anchor, margin overlay) +
RP basket (Treasuries/gold anchor) + measured income sleeve (½ BIZD BDC + ½ JEPI cov-call) + cash. The anchor
CUSHIONS the income sleeve: income-only −34%DD → anchored −7 to −11.5%DD. Frontier (2020-26): cash-yield 4.5%
(Conservative) → 6.7% (Income-max). RECOMMENDED **Balanced (FX .45 notional / basket .30 / income .30 / cash
.40): ~9.9% total ret, 5.3% CASH yield, −8.8% in-window DD, every yr +ve (2022 −2%).** CAVEAT: still ~0.85
equity-corr → in-window DD flattered by benign 2020-26 window; a 2008-style bear ~−15 to −20% (income sleeve
fell −50%+ in 2008, cushioned ~40% by anchor). Honest deal = ~5-6% sustainable CASH + ~10% total (realizable)
at MODERATE risk; can't get high cash yield AND low risk (yield IS the risk). PLACED on paper (2026-07-18,
staged PreSubmitted, market closed): `scripts/income_sleeve.py` (equal-wt BIZD/JEPI, client_id 28, pushed
origin @ 3ee4178) $298k + basket TRIMMED $400k→$298k, alongside the $300k iBonds ladder → Balanced book
(basket $298k + ladder $300k + income $298k + ~$98k cash + FX overlay). All 13 orders staged for next open
(5 basket sells + 2 income buys + 6 ladder buys), verified queued, no conflicts.
**FILLS CONFIRMED 2026-07-20:** ALL filled at target, 0 open orders, no partials/errors. Positions verified —
basket SPY65/TLT837/IEF1308/GLD71/DBC1032, income BIZD11723/JEPI2635, ladder IBTG2186..IBTL2489. Account: NAV
$988,270, GrossPositionValue $891,648 (3 ETF sleeves ~$298k+$300k+$298k), ~$97k cash, FX carry on margin. The
Balanced diversified income book is now LIVE on paper as designed. Forward-track it: judge realized cash yield
+ Sharpe/DD vs the ~5-6% cash / ~10% total / −8.8% in-window target over MONTHS. snapshot_nav.py captures
combined NAV; per-sleeve logs = basket/cash/bond_ladder/income_sleeve _positions.csv. The real answer =
COMBINE uncorrelated sleeves + modest leverage: carry_cot_mom (Sharpe ~1.15, ≈0 equity corr) + basket
(0.45 corr) → blend Sharpe plausibly ~1.3, lever THAT to 10% → drawdown stays controlled (diversified risk),
unlike levering either alone. **NEXT (the real deliverable): test carry_cot_mom + basket combination — blend
ratio, leverage-to-10%, resulting DD/worst-years.** Don't re-run the 4 gates — closed. Scripts in scratchpad:
vrp_gate / basket_gate / trend_gate / factor_gate.py.