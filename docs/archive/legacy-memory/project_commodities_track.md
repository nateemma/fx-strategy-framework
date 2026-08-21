---
name: project_commodities_track
description: "Commodity futures at IBKR — a well-motivated 3rd track: runs the program's 3 validated engines (carry/roll, trend, COT) in a liquid orthogonal asset class. Data-feasibility PASS (COT+trend free & deep; carry data-constrained). Signal-check pending."
metadata:
  node_type: memory
  type: project
  originSessionId: e1399a6e-effc-415c-9b11-ad051d604f86
---

**Commodity futures at IBKR = a genuinely well-motivated new track (assessed 2026-07-17).** Far more
promising than the crypto-derivatives track ([[project_ibkr_crypto_derivatives_track]], gated negative):
it lets us run the program's THREE already-validated signal engines in a liquid, shortable, orthogonal,
deep-history asset class where they are native and academically robust.
- **Carry** → commodity ROLL YIELD (backwardation/contango) — the textbook carry factor (Gorton-Rouwenhorst,
  Koijen "Carry"). Carry is the program's dominant axis ([[project_fx_cot_positioning]]).
- **Trend/momentum** → already the FX diversifier ([[project_fx_trend_is_the_diversifier]]); commodities are
  trend's best historical home + crisis alpha (SG CTA index +20% in 2022; 3-12mo TSMOM Sharpe held post-2008).
- **COT positioning** → the CFTC COT report was BUILT for commodities (richest positioning data of any asset
  class); COT is the program's first non-price edge ([[project_fx_cot_positioning]]). `forex/data/cftc.py`
  loader works as-is.
Strategic value = ORTHOGONALITY to the FX book: a low-corr commodity sleeve lifts PORTFOLIO Sharpe
([[project_fx_return_bar]]), which is the real bar. Structural fitness is the OPPOSITE of crypto's walls:
deeply liquid, shortable, cheap (CME/ICE/NYMEX/COMEX/CBOT; micro contracts MCL/MGC right-sized for ~$1M),
decades of clean survivorship-free history, single venue at IBKR.

**DATA-FEASIBILITY SPIKE = PASS (strong), 2026-07-17.** Two of the three engines are FREE, deep, broad,
buildable NOW; only carry is data-constrained:
- **TREND: FREE.** Yahoo chart API continuous front-month `=F` (dependency-free urllib, no key): **20/20**
  liquid commodities across all sectors (energy CL/BZ/NG/RB/HO, metals GC/SI/HG/PL, grains ZC/ZW/ZS/ZL/ZM,
  softs SB/KC/CT/CC, livestock LE/HE), ~**2000→present (26yr)**, daily, ~6,500 bars each.
  CAVEAT: Yahoo continuous is OPAQUELY back-adjusted → valid for TREND (momentum on returns) but
  **NEVER compute carry/roll from it** (needs real term structure).
- **COT: FREE + VERY deep.** CFTC Socrata legacy futures-only (dataset 6dca-aqww, same as FX). **19/19**
  commodities, most back to **1986 (40yr), 1900+ weekly obs**, current to ~1wk lag. Reuses `forex/data/
  cftc.py` load_cot as-is; just add codes. Verified codes (cftc_contract_market_code): WTI 067651, NatGas
  023651, RBOB 111659, HeatOil 022651, Gold 088691, Silver 084691, Copper 085692, Platinum 076651, Corn
  002602, Wheat SRW 001602, Soybeans 005602, SoyOil 007601, SoyMeal 026603, Sugar11 080732, Coffee 083731,
  Cotton 033661, Cocoa 073732, LiveCattle 057642, LeanHogs 054642.
- **CARRY: constrained (the one deferred piece).** Yahoo `=F` is front-month only (no roll). FREE for ENERGY
  only via **EIA legacy XLS** (`eia.gov/dnav/pet/hist_xls/RCLC1d.xls` = WTI contract-1, `RCLC2d.xls` =
  contract-2; both HTTP 200, real ~500KB .xls — needs `xlrd>=2.0.1` to parse; NG=RNGC1/2, etc.). Broad
  cross-commodity term structure = PAID feed (Databento/Norgate/FirstRate) or individual-contract stitching.
  EIA v2 API needs a free key (403 without). Stooq is now behind a JS proof-of-work wall — dead as a free src.

**SIGNAL-CHECK RUN (2026-07-17) — the two FREE signals (trend, COT) FAIL the deployment-regime bar;
verdict now hinges on the UNTESTED carry sleeve.** Weekly cross-sectional backtest, 19 commodities, causal,
net 5bp, distant eras. Tested with AND without the standard vol-targeting lever (per-instrument inverse-vol):
- **Trend (TSMOM 12mo, vol-targeted):** 2000-09 **0.54**, 2010-17 0.14, **2018-26 −0.04, RECENT15+ −0.20.**
  Real historically, decayed to flat/negative in the modern regime. Multi-horizon (1/3/12mo) was WORSE
  (short horizons whipsaw). Vol-targeting improved HISTORY (0.35→0.54) but did NOT move the modern verdict.
