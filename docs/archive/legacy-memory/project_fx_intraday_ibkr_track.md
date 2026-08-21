---
name: project_fx_intraday_ibkr_track
description: "FX intraday (IBKR 15/5-min) track — data pipeline works, trend has no edge; a real LiveExecution reconnect bug found"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

Exploratory "B" track (2026-07-15): a fast-timeframe FX strategy on **IBKR intraday data**, to (a) prove
IBKR-data backtesting and (b) watch a real strategy trade live on paper. Not for profit.

**IBKR intraday data pipeline WORKS.** `reqHistoricalData` gives clean N-min MIDPOINT bars (15-min: 2745
bars×9 ccy/30d; 5-min fine too). Build a spot panel (invert USD.X → USD-per-FX via `spot_invert`) + zero
rates (carry irrelevant intraday) into a `DataView`; the framework's `backtest` runs. **Annualize with
ACTUAL bars/year (~24,380 for 15-min FX), NOT the daily ×252** — the framework's `metrics` hardcodes 252,
so recompute Sharpe/vol with the right factor (or add a periods_per_year param if this is formalized).
This answers "can we backtest on IBKR data" = YES. (IBKR gives PRICES only, not rate series — so it's for
price strategies, not carry; carry still needs FRED.)

**Intraday trend is a cost-dominated LOSER (expected, not a real edge).** 15-min trend (ema/tsmom/donchian,
lookbacks 24/48/96 bars), 2bp cost: every config NEGATIVE Sharpe (−1.9 to −20.5), worse for shorter
lookbacks (more whipsaw + spread). 15-min FX ≈ random walk. Don't pursue intraday trend for edge.

**CORRECTION (do not repeat my error):** the A demo loop + B "live" loop I ran did NOT actually trade —
they ran in **preview mode**. `LiveExecution` defaults `preview=True`; passing `confirm=True` alone still
previews (places nothing). Direct-script loops MUST pass `preview=False`. So the "9 orders EVERY round /
over-trading bug" I reported was a **preview artifact** (flat account → recompute full book each round),
NOT a real snapshot lag. **The reliable, validated placement path is the CLI** (`dryrun --broker ib
--confirm` → sets preview=False), not ad-hoc scripts — stop hacking live loops.

**Loop-fix (committed) IS still valid + now validated:** `_compute` now does `ib.reqPositions() +
ib.sleep(1.5)` before reading positions so a FRESH connect doesn't read a spurious empty snapshot.
Validated 2026-07-16 via two separate CLI processes: cycle 1 established the carry book, cycle 2 (fresh
connect, same target) reconciled to **turnover 0.0 / 0 orders** — correct, no over-trade. So the fix is
real (needed for fresh-connect reconciliation); only my B-loop *evidence* for it was the preview artifact.

Related: [[project_fx_em_carry_edge.md]] (the real edge + the Phase 0–3 execution stack this reuses).
