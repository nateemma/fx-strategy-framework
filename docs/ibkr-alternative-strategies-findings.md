# IBKR Alternative-Strategy Investigations — Findings (2026-07-17)

**Question:** the FX book (`carry_cot_mom`, WF Sharpe ~1.15) runs on IBKR paper. What *else* can IBKR be
used for to generate decent returns (~10%) without huge risk? Three adjacent asset classes were assessed,
each via cheap free-data feasibility gates before any build. This is the durable record.

## Summary verdict

| Track | Verdict | Why |
|---|---|---|
| **Crypto derivatives** | ✗ NO | Spot data ≤ freqtrade; the one shortable signal (funding-reversion on BTC/ETH nano perps) is real but **cost-dominated** and dead in the modern regime. |
| **Commodity futures** | ✗ NO | Free signals (trend, COT) real but **decayed to flat/neg post-2018**; the strongest factor (carry/roll) is **untestable on free data** (roll-gap artifact) — needs paid roll-adjusted data to even assess. |
| **Equity / ETF / options** | ~ one survivor | 5 candidates; only the **diversified risk-parity basket** clears a bar (Sharpe 0.8, −21% DD). No single strategy = "10% without huge risk". |
| **➡ FX book + basket COMBINATION** | ✓ **YES** | The actual answer: two uncorrelated sleeves → **~10% CAGR at −8% max drawdown, Sharpe ~1.5, every year positive.** |

**Core lesson:** "~10% without huge risk" is **not a single strategy** — 10% is a risk premium, so every
standalone route either carries the risk (options VRP, levered basket) or has been arbitraged away (factors,
trend). The answer is **combining uncorrelated sleeves and levering the blend modestly.**

---

## 1. Crypto derivatives — NO

- **Spot port pointless:** IBKR spot crypto (~20 coins) is same-or-worse data than binance.us+ccxt; the old
  freqtrade edge lived in illiquid alts, absent on IBKR's liquid majors.
- **New (Feb-2026):** Coinbase nano BTC/ETH perpetual futures on IBKR — shortable, funding-bearing. Unlocks
  the one signal that survived the crypto program (funding-reversion, Study #7).
- **Data feasibility PASS** (Binance Data Vision funding 2020+, free) but **signal-check FAIL:** funding-
  reversion gross-positive every era (real) but **cost-dominated** — net-of-cost dead by 5–10bp and negative
  in 2023–26. Cross-sectional on 2 assets (BTC/ETH) is dead. Majors are too efficient.
- Interest on idle USD cash (3.1–4.3%) is the only real benefit — needs no strategy.

## 2. Commodity futures — NO (pending a paid-data carry test)

- **Data feasibility PASS for 2 of 3 signals:** free deep data — Yahoo `=F` continuous (20 commodities, 26yr)
  for trend; CFTC COT (19 commodities, 40yr, reuses `forex/data/cftc.py`) for positioning.
- **Signal-check FAIL:** trend (TSMOM) and COT contrarian are real historically but **decayed to flat/neg in
  2018–26** even vol-targeted; XS-momentum dead. Same crowding-decay trap as G10 carry.
- **Carry (roll yield) — the strongest commodity factor — is UNTESTABLE on free data.** Unadjusted front-
  month continuous series' roll gaps *are* the carry signal with flipped sign (uniform −100% artifact,
  scales with contango depth: WTI +0.06 vs NatGas −0.19). A valid test needs roll-adjusted data (Norgate/
  Databento free trial). Shelved pending that.

## 3. Equity / ETF / options sprint — one survivor

Five candidates, free-data gate each, same bar (return / drawdown / modern-regime / equity-beta corr).
Orthogonality-to-FX was **demoted from a gate to a Phase-2 bonus** — a standalone-good strategy earns its
place regardless; the risk-relevant correlation is **to equity beta**, not to the FX book.

| # | Candidate | Verdict | Modern standalone | Equity corr |
|---|---|---|---|---|
| 1 | Options VRP (put-write/buy-write) | ✗ FAIL | ~7% but −40% DD | 0.85 |
| 2 | **Diversified RP basket** [SPY,TLT,IEF,GLD,DBC inverse-vol] | ✓ **PASS** | ~6–7% / Sharpe 0.8 / −21% DD | **0.48** |
| 3 | Cross-asset trend (TSMOM) | ✗ FAIL | ~0% modern, −32% COVID whipsaw | −0.03 |
| 4 | Equity style factors | ✗ FAIL | premia decayed (combo Sh 1.0→0.05) | low but no return |
| 5 | Momentum rotation (crypto analog) | ~ works, doesn't beat basket | ~6–7% / Sharpe 0.6 | 0.5 |

**Key sub-findings:**
- **Options VRP is equity-lite, not low-risk** — the vol premium *is* payment for bearing crash risk; you
  can't collect ~10% of it and avoid the tail. Useful only as a crisis-regime diversifier.
- **Equity-style diversification does nothing for risk.** Equal-weight sectors (0.99 corr, −52% DD) and a
  large/mid/small/value/growth/dividend/foreign/EM/REIT basket (0.97 corr, −55% DD) are *just the S&P*.