- **COT contrarian (FX-validated form, vol-targeted):** 2000-09 0.00, 2010-17 **0.45**, **2018-26 −0.21**,
  RECENT15+ +0.11 (the +ve is all 2015-17). Okay 2010-17, negative in the true 2018+ window. Note: OPPOSITE
  era-pattern to FX COT (which was modern-ONLY) → COT is era/asset-UNSTABLE, not a universal edge.
- **XS-momentum:** dead every era (−0.3 to −0.7). Drop.
- **Blend trend+COT:** corr −0.29 (good diversification structure) but −0.29/−0.35 modern — can't blend two
  ~zero-modern signals into edge. Same decay trap as G10 carry: full-history flatters, deployment regime is truth.
- **NOT TESTED: commodity CARRY (roll yield)** — the strongest/most-persistent commodity factor in the lit,
  and the ONE gated behind term-structure data. So the free signals don't carry the avenue; the verdict now
  hinges on carry, still unmeasured. Reframes the question: NOT "port freqtrade" but "is it worth acquiring
  term-structure data to test commodity carry."
- **DECISIVE NEXT GATE (cheap, free):** test ENERGY carry from free EIA curves (WTI/NG/HO/RB contracts 1-2,
  reachable — needs `xlrd` or free EIA v2 key to parse the .xls). If energy-carry is alive 2018-26 → justifies
  paying for broad term-structure data (Databento/Norgate) to test full carry sleeve; if dead → avenue weakens
  sharply for $0. Orthogonality-vs-carry_cot_mom deferred until a commodity signal clears the standalone bar.
Scripts: scratchpad `commod_feasibility.py`, `commod_signalcheck.py`, `commod_refine.py`. Don't re-run trend/
COT/XS-mom — closed as modern-weak. The open question is CARRY only.

**ENERGY-CARRY GATE RUN (2026-07-17) — INCONCLUSIVE BY CONSTRUCTION; carry is UNTESTABLE on free data.**
Pulled EIA free term structure (WTI RCLC1-4 `/pet/`, NatGas RNGC1-4 `/ng/`, HeatOil EER_EPD2F_PE{1-4}_Y35NY_DPG,
RBOB EER_EPMRR_PE{1-4}_Y35NY_DPG — all `hist_xls/*d.xls`, need `xlrd>=2.0.1` [installed into freqtrade .venv]).
Built roll-yield (C1-C2)/C2 signal; returns from Yahoo `=F`. ALL variants uniformly catastrophic (Sharpe
−0.6..−1.4, maxDD ~−100% EVERY era) → classic simulator-artifact signature, NOT a real anti-edge. ROOT CAUSE:
Yahoo `=F` (and EIA C1) are FRONT-MONTH, NOT roll-adjusted → the monthly roll GAP is the carry signal with
FLIPPED sign; "long backwardation" mechanically bets against the fake jump. Fingerprint: predictive corr(roll,
next-ret) SCALES WITH CONTANGO DEPTH — WTI (mild) +0.06 vs NatGas (deep −0.27 roll) −0.19; pooled −0.11.
Outlier-neutralization (|z|>5) caught only 5-18 days (rolls are ~300 sub-5σ monthly events) → can't fix it.
LESSON (crypto-rule confirmed): a surprising uniform result = simulator bug, don't believe the number.
**CONCLUSION: commodity carry CANNOT be validly backtested on free continuous data — needs ROLL-ADJUSTED
returns (individual-contract / Panama back-adjust / paid feed). EIA & Yahoo can't provide it.** So the carry
question — the only standing commodity hypothesis after trend/COT failed modern — requires a DATA INVESTMENT
to answer. Script: scratchpad `energy_carry.py` (v1, artifact) + `energy_carry_v2.py` (cleaning attempt).

**COMMODITY AVENUE — OVERALL VERDICT (2026-07-17): shelved, with a cheap escape hatch.** Free testable signals
(trend, COT) DECAYED to flat/neg modern; carry (strongest factor) is data-gated & untestable free & faces the
SAME crowding headwind. Recommend: SHELVE unless you want the definitive carry read — for which the $0 path is
a FREE TRIAL of Norgate or Databento (roll-adjusted continuous + individual contracts), run the carry test
once properly, then decide. Do NOT buy a subscription speculatively. Live FX carry_cot_mom (~1.15 WF Sharpe)
still clears the bar; commodities do not without carry surviving. Don't re-run the free carry test — closed.
