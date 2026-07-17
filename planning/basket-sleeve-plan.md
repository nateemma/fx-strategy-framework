# Plan: ETF risk-parity basket as a second paper sleeve

## Goal
Add a self-contained ETF basket sleeve that runs alongside the FX book (`carry_cot_mom`) on the IBKR PAPER
account (DUQ218063). Basket = inverse-vol weights over `[SPY, TLT, IEF, GLD, DBC]`, quarterly rebalance,
long-only, allocated a fixed dollar amount ($400,000 by default). It reuses the FX book's proven safety
pattern (`forex/run/execution.py::LiveExecution`) but places `Stock`/SMART contracts, not FX `Forex`.

## Global Constraints (bind every task)
- **Universe (exact, ordered):** `["SPY", "TLT", "IEF", "GLD", "DBC"]`.
- **Weights:** inverse of trailing **60**-trading-day daily-return std, normalized to sum to 1.0, LONG-only.
  Zero/NaN-vol symbols → dropped from the normalization (never divide by zero); if all invalid → equal weight.
- **Sizing:** whole shares, `round(weight * allocation_usd / price)`.
- **Safety guards (mirror LiveExecution exactly):** preview path connects `readonly=True` and places nothing
  (`applied=False`); placement path requires `confirm=True`, connects `readonly=False`, checks the account
  starts with `"DU"` (else requires `allow_live=True`), enforces a per-order cap (`max_order_frac`, default
  0.5 of allocation), skips orders below `min_order_usd` (default 500), reconciles against current positions
  via `reqPositions()` + `ib.sleep(1.5)` then `positions()` keyed by `conId` (avoids the over-trade-on-
  reconnect bug), places `MarketOrder` with explicit `tif="DAY"`, waits for all orders to reach a terminal
  status, and on any placeOrder failure runs a best-effort unwind (cancel unfilled + flatten filled) that
  **never raises** before re-raising the original error with "VERIFY POSITIONS IN IBKR".
- **Hermetic tests:** all broker interaction goes through injectable factories (`ib_factory`,
  `contract_factory`, `order_factory`) exactly like LiveExecution, so tests use a fake IB (see
  `tests/test_live_execution.py::_FakeIB`) and never import `ib_async`.
- **No changes to FX code paths** (`execution.py` LiveExecution, the FX CLI, scheduled FX scripts). The
  basket is additive and independent.
- Python style matches the repo (no type-annotation-heavy code; terse, guard-first, matches execution.py).