- **Adding "more asset classes" can backfire.** Piling EM-bonds/REITs/foreign onto the RP basket *raised*
  equity correlation (0.48→0.75) and worsened drawdown — those assets are equity-correlated. Diversification
  comes from uncorrelated *risk* (govt bonds, gold, trend), not ticker count. **Must risk-weight, not dollar-weight.**
- **Momentum rotation's crypto magic does NOT transfer.** Frequent rebalancing *hurts* on liquid ETFs
  (weekly Sharpe 0.54 < monthly 0.61 — whipsaw). The crypto winner leaned on survivorship + illiquid-alt
  concentration + extreme dispersion, none of which exist in efficient ETFs. Concentrated dual-momentum
  (top-1) is a notable crisis-alpha diversifier (corr 0.24, +21% in 2022) but standalone weak.

---

## 4. THE ANSWER — `carry_cot_mom` + RP basket combination

Two genuinely uncorrelated, high-Sharpe sleeves blended at equal risk. FX returns are **walk-forward OOS**
(`walk_forward(carry_cot_mom, view, train=750d, test=250d, 5bp)` — honest, de-biased); basket = inverse-vol
[SPY,TLT,IEF,GLD,DBC]. **WF window 2018-08 → 2026-05**. (In-sample full-backtest over 2015-10→2026-07 gives
near-identical blend numbers — Sharpe 1.54 / −8.1% DD — so the result is not an in-sample artifact.)

| Walk-forward OOS | Return | Vol | Sharpe | maxDD |
|---|---|---|---|---|
| FX book (`carry_cot_mom`, OOS) | 3.1% | 2.7% | **1.14** | −2.9% |
| RP basket | 11.1% | 9.9% | 1.12 | −19% |
| **corr(FX, basket)** | | | **+0.11** | (≈ uncorrelated) |
| **Equal-risk blend** (each → 10% vol, 50/50) | **11.3%** | 7.4% | **1.52** | **−8.2%** |
| **Blend scaled to ~10% CAGR** | **10.5%** | 6.4% | **1.59** | **−7.3%** |

- **Per-year (levered blend):** 2019 +17, 2020 +11, 2021 +6, **2022 +3**, 2023 +15, 2024 +9, 2025 +17.
  **Every year non-negative; worst 0.0%; +3% in 2022** (when SPY −18%, 60/40 −18%).
- vs SPY same window: ~13.7% CAGR but Sharpe ~0.84 and −34% drawdown. The blend gives ~75% of equity's
  return at **~1/4 of its drawdown** and nearly 2× the Sharpe.

**This is "~10% without huge risk"** — achieved by combination, not by any single strategy, exactly as the
theory predicted (two Sharpe~1.1 sleeves at corr 0.11 → blend Sharpe ~1.5; diversification cuts vol so the
10%-CAGR scaling runs at only ~6.4% vol). The FX Sharpe is the honest OOS 1.14 (= the recorded WF), so the
diversification — not an in-sample FX number — is doing the work.

### Honest caveats
- **Window has no 2008 GFC** (FX spot history limit). WF window includes 2018-vol, COVID-2020, 2022; the
  blend handled all. FX carry is structurally uncorrelated to equities, so 2008 should be fine, but untested here.
- **The basket leg's 2018–26 Sharpe (1.12) flatters its long-run 0.80** (2007–26 incl. 2008) — the benign
  window helps the *basket*, not the FX book. Through-cycle honest expectation: blend Sharpe **~1.3–1.4**,
  10% CAGR at maybe **−10 to −12% drawdown** — still comfortably clears "10% without huge risk".
- **Leverage is concentrated in the FX sleeve** (~3.8× its natural 2.7% vol to reach a 10%-vol contribution)
  — normal and IBKR-feasible for low-vol FX carry; the basket runs ~unlevered. Portfolio-level leverage ≈ 1×.
- Borrow cost modeled (SHY + 1.5% margin spread) in the levered figure.

### Next steps (if pursued)
1. Decide the FX-sleeve leverage / capital split and add the basket as a second sleeve on IBKR (the basket is
   trivially implementable: 5 ETFs, quarterly rebalance).
2. Optionally add the concentrated dual-momentum sleeve (corr 0.24) as a small crisis-alpha overlay.
3. Stress the blend against a synthetic/proxy 2008 (splice a pre-2015 FX-carry index + basket) before sizing.

## Reproduction
Scratchpad scripts (this session): `vrp_gate.py`, `basket_gate.py`, `basket_expanded.py`, `trend_gate.py`,
`factor_gate.py`, `momentum_rotation.py`, `combination_test.py` (in-sample), `combination_wf.py` (walk-forward).
Crypto/commodities: `crypto_funding_*`,
`commod_*`, `energy_carry_*`. Data: Yahoo chart API (ETFs, `=F` futures), CFTC Socrata (COT), Binance Data
Vision (crypto funding), EIA (energy curves), Ken French library (factors) — all free.
