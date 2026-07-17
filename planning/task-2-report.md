# Task 2 report: BasketExecution

## Summary
Implemented `BasketExecution` in `forex/run/basket.py`, a long-only Stock/SMART executor for the
ETF risk-parity basket sleeve, parallel to `forex/run/execution.py::LiveExecution` (FX) but without
FX inversion or odd-lot handling. Uses Task 1's `inverse_vol_weights` and `target_shares` from
`forex/run/basket_weights.py` unmodified.

## Files
- `forex/run/basket.py` (new) — `BasketReport` dataclass + `BasketExecution` class.
- `tests/test_basket_execution.py` (new) — hermetic tests with a `_FakeIB` modeled on
  `tests/test_live_execution.py::_FakeIB`.

## Design / structure
Mirrors `LiveExecution`'s structure as instructed:
- **Two independent connect paths** (preview vs placement), each with its own `try/finally:
  ib.disconnect()` — matching `LiveExecution.rebalance`, not a single shared connection.
- **Lazy factories**: `ib_factory` (default `ib_async.IB()`), `contract_factory` (default
  `ib_async.Stock`, called as `contract_factory(sym, "SMART", "USD")`), `order_factory` (default
  `ib_async.MarketOrder`). Real `ib_async` is only imported when a factory isn't injected, so tests
  run with zero `ib_async` dependency.
- **`_compute(ib, allocation_usd)`**: shared by both preview and placement. Validates NAV, qualifies
  each symbol's contract (raises if no `conId`), pulls 120D/1D/MIDPOINT historical bars (raises if
  empty), validates the last price (finite, >0), builds a price-history `DataFrame` and a last-price
  `Series`, calls `inverse_vol_weights`/`target_shares`, then reconciles against current IBKR
  positions (`reqPositions()` + `sleep(1.5)` before reading, matching the FX comment about the
  reconnect-per-loop stale-snapshot bug) to produce signed `order_shares` per symbol.
- **Preview**: connects `readonly=True`, returns `BasketReport(applied=False)`, places nothing.
- **Placement**: requires `confirm=True` (checked *before* connecting, matching FX); connects
  `readonly=False`; DU-account guard (`allow_live` escape hatch); per-symbol loop does
  cap-guard → sub-min skip (recorded in `skipped`) → place via `order_factory` with `tif` set.
  Any exception mid-loop triggers `_unwind` (best-effort cancel-unfilled + flatten-filled, wrapped in
  try/except so it **never raises**) and re-raises `RuntimeError(... "VERIFY POSITIONS IN IBKR")`.
  After placing, waits (up to 60s) for all trades to hit a terminal status, then builds the fill
  report from executions, setting `complete=False` on any leg under-filled by >1 share.

