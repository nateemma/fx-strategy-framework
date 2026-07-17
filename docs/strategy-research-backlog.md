# FX Strategy Research Backlog

A prioritized list of strategies to investigate on this framework, grounded in the academic FX
literature and the methodology lessons carried over from a prior crypto ML program.

## How to read this
The "best FX strategies" are a small set of **well-replicated cross-sectional factors** (carry,
momentum, value, dollar) plus their **risk-managed / conditioned** versions. The frontier is
*combining and risk-managing* them, not predicting price. Two hard-won principles frame every entry:

1. **ML does not beat an efficient market on raw price direction.** Major FX is *more* efficient than
   crypto, where a price-only information ceiling (Spearman ρ ≈ 0.15) was proven three ways. ML earns
   its keep on **conditioning / timing / sizing** factor exposures and on **non-price data** (rates,
   positioning, vol, text) — never on out-modeling the price series.
2. **Judge on out-of-sample, distant-window, cost-and-liquidity-aware P&L.** Much published "FX ML" is
   overfit. The robust, replicated stuff is factor-based and risk-managed.

Each strategy maps to the framework as a `Strategy.target_weights(view) -> weights` (+ optional
`fit`/`search_space`); "new data" means extending `DataView` with a loader.

---

## Tier 1 — build next (strong evidence, free data, natural framework fit)

### 1. Cross-sectional momentum
Rank currencies by trailing return (1–12 months); long winners / short losers. Low correlation to
carry, so it diversifies the book. Well-documented (Menkhoff, Sarno, Schmeling, Schrimpf 2012,
*Currency Momentum Strategies*). **Data:** none new (prices already in `DataView`). **ML angle:**
none needed for v1 (rule-based); later, condition the lookback/turnover on vol regime.
> **Status (2026-07-14): BUILT → BENCHED.** `momentum.py`. G10 monthly Sharpe ~0.07, uncorrelated to
> carry (−0.07) but adds ~nothing to the blend; daily rebalance was self-harming. Valid factor, too
> weak to deploy.

