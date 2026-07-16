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

### 5. Regime / risk-on–risk-off conditioning
An ML classifier on **cross-asset vol + credit spreads + positioning + rate state** that scales factor
exposure (lean into carry in calm regimes, into value/defensive in stress). This is the
"conditioning, not prediction" pattern that actually worked in crypto (the regime filter). **Data:**
FRED risk proxies + COT. **Guard:** distant-window validation; report IS–OOS gap.

### 6. Central-bank communication NLP
Hawkish/dovish scoring of FOMC/BOJ/ECB/SNB/BoE statements & minutes → a rate-differential-expectations
signal orthogonal to price. Modern-ML use case with **free text**. **Data:** central-bank text.

### 7. Positioning (CFTC COT) as a contrarian signal
Extreme net-speculative crowding precedes reversals. Free, weekly, lagged. Useful standalone and as a
feature for #4/#5.

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