One spec-reading judgment call: the numbered spec steps read almost like one linear function, but
the "mirror execution.py's structure" instruction (separate preview/placement paths each owning
their own connect/disconnect) takes precedence — this matches `LiveExecution` exactly and is what I
implemented. The per-order cap check and sub-min skip check live in a single per-symbol loop (not a
separate atomic pre-check pass like FX's gross-cap two-pass), per the literal spec wording — so a
cap violation on a later symbol can leave earlier orders already placed, which is exactly why it
routes through the same `_unwind` path as any other placement failure.

## Tests (7, all hermetic — no `ib_async` import)
1. `test_preview_places_nothing` — preview returns `applied=False`, zero `placeOrder` calls.
2. `test_placement_happy_path_buys_and_tif` — confirm=True on DU account places BUY orders for both
   symbols with `tif="DAY"`, positive filled quantities recorded in `rep.orders`.
3. `test_reconcile_no_overtrade_when_positions_match_target` — learns the target share count from a
   preview run, seeds a fresh fake with a matching position at the same deterministic `conId`, then
   asserts placement issues zero orders.
4. `test_non_paper_account_blocked_without_allow_live` — non-"DU" account raises, no orders placed.
5. `test_per_order_cap_raises` — a single-symbol basket (100% weight) with a near-zero
   `max_order_frac` raises before any `placeOrder` call.
6. `test_sub_min_order_skipped_and_recorded` — an absurdly high `min_order_usd` causes the order to
   be skipped and recorded in `rep.skipped`, zero `placeOrder` calls.
7. `test_midbatch_failure_triggers_unwind_and_raises` — `_fail_on=2` on a 2-symbol basket: order 1
   fills, order 2 raises, `_unwind` flattens order 1 with an opposite SELL, and the re-raised error
   matches `"VERIFY POSITIONS"`.

Weight math itself is not re-tested (Task 1's responsibility) — the fake IB returns synthetic
sinusoidal bar histories only to give `inverse_vol_weights` enough non-degenerate history to produce
nonzero, non-NaN weights.

## Verification
- `pytest tests/test_basket_execution.py -q` → 7 passed.
- `pytest -q` (full suite) → 267 passed, no regressions.
- Self-reviewed the diff: `_unwind` mirrors `LiveExecution._unwind` line-for-line in spirit (every
  fallible call wrapped in try/except, warnings printed not raised); no changes to `execution.py`,
  `basket_weights.py`, or any FX/CLI code; no speculative features beyond the spec (e.g. no gross-cap
  guard — not requested for the basket sleeve).

## Commit
`b2bd77f` — "feat: BasketExecution — long-only Stock/SMART executor for the ETF basket sleeve"
(2 files changed, 271 insertions: `forex/run/basket.py`, `tests/test_basket_execution.py`).

## Concerns / follow-ups for later tasks
- No CLI entry point yet (out of scope for Task 2 per spec — "Do NOT modify ... any FX/CLI code").
- `BasketExecution` has no gross-exposure cap (FX's `max_gross`); acceptable since the basket is
  long-only and each symbol is already capped individually via `max_order_frac`, but worth a
  conscious decision if the basket sleeve grows to many symbols.
- Pre-existing untracked files `planning/task-1-report.md` and `planning/task-1-review.txt` from
  Task 1 were left alone (not part of this task's diff).

## Review fixes (round 2)

Coordinator review of the first pass flagged three items; all three addressed:

1. **Per-order cap is now a pre-pass** (mirrors `execution.py:229-232`). Hoisted the
   `max_order_frac` check into its own loop over `c["orders"]`, run entirely BEFORE the `placed = []`
   placement loop. A cap breach on any symbol — including a later one — now raises before a single
   `placeOrder` call happens for the batch; nothing needs unwinding on this path (matches FX: the
   pre-pass raise sits before `placed = []` is even declared). The `min_order_usd` skip stays inside
   the placement loop as instructed (it only skips, never places, so it's safe to interleave with
   placement).
2. **Robust history assembly.** Each symbol's closes are now built as a `pd.Series` keyed by
   `b.date` (`history[sym] = pd.Series({b.date: float(b.close) for b in bars})`), and combined via
   `pd.concat(history, axis=1)` instead of `pd.DataFrame(history)` from equal-length lists. Unequal
   bar counts across symbols now align by date (missing dates become NaN) instead of raising a raw
   `ValueError`; `inverse_vol_weights` already tolerates NaNs (verified against Task 1's tests, which
   cover NaN-column dropping).
3. **Strengthened `test_per_order_cap_raises`** (renamed
   `test_per_order_cap_raises_as_a_prepass_before_any_placement`). Uses two symbols — TLT ($50,
   works out to ~11% weight, within a 0.5 cap) and SPY ($400, ~89% weight, breaches the 0.5 cap) —
   with TLT ordered first and SPY (the breaching symbol) second. Manually verified the weight split
   (`inverse_vol_weights` on the same synthetic series: TLT≈0.111, SPY≈0.889) before wiring the test,
   confirming SPY is the one that breaches. Asserts `placeOrder_calls == 0`, which would fail under
   the old in-loop-check implementation (TLT would have been placed before SPY's breach was
   discovered).

Also updated the fake `_Bar`/`reqHistoricalData` in `tests/test_basket_execution.py` to carry a
`.date` field (`_Bar(close, date)`), required by the new date-indexed history assembly.

### Verification (round 2)
- `pytest tests/test_basket_execution.py -q` → **7 passed**.
- `pytest -q` (full suite) → **267 passed**, no regressions.

### Commit (round 2)
`fd07cb3` — "fix: basket per-order cap as atomic pre-pass + date-aligned history
assembly" (`forex/run/basket.py`, `tests/test_basket_execution.py`).
