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

### 2. Value / PPP mean-reversion
Long currencies cheap vs fair value (PPP / real effective exchange rate), short expensive ones; they
revert over 1–5 years. The third leg of the classic carry–momentum–value trio (Asness, Moskowitz,
Pedersen 2013, *Value and Momentum Everywhere*). **Data:** REER / PPP series (OECD/BIS, largely free
via FRED). **ML angle:** none for v1; the edge is the slow reversion.

### 3. Combined factor portfolio (carry + momentum + value)
The single most defensible "best" baseline: the three factors are low-correlated, so an
equal-risk or vol-weighted blend has a much higher Sharpe than any one alone (Baz et al.,
*Dissecting Investment Strategies*). **Framework:** a meta-`Strategy` that blends sub-strategy weights.
**ML angle:** factor *timing* (Tier 2) sits on top of this.

### 4. Carry crash / vol overlay — finish the ML stage
The EWMA vol-target overlay exists (Sharpe 0.34 → 0.40 hyperopt'd). The spec'd **Stage-B ML vol
forecaster** (gradient-boosted, cross-asset + positioning features, walk-forward CV, ships only if it
beats EWMA OOS) is the highest-conviction ML add — vol is predictable where direction is not, and
global FX vol is a *priced* carry-crash factor (Menkhoff et al. 2012, *Carry Trades and Global FX
Volatility*). **Data:** VIX/MOVE/credit (FRED), CFTC COT. **This is the flagship ML piece.**

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

### 12. EM carry extension
Bigger carry differentials in liquid EM (MXN, ZAR, PLN…) — but fatter crash tails and the crypto
"edge-lives-where-you-can't-cheaply-trade" wall. Add only after the G10 machinery + crash overlay are
proven, and model fills realistically.

---

## Where ML helps vs where it's a trap

| ML is a real lever | ML is a trap |
|---|---|
| Vol forecasting for sizing + crash avoidance (#4) | Predicting major-FX direction from price/TA |
| Regime / factor-timing conditioning (#5) | Deep nets on OHLCV windows (info-ceiling) |
| Extracting non-price signals: NLP (#6), positioning (#7), macro nowcast (#8) | More features / bigger models on a low-SNR target (overfits) |
| Cross-sectional ranking over a *feature-rich* factor set (gradient-boosted), OOS-validated | Complex models judged on in-sample fit |

## Data availability
- **Free (have or easy):** spot & rates (FRED — built), VIX/MOVE/credit (FRED), CFTC COT, PPP/REER
  (OECD/BIS via FRED), central-bank text.
- **Paid / hard:** FX options vol surfaces (#9), genuine order flow (#10), fast consensus feeds (#8).

## Suggested order
1. **Cross-sectional momentum** (#1) — free, natural, diversifies carry, proves the "second strategy on
   the framework" path.
2. **Value/PPP** (#2) → **combine into a carry+mom+value portfolio** (#3) — the defensible baseline.
3. **Stage-B ML vol forecaster** (#4) — the flagship ML piece; infra (walk-forward, hyperopt, config)
   is already built for it.
4. **Regime conditioning** (#5) + the non-price feature loaders (#6–#8) as the ML frontier.

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