## Task 1 — pure weight/share functions  (`forex/run/basket_weights.py`)
Two pure functions, fully unit-tested, no broker, no ib_async:
- `inverse_vol_weights(prices: pd.DataFrame, lookback: int = 60) -> pd.Series`
  - `prices`: columns = symbols, rows = daily closes (adjusted or raw — caller's choice).
  - returns weights (index = symbols present, summing to 1.0): inverse of the std of the last `lookback`
    daily pct-change returns, normalized. Drop symbols with NaN/zero vol before normalizing; if none remain,
    return equal weights over all input columns.
- `target_shares(weights: pd.Series, allocation_usd: float, prices: pd.Series) -> dict[str, int]`
  - `prices`: last price per symbol. Returns `{symbol: whole_shares}` = `round(w * allocation_usd / price)`,
    omitting symbols with non-positive price or zero resulting shares.
- **Tests** (`tests/test_basket_weights.py`): higher-vol symbol gets lower weight; weights sum to 1;
  zero-vol / NaN column handled; all-invalid → equal weight; `target_shares` rounds correctly and drops
  zero/invalid; a known small numeric example verified by hand.
- Model: **haiku** (self-contained, spec is complete).

## Task 2 — `BasketExecution`  (`forex/run/basket.py`)
Long-only Stock/SMART executor parallel to LiveExecution. Uses Task 1 functions.
- `@dataclass BasketReport`: `orders: dict` (symbol->signed shares traded), `positions: dict`
  (symbol->target shares), `weights: dict`, `equity: float` (NAV), `allocation: float`, `applied: bool`,
  `complete: bool = True`, `skipped: dict = {}` (symbol->usd for sub-min orders).
- `class BasketExecution` — `__init__(symbols=[...5...], host="127.0.0.1", port=4002, client_id=24,
  preview=True, confirm=False, allow_live=False, lookback=60, min_order_usd=500.0, max_order_frac=0.5,
  tif="DAY", ib_factory=None, contract_factory=None, order_factory=None)`. Default `contract_factory` lazily
  imports `ib_async.Stock` (call as `Stock(sym, "SMART", "USD")`); default `order_factory` lazily imports
  `MarketOrder`; default `ib_factory` imports `IB`. **client_id=24** (FX uses 23 — must differ).
- `rebalance(self, allocation_usd: float) -> BasketReport`:
  1. Connect (readonly in preview). Get NAV from `accountSummary()` NetLiquidation (validate finite/>0).
  2. For each symbol: qualify `Stock(sym,"SMART","USD")` (raise if no conId); `reqHistoricalData(c, "", "120 D",
     "1 day", "MIDPOINT", useRTH=True)`; build a price-history DataFrame + last-price Series (validate finite/>0).
  3. `weights = inverse_vol_weights(history, lookback)`; `shares = target_shares(weights, allocation_usd, last)`.
  4. Reconcile: `reqPositions(); ib.sleep(1.5)`; `cur = {conId: position}`; per symbol
     `order_shares = target - current`.
  5. Preview → return report with `applied=False`, no placement.
  6. Placement (confirm required): DU-account check; per-order cap (`|order_shares|*price/allocation >
     max_order_frac` → raise); skip `|order_shares|*price < min_order_usd` (record in `skipped`); place
     BUY/SELL MarketOrder(round(abs(shares))) tif=DAY; on failure `_unwind` (never raises) then re-raise
     "VERIFY POSITIONS IN IBKR"; settle-wait; fill report + `complete` flag (under-fill tolerance 1 share).
- **Tests** (`tests/test_basket_execution.py`) using a fake IB modeled on `_FakeIB` (extend it to return
  multi-bar history and per-symbol conIds/prices): preview places nothing & applied=False; placement places
  correct BUY/SELL shares with tif=DAY; reconcile produces zero orders when already at target (no over-trade);
  DU-account guard blocks a non-DU account without allow_live; per-order cap raises; sub-min order skipped;
  induced placeOrder failure triggers unwind and re-raises without masking. Weights come from Task 1 (don't
  re-test the math here).
- Model: **sonnet** (integration + judgment, mirrors a subtle guard/rollback pattern).

## Task 3 — runner script + per-sleeve tracking
- `scripts/basket_rebalance.py`: builds `BasketExecution` from env/args (`--confirm`, `--preview`,
  `--allocation` default 400000, `--port` default 4002, `--client-id` default 24), calls `rebalance`, prints
  a concise summary (weights, orders, skipped, applied), and on `applied` appends a row per held symbol to
  `basket_positions.csv` (columns: `timestamp, account, symbol, shares, price, market_value, weight`).
- `scripts/basket_rebalance.sh`: thin wrapper (mirrors `monthly_paper_rebalance.sh` header/guards style;
  quarterly cadence noted in comments; requires IB Gateway on port 4002 logged into the paper account).
- `docs/basket-sleeve.md`: what it is, how to run preview/placement, the $400k allocation, quarterly cadence,
  and that whole-account NAV is already tracked by `snapshot_nav.py` (this adds per-sleeve position logging).
- **Tests** (`tests/test_basket_runner.py`): the CSV-logging helper writes the expected header+row given a
  report (pure/temp-file test; no broker).
- Model: **haiku** (mechanical, spec complete).

## Out of scope (controller does this live, not a subagent)
- Live paper validation on the Gateway (preview → tiny 1-share test order → full $400k placement) and the
  actual placement. Done by the controller after the code lands + final review.

## Verification
- `pytest tests/test_basket_weights.py tests/test_basket_execution.py tests/test_basket_runner.py` all green.
- Full suite still green (no FX regressions).
- `python scripts/basket_rebalance.py --preview` produces a sensible weight/order preview (dry, no broker
  needed if a fake/preview path is exercised; real preview requires the Gateway).