### 2. Value / PPP mean-reversion
Long currencies cheap vs fair value (PPP / real effective exchange rate), short expensive ones; they
revert over 1–5 years. The third leg of the classic carry–momentum–value trio (Asness, Moskowitz,
Pedersen 2013, *Value and Momentum Everywhere*). **Data:** REER / PPP series (OECD/BIS, largely free
via FRED). **ML angle:** none for v1; the edge is the slow reversion.
> **Status (2026-07-14): BUILT.** `value.py`. Adds no standalone Sharpe but **halves carry drawdown**
> (Calmar lever) — kept in the blend for risk, not return.
> **Tested on EM/tradeable universe + 3-way blend (2026-07-16): does NOT beat carry_cot.** Value alone on
> EM is weak (Sharpe 0.34–0.44, same as G10 — EM didn't rescue it). carry+cot+value vs carry+cot: modern
> 2018-26 Sharpe 0.94 vs 1.01 (value HURTS), full-period Calmar 0.48 vs 0.41 (tiny bump, flat Sharpe).
> Reason: value is 0.39-correlated with COT and its only role is DD reduction — but COT already fills that
> slot (always-on diversification, DD −4.6%). Value is redundant now that COT holds the risk-reducer role +
> dilutes modern Sharpe. **carry_cot (2-way) stays the deployable book; 3-way rejected.** (REER: G10+MXN+ZAR
> only; PLN/HUF/CZK/ILS lack FRED REER.)

### 3. Combined factor portfolio (carry + momentum + value)
The single most defensible "best" baseline: the three factors are low-correlated, so an
equal-risk or vol-weighted blend has a much higher Sharpe than any one alone (Baz et al.,
*Dissecting Investment Strategies*). **Framework:** a meta-`Strategy` that blends sub-strategy weights.
**ML angle:** factor *timing* (Tier 2) sits on top of this.
> **Status (2026-07-14): BUILT — but the edge is pre-2010.** `blend.py` (`carry_trend`,
> `carry_trend_value`, + vol-targeted). **Corrected numbers** (an earlier ~0.52 figure was a stale-cache
> artifact; current data validated against FRED): deployable `carry_trend_voltarget` OOS Sharpe **0.15**
> (1997+), but era-split shows **0.82 (1997–09) → 0.07 (2010–17) → 0.006 (2018–26)** — G10 carry died
> with ZIRP-era rate-differential compression; **no modern edge**. Value does NOT robustly help
> (era-split rejects it, negative since 2018) — deployable stays `carry_trend_voltarget`. More G10 rank
> factors are dry; the live question is whether **EM carry (#12)** or non-price data revive an edge.
> **CARRY-MOMENTUM refinement = ADDITIVE (2026-07-16).** Ranking by the 6-month CHANGE in the rate
> differential (is the carry WIDENING?) is a genuine 3rd diversifying sleeve: corr 0.04 vs carry, −0.16
> vs COT (orthogonal to BOTH, unlike value's 0.39-with-COT). Weak alone (Sharpe 0.24–0.35) but the blend
> `carry+cot+mom` beats `carry_cot` CAUSALLY (trailing-vol risk-parity): full 2015-26 Sharpe 0.73→0.94,
> 2018-26 1.00→1.07, maxDD −4.6%→−3.9%; helps 6/10 years (gives up upside only in carry's strongest years,
> e.g. 2022). Lookback 6mo (mom6 > mom12; level+mom combos worse — keep them SEPARATE sleeves).
> **FORMALIZED + WALK-FORWARD-VALIDATED (2026-07-16, commit 7566df6):** `strategies/carrymom.py`
> CarryMomStrategy (`carry_mom`), `CarryCotMom` blend (`carry_cot_mom`). WF (750/250, 5bp): carry_cot_mom
> Sharpe **0.98 vs carry_cot 0.96**, 2018-26 **1.08 vs 1.03**, maxDD −3.9% vs −4.1% — real but MODEST. The
> big full-period gain (0.73→0.94 in a daily-trailing-vol blend) shrinks in the framework because (a)
> BlendStrategy uses monthly-EWMA risk-parity (captures less momentum diversification) and (b) momentum's
> largest benefit is 2015-17, which WF puts in-training. Modern-era (2018+) gain is small (+0.05 Sharpe).
> Legitimate 3-factor book, now first-class; carry_cot vs carry_cot_mom is a marginal call (extra turnover
> ~6x/yr for +0.05 Sharpe). 242 tests pass.
> **LOOKBACK ROBUSTNESS (2026-07-16): strong PASS + upgrade.** Swept mom lookback 63-378d in the blend:
> smooth monotone-then-plateau surface (63d too noisy WF 0.84 < base; 126d 0.98; 189d 1.01; 252d 1.15;
> 315d 1.05; 378d 1.18) — a broad high plateau (189-378d all WF ~1.0-1.2), NOT a spike → 126d is validated
> and CONSERVATIVE, not cherry-picked. corr(mom,carry) stays ≈0 (+0.03→−0.02) even at 12-18mo → never
> redundant. Both sub-periods improve (H1 2015-20: 0.55→1.31 at 252d). UPGRADE: default should be **252d
> (12mo)** — mid-plateau, WF ~1.15 vs 0.98 at 126d, lower turnover, canonical 12mo momentum horizon
> (principled, not sweep-chasing).
> **BLEND-CADENCE INVESTIGATED (2026-07-16) → no change; earlier "gap" was a measurement artifact.** Swept
> cadence (daily/weekly/monthly) × EWMA lam (0.94–0.99) for both blends: monthly (the default) is best or
> tied for BOTH; faster cadence does NOT capture more diversification (hypothesis refuted). Measured
> consistently in the framework, carry_cot_mom's FULL-period Sharpe is 0.76→0.96 (+0.20, matching the quick
> daily blend) — the diversification was never left on the table; the walk-forward just can't see it because
> momentum's gain concentrates in 2015-17 (in the WF training window). The prior "framework leaves
> diversification on the table" claim compared WF-vs-full across tools — apples-to-oranges, now corrected.
> lam=0.99 is a within-noise nudge (helps 3-way WF 0.98→0.99, hurts 2-way) — keep defaults. Blend machinery
> is sound; no change.

### 4. Carry crash / vol overlay — finish the ML stage
The EWMA vol-target overlay exists (Sharpe 0.34 → 0.40 hyperopt'd) — it *is* the deployable book. Vol
is predictable where direction is not, and global FX vol is a *priced* carry-crash factor (Menkhoff et
al. 2012, *Carry Trades and Global FX Volatility*).
> **Status (2026-07-14): CLOSED — negative.** The Stage-B ML vol forecaster was built and tested
> end-to-end: price-only HAR, cross-asset macro HAR (VIX / BAA10Y credit / term slope), EWMA-anchored
> HAR, and a nonlinear gradient-boosted variant. **All lose to the zero-parameter EWMA on walk-forward.**
> Performance is *monotone-decreasing in model capacity* (EWMA 0.123 › ridge 0.087 › GBM 0.064 Sharpe) —
> estimation variance, not capacity, is the binding constraint (forecast-combination puzzle). An MLX
> LSTM was proposed and **shelved** on this evidence (strictly more capacity → predicted worse; its one
> DoF, learned memory, is what EWMA already is). **EWMA stays the default; the ML-vol-*forecasting*
> lever is exhausted.** EWMA-based vol *sizing* still works — it's the *learned* forecaster that adds
> nothing. Crash management now routes to the trend overlay (#11) and regime conditioning (#5), not to a
> better vol model. Rejected variants stay registered as documented negatives.

---

## Tier 2 — ML earns its keep (needs non-price data; overfitting-guarded)

### 4b. Yield-curve slope / rate-expectations signal — REJECTED
Idea (from the IBKR-data question): the yield-curve slope (10y−3m per ccy, OECD IRLTLT01 − IR3TIB01)
encodes market-implied expected rate direction — a forward-looking, priced version of the NLP hawkish/
dovish idea. FRED-backtestable (yields to ~1997-2001 for EM, longer for G10).
> **Status (2026-07-17): TESTED → REJECTED (carry-redundant).** Cross-sectional rank-IC is NEGATIVE
> historically (−0.05..−0.09 in 2000-09, fading to ~0 in 2018-26) — i.e. INVERTED curve (high short rate)
> → currency appreciates, which is just carry re-expressed (WRONG sign for the "steep=appreciation"
> hypothesis). Slope sleeve weak alone (Sharpe 0.11/0.23), moderately correlated with carry/cot/mom
> (−0.20/−0.29/+0.24, NOT orthogonal), and adding it HURTS the blend (carry+cot+mom 2018-26 1.22→1.12,
> maxDD −3.0%→−4.2%). Forward-looking rate-expectations content is either priced or already captured by
> carry + carry-momentum. Caveat: 10y-3m term-spread (2y unavailable cross-country); a pure near-term
> measure might differ but low prior. carry_cot_mom (3-factor) stands.

### 4c. FX skewness / crash-risk premium — REJECTED
Rank by trailing return skewness; long negative-skew (crash-prone) currencies for the tail premium
(Rafferty). Backtestable from spot returns (no new data).
> **Status (2026-07-17): TESTED → REJECTED (carry-redundant).** Rank-IC weak + era-UNSTABLE (positive
> 2010-17, negative 2000-09 and 126d-2018-26, full ~0). Skew sleeve 0.41-correlated with CARRY (high-carry
> currencies ARE the crash-prone ones), weak alone (0.31/0.34), and adding it HURTS the blend
> (carry+cot+mom 2018-26 1.22→1.12, DD −3.0%→−3.9%). Same failure mode as value + slope.

### SYNTHESIS: additive factors are ORTHOGONAL-to-carry; carry-correlated factors are redundant
The full factor search converges on a structural rule. **WORKED (added to the book):** COT positioning
(corr vs carry **0.09**), carry-momentum (**0.03**) — both orthogonal to carry. **FAILED (redundant,
dilutive):** value (0.39 vs COT), yield-slope (carry-corr), skewness (0.41 vs carry) — all carry in
disguise. Carry is the dominant axis; extra edge comes ONLY from genuinely orthogonal dimensions
(positioning, rate-differential-change), never from another carry-flavored factor. **Rule for any future
factor idea: check its return-correlation to carry FIRST.** Deployable book = `carry_cot_mom` (3-factor).

### 5. Regime / risk-on–risk-off conditioning
An ML classifier on **cross-asset vol + credit spreads + positioning + rate state** that scales factor
exposure (lean into carry in calm regimes, into value/defensive in stress). This is the
"conditioning, not prediction" pattern that actually worked in crypto (the regime filter). **Data:**
FRED risk proxies + COT. **Guard:** distant-window validation; report IS–OOS gap.
> **Status (2026-07-16): DIAGNOSED → REJECTED as a de-risking gate.** The regime→carry relationship
> FLIPS across regime: on the long G10 history (has crashes) risk-off = where carry CRASHES (2008 −20%
> is all risk-off days) so a gate helps; on the deployable EM window (2015-26, no crash) risk-off = carry's
> BEST returns (Sharpe risk-OFF 1.19 vs risk-ON 0.45; carry_cot 1.67 vs 0.23) so a gate CUTS the best
> periods. A de-risking gate is thus (1) return-harmful in-regime (vol-target failure again — "always-on
> beats timed", nth confirmation); (2) tail-protective only vs crashes this window can't validate; (3)
> REDUNDANT — carry_cot's always-on positioning diversification already cut DD −17.8%→−4.1%; (4) built on
> an era/universe-UNSTABLE (sign-flipping) relationship → ML classifier would overfit. Crash protection
> comes from diversification, not a timed gate. Don't build the conditioning overlay.

### 6. Central-bank communication NLP
Hawkish/dovish scoring of FOMC/BOJ/ECB/SNB/BoE statements & minutes → a rate-differential-expectations
signal orthogonal to price. Modern-ML use case with **free text**. **Data:** central-bank text.
> **Status (2026-07-16): FEASIBILITY SPIKE → RED light (build not justified).** Fetched 8 FOMC statements
> (2021 dovish → 2022-23 hawkish → 2024 cuts) via WebFetch, lexicon-scored. (a) SCORER VALID — net-hawkish
> orders the tone cycle correctly (mean hawkish +130 vs dovish −57); the reproducible lexicon works. (b) NO
> FX SIGNAL — tone LEVEL vs USD move corr −0.13/−0.15 (wrong sign), tone CHANGE (surprise proxy) +0.10/
> −0.08 (~0). Anticipated CB communication is PRICED (post-statement drift is a fade / sell-the-news) —
> the program's efficient-market wall again. Caveat: n=8, Fed-only, USD numeraire (low power); a full
> multi-bank tone-SURPRISE build (tone vs a model of expected tone) is the only remaining hope but is a
> large speculative build against a low prior. Not pursued. Lexicon scorer kept as reusable infra if ever
> revisited. Spike code: /tmp/fomc_spike.py.

### 7. Positioning (CFTC COT) as a contrarian signal
Extreme net-speculative crowding precedes reversals. Free, weekly, lagged. Useful standalone and as a
feature for #4/#5.
> **Status (2026-07-16): LOADER BUILT + Phase-1/2 PASS — first non-price edge in the program.**
> `forex/data/cftc.py` `load_cot` (CFTC Socrata legacy futures-only, net non-commercial = long−short,
> keyed on stable contract code; `COT_CODES` for EUR/JPY/GBP/CHF/CAD/AUD/NZD/MXN/ZAR; history to 1986).
> Contrarian signal (fade crowding, 3yr rolling z, release-lagged): modern-era cross-sectional
> **Sharpe 0.71 (2018–26, 4bp, −6% DD)**, 0.35–0.42 (2010–26), cost-robust to ~8–15bp (turnover 11×/yr),
> **uncorrelated to carry (ρ=0.05)** → genuine diversifier. **Caveat:** modern-only — flips NEGATIVE
> pre-2010 (−0.44 in 2000–09), flat 2010–17; an in-regime (2018+) edge like carry, not multi-decade
> robust. **BLEND WITH REAL DEPLOYABLE BOOK = DECISIVE WIN (2026-07-16):** carry (real `TRADEABLE_CARRY`)
> + COT, corr −0.01, equal-risk mix **Sharpe 0.74→1.05 (full) / 0.85→1.06 (2018-26), maxDD −17.8%→−4.8%,
> Calmar 0.36→0.73** — biggest risk-adjusted improvement to the book in the program (annRet drop is a
> de-lever artifact; scale-free metrics + re-lever = ~40% more return at same risk, 1/3 the DD).
> **FRAMEWORK STRATEGY BUILT (2026-07-16):** `carry_cot` (`strategies/blend.py`, risk-parity carry +
> `positioning`), `PositioningStrategy` (`strategies/positioning.py`, contrarian dollar-neutral),
> `forex/features/positioning.py`, `DataView.positioning`, `build_carry_view` auto-loads COT. Reproduces:
> `carry_cot` vs `carry` (2018-26, 5bp) Sharpe 0.85→1.03, maxDD −17.8%→−4.1%, Calmar 0.39→0.87.
> **WALK-FORWARD VALIDATED (clean OOS, fixed params, fit no-op):** train 750d/test 250d, 8 windows —
> carry_cot Sharpe **0.96 vs carry 0.82**, Calmar **0.84 vs 0.38**, maxDD **−4.1% vs −17.8%**, far more
> consistent per-window. **`carry_cot` is now the deployable book** — remaining is the live-account switch,
> not research. COT is also the first feature for regime conditioning (#5).
> **DEEPENED (2026-07-16): FX-native COT is ONE-DIMENSIONAL.** Tested richer cuts vs net-spec level —
> positioning MOMENTUM is dead (chg_mom −0.94 Sharpe), OI-normalization no help, and level/commercial/
> percentile are all 0.97–0.99 correlated (same underlying). Percentile transform is more era-robust
> (2010–26 Sharpe 0.03→0.23) BUT that gain lives in 2010–17, outside the deployable IBKR window (2015+)
> where raw-level (0.68) is strongest → NO change to carry_cot warranted; current signal confirmed best.
> Momentum/OI/percentile/commercial retired as documented negatives. **Cross-MARKET positioning TESTED →
> NEGATIVE (2026-07-16):** commodity (gold/WTI/copper/silver/platinum) spec positioning → commodity FX
> (AUD/NZD/CAD/ZAR/MXN) sign-flips WITHIN the modern era (+0.089 12wk-corr 2010-17 → −0.076 2018-26),
> cross-sectional Sharpe directional −0.32 / contrarian +0.08 (≈0) — economically sensible but positioning
> doesn't cleanly lead the FX and the beta is unstable. **COT THREAD COMPLETE:** FX-own net-spec contrarian
> is the singular edge (deployed in carry_cot); all other cuts (momentum/OI/percentile/commercial/
> cross-market) are redundant, dead, or era-unstable. No more juice in COT.

### 8. Macro-surprise nowcasting
Economic-surprise (actual − consensus) drives short-horizon FX; an ML nowcast of the surprise vector
conditions entries. **Data:** release calendars + consensus (partly free).

---

## Tier 3 — harder / research (data or shorting constraints)

### 9. FX volatility risk premium
Systematically selling FX option vol earns a premium (Della Corte, Ramadorai, Sarno). **Blocked:**
needs FX options data (not free) and options execution — beyond spot/IBKR-FX for now.

### 10. Order-flow / customer-flow signals
Order flow has real predictive content (Evans & Lyons). **Blocked:** genuine flow data is expensive.

### 11. Time-series trend-following (CTA overlay)
Absolute-momentum trend on each pair; a diversifier and a crude regime signal. Easy to add; modest
standalone edge, better as an overlay.
> **Status (2026-07-14): signal BUILT; crash-overlay TESTED → static already captures it.** `trend.py`
> (tsmom / ema / donchian) is a blend component. A diagnostic *confirmed* trend is a convex carry-crash
> hedge (corr deepens −0.10→−0.30 in carry-down months; +0.48% mean in worst-decile carry months; +11%
> in 2008-10). BUT a state-conditioned **crash overlay** (`carry_trend_crash*`, tilt to trend on carry
> drawdown) **lost to the static blend** — worse Calmar *and deeper* drawdown at defaults, and hyperopt
> walked the tilt to ~0 (static). The static blend holds trend *continuously* so it's positioned before
> the crash; the dynamic tilt buys the hedge late (resample lag) and whipsaws into the recovery.
> **Always-on beats timed** (cf. #4). `carry_trend_voltarget` stands; crash variants kept as documented
> negatives. Trend's hedge is captured by *holding it*, not timing it.

### 12. EM carry extension
Bigger carry differentials in liquid EM (MXN, ZAR, PLN…) — but fatter crash tails and the crypto
"edge-lives-where-you-can't-cheaply-trade" wall. Add only after the G10 machinery + crash overlay are
proven, and model fills realistically.
> **Status (2026-07-16): DONE — THIS IS THE DEPLOYABLE BOOK.** EM carry revived the modern edge G10
> lost to ZIRP. G10+MXN+ZAR Sharpe **0.68 (2018–26)** vs G10-only 0.27; broadened to `TRADEABLE_CARRY`
> (G10 + MXN/ZAR/PLN/HUF/CZK/ILS, 15 ccy) → **Sharpe 0.69 full / 0.81 recent, cost-robust to 15bp,
> positive in both eras** — wider universe = better cross-sectional leg selection. Formalized:
> `config.TRADEABLE_CARRY`, `forex.data.ibkr.build_carry_view`/`fetch_daily` (IBKR spot for the CE-Europe
> legs FRED lacks + FRED rates), CLI routing, pre-trade odd-lot warning. **Paper-fill-validated on IBKR**
> (all 4 CE-Europe legs qualify+fill+flatten; USD 25k IdealPro min noted). The liquidity wall does NOT
> bite these EM. The full Phase 0–3 IBKR execution stack (preview → guarded placement → reconcile →
> auto-unwind) is built + paper-validated. Docs: README "EM carry" + memory `project_fx_em_carry_edge`.
> Remaining is deployment (live-account switch), not research.

---

### 13. Intraday (sub-daily) directional & reversion — CLOSED negative
Assessed a broad intraday idea set from an external list (currency-strength ranking, vol-spike
mean-reversion, cointegration/stat-arb, session-conditioned breakout) on IBKR 1h data (7 majors, 2y).
> **Status (2026-07-16): CLOSED — nothing tradeable.** Every mechanism fails cost on liquid majors:
> currency-strength *momentum* rejected (strength REVERTS intraday, rank-IC uniformly negative);
> cross-sectional reversion real in gross (~1.5 Sharpe) but **sub-spread** (net-negative at 2bp);
> vol-spike selective reversion sub-spread; cointegration only in CHF crosses (~10-day half-life, an
> SNB-peg artifact, **refuted OOS** with a 2015 de-peg tail); session breakout shows no continuation
> (hit ~50%). Confirms the price-only ceiling holds *intraday* too — the only edge is slow and
> cross-sectional. Full method + results: `docs/intraday-fx-assessment-plan.md`.

## Where ML helps vs where it's a trap

| ML is a real lever | ML is a trap |
|---|---|
| Vol *sizing* via EWMA (deployed) | A *learned* vol forecaster beating EWMA — tested end-to-end, lost (#4) |
| Regime / factor-timing conditioning (#5) | Deep nets on OHLCV windows (info-ceiling) |
| Extracting non-price signals: NLP (#6), positioning (#7), macro nowcast (#8) | More features / bigger models on a low-SNR target (overfits) |
| Cross-sectional ranking over a *feature-rich* factor set (gradient-boosted), OOS-validated | Complex models judged on in-sample fit |

## Data availability
- **Free (have or easy):** spot & rates (FRED — built), VIX/MOVE/credit (FRED), CFTC COT, PPP/REER
  (OECD/BIS via FRED), central-bank text.
- **Paid / hard:** FX options vol surfaces (#9), genuine order flow (#10), fast consensus feeds (#8).

## Suggested order
**Every price-based lever is now closed** (2026-07-16). #1–#4 done (momentum benched; value =
drawdown-halver; G10 blend has no modern edge; ML vol forecaster exhausted — EWMA wins). #11 trend done
(convex hedge, but static beats a timed crash overlay). #13 intraday done (nothing tradeable). **#12 EM
carry is DONE and IS the deployable book** (`TRADEABLE_CARRY`, Sharpe 0.69–0.81, paper-validated). So
the price/factor axis is exhausted — the only research frontier left is **non-price data**:

1. **CFTC COT positioning** (#7) — **NEXT.** The cheapest door into the non-price frontier the whole doc
   points at: free, weekly, lagged; works standalone (extreme spec-crowding precedes reversals) *and*
   becomes the first feature for regime conditioning (#5). Natural response now that every price-based
   edge (G10 factors *and* intraday) is closed. Add as a `DataView` COT loader → a contrarian
   `Strategy`, era-split OOS. Overlay it on the deployable EM-carry book (positioning-timed carry).
2. **Regime conditioning** (#5) on cross-asset vol + credit + COT + rate state — factor/exposure timing
   on top of the carry book; the ML frontier that isn't price-direction prediction.
3. **Central-bank NLP** (#6) / **macro-surprise nowcast** (#8) — need text/consensus feeds; options VRP
   (#9) and order flow (#10) remain data-blocked.

*Parallel non-research track:* deploy `TRADEABLE_CARRY` live (execution stack paper-validated; the only
remaining gate is the deliberate live-account switch — `allow_live` + `U…` account + live port).

## Key references
- Lustig, Roussanov, Verdelhan (2011), *Common Risk Factors in Currency Markets*.
- Menkhoff, Sarno, Schmeling, Schrimpf (2012), *Carry Trades and Global Foreign Exchange Volatility*.
- Menkhoff, Sarno, Schmeling, Schrimpf (2012), *Currency Momentum Strategies*.
- Asness, Moskowitz, Pedersen (2013), *Value and Momentum Everywhere*.
- Barroso, Santa-Clara (2015), *Beyond the Carry Trade: Optimal Portfolios of Currencies*.
- Della Corte, Ramadorai, Sarno (2016), *Volatility Risk Premia and Exchange Rate Predictability*.
- Evans, Lyons (2002), *Order Flow and Exchange Rate Dynamics*.
- Baz, Granger, Harvey, Le Roux, Rattray, *Dissecting Investment Strategies in the Cross Section and
  Time Series* (carry/value/momentum/trend, practitioner-oriented).

## Caveats
Short/survivor-biased samples inflate magnitudes; every FX factor has crash risk; published FX-ML is
frequently overfit; and the deepest wall — the price-only information ceiling — is not moved by a
better model, only by new information or (offshore) shorting/leverage. Treat this list as *hypotheses
to falsify* with the framework's OOS + distant-window discipline, not a menu of guaranteed edges.
