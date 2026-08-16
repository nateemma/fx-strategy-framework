# FX Carry + ML Crash-Overlay — Research→Paper→Live Program

*Design spec. Status: approved 2026-07-10. Next step: implementation plan (writing-plans).*

A systematic FX research program that pivots the methodology proven on a prior crypto ML
program (rigorous walk-forward + distant-window validation, point-in-time causality, "judge
on P&L not model accuracy", staged cheap-gates) onto G10 currencies. The flagship idea is a
**carry strategy whose tail risk is managed by an ML "crash-avoidance" overlay**, taken
end-to-end: research → IBKR paper → small live sleeve. The pipeline built for the flagship is
then reused for further FX ideas.

---

## 1. Goal & success criteria

Build a **G10 carry strategy whose tail risk is managed by an ML crash-avoidance overlay**,
end-to-end (research → paper → live), then reuse the pipeline for further FX ideas.

Success is judged the way the crypto program was — **not on model accuracy**:

- **Research gate:** the overlay must improve the carry basket's **risk-adjusted return
  (Sharpe/Calmar) and cut max drawdown out-of-sample on a temporally-distant era** (the #1
  lesson carried over: adjacent walk-forward windows share a regime and give false confidence).
- **Paper gate:** live paper P&L tracks the backtest within noise over a sustained window
  (backtest ≡ live parity).
- **Live gate:** a small sleeve only, and only after the paper gate passes.

## 2. Project environment

- **Repo:** new project at `~/Documents/forex`, its own git, standard Python package layout —
  fully separate from the crypto freqtrade repo.
- **Broker / execution:** Interactive Brokers via the **`ib_async`** client. Start on a **paper
  account**. Instrument: **spot FX on IDEALPRO** (cash forex = real currency borrow, the purest
  carry). Micro-FX futures are noted as an alternative for cleaner financing transparency.
- **Data (free-first):**
  - **Prices:** IBKR historical FX (daily + intraday, ~decades).
  - **Rates / macro:** FRED (policy rates, OIS proxies, CPI and other releases, decades of
    history) — the non-price data that raises the information ceiling.
  - **Positioning:** CFTC **COT** (weekly) plus retail-sentiment feeds.
  - **Cross-asset risk:** VIX, MOVE, credit spreads, equity indices (FRED / Yahoo).
  - **Central-bank text:** FOMC / BOJ / ECB / SNB statements & minutes (for the later NLP phase).
- **Compute / ML:** continue **MLX + sklearn** on Apple Silicon. Models are small tabular
  classifiers / vol models — no GPU cluster needed.

## 3. Architecture (isolated, testable units)

- **`data/`** — one loader per source, feeding a cached **feature store** (parquet).
  **Point-in-time correctness is the core discipline** (the FX analog of causal lagging): macro
  releases lag their reference period (CPI is released weeks later; COT is Friday-for-Tuesday),
  so every series is stamped with its *release* date, never its reference date. This is where FX
  lookahead bugs live.
- **`features/`** — rate differentials, carry, value (PPP / REER), momentum, dollar factor,
  positioning, cross-asset risk, realized / implied vol.
- **`labels/`** — the carry-stress target (continuous, not rare-binary — see §6).
- **`models/`** — crash/stress model + vol forecaster, plus the **walk-forward CV harness**.
- **`backtest/`** — vectorized portfolio simulator (carry accrual, financing, spreads, slippage),
  metrics (Sharpe / Calmar / drawdown), and the **validation harness** (walk-forward +
  distant-window). Shares the same signal code path as execution.
- **`execution/`** — `ib_async` paper/live: order management, position reconciliation, and
  **backtest ≡ live parity** (a lesson from the crypto config-override bug — the live signal path
  must be byte-for-byte the same logic as the backtest).
- **`research/`** — one script per experiment, staged-gate style.

Design intent: each unit has one purpose, a well-defined interface, and is testable in isolation.
The feature store decouples data ingestion from modeling; the shared signal path decouples
strategy logic from whether it runs in backtest or live.

## 4. Strategy ideas (the set — flagship first; each phase opens with a cheap signal-gate)

1. **Flagship: G10 carry + ML crash-avoidance overlay.** Long high-yielders / short low-yielders
   (beta-neutral), with an ML model that scales the basket down ahead of unwinds using
   risk / positioning / vol features.
2. **Cross-sectional G10 factors.** Carry / value / momentum / dollar, ML-conditioned on macro +
   positioning — the cross-sectional-momentum framework from the crypto program, on a clean,
   non-survivorship-biased universe.
3. **ML volatility forecasting** for position sizing + the kill-switch (vol is predictable where
   direction is not; it sizes the carry and triggers the de-risk).
4. **NLP on central-bank communication** — hawkish/dovish scoring as a rate-differential-
   expectations feature.
5. **EM extension (later phase)** — add liquid EM carry once the machinery + overlay are proven.

## 5. Implementation & test plan (phased, gated)

- **Phase 0 — Environment.** IBKR paper account + `ib_async` connection; data pipeline with
  point-in-time stamping; vectorized backtester skeleton; validation harness.
  *Verify:* reproduce a known G10 carry-basket return from the literature within reason.
- **Phase 1 — Flagship.** Carry baseline → define the carry-stress target → build features → train
  the overlay model (walk-forward CV) → backtest overlay vs bare carry → **validate on a distant
  era**. *Gate:* the overlay improves OOS Sharpe/Calmar and cuts max drawdown on the distant
  window, after realistic costs.
- **Phase 2–4 — Expand** (cross-sectional factors, vol sizing, NLP), each behind its own
  signal-gate.
- **Paper gate.** Run the flagship on IBKR paper for a sustained window; confirm live ≡ backtest
  parity and execution / financing realism.
- **Live gate.** A small sleeve only, after the paper gate passes; hard risk limits and the
  kill-switch active.
- **Methodology (ported from the crypto program):** walk-forward, **distant-window validation**,
  **point-in-time data (no lookahead)**, realistic costs (spreads + financing), **judge on P&L not
  accuracy**, staged cheap-gates before deep work on any idea.

## 6. Risks & non-goals

- **The crash-sample problem (biggest statistical risk).** True carry unwinds are *rare* — a
  handful in decades (2008, the 2015 CHF de-peg, August 2024…). A binary "crash" classifier would
  have almost no positive labels and would overfit — the crypto "n≈2 payoff events" caveat in a new
  suit. **Mitigation:** model a **continuous carry-stress target** (forward drawdown severity /
  forward basket volatility) rather than rare binary events, and pool across all G10 pairs and
  decades to grow the effective sample. This is a central modeling choice, not an incidental one.
- **Macro lookahead** — mitigated by release-date stamping in the data layer (§3).
- **Regime shift** — the rate environment has moved (BOJ hiking to a multi-decade high, SNB at
  zero); distant-window validation is the guard.
- **Non-goal (explicit):** short-horizon FX *direction* prediction from price / TA — the
  efficient-market wall already mapped in the crypto program. Out of scope by design.

---

## Open items for the implementation plan

- Exact G10 pair list and how the beta-neutral carry basket is weighted.
- Precise definition of the continuous carry-stress target (horizon, normalization).
- The specific free feature set for v1 of the overlay (which FRED series, which COT fields,
  which cross-asset risk proxies).
- The literature carry-basket benchmark used for the Phase 0 reproduction check.
- Paper-gate duration and the pass/fail parity tolerance.
