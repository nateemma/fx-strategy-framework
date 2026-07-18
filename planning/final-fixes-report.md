# ETF-basket sleeve — final-review fixes

Branch: `impl/basket-sleeve`, commit `27d357c`.

## Fix 1 — per-order cap default too tight (`forex/run/basket.py`)
Changed `max_order_frac` default from `0.5` to `0.6` in `BasketExecution.__init__`. Inverse-vol
gives IEF (lowest vol) a natural weight ~0.49, which sat right against the old 0.5 cap and could
abort the first-ever rebalance. The raise-on-breach behavior is untouched — a genuine >60%
single-leg concentration still raises `RuntimeError` before any orders are placed (pre-pass check
at `forex/run/basket.py:129-130`).

No existing test asserted the old default value directly (all `max_order_frac` usages in
`tests/test_basket_execution.py` pass an explicit value), so no test needed updating for the
default change itself.

## Fix 2 — history drop threshold too strict (`forex/run/basket_weights.py`)
`inverse_vol_weights` required `counts >= lookback` (zero NaNs tolerated). Changed to
`counts >= lookback * 0.9` — at least 90% of the window must be present. NaN-std, zero-std, and
the all-invalid equal-weight fallback are unchanged.

Added two tests to `tests/test_basket_weights.py`:
- `test_few_missing_bars_kept`: a symbol with 3 isolated missing bars in the window (6 NaN
  returns, count=54 exactly at the 90% boundary) is kept.
- `test_many_missing_bars_still_dropped`: a symbol with only 19 of 60 returns present is still
  dropped even under the relaxed tolerance.

## Fix 3 — CSV tracks intent + wrong account
- `forex/run/basket.py`: added `account: str = ""` to `BasketReport`. On the placement path,
  `rebalance()` already resolves `acct = (ib.managedAccounts() or [""])[0]` for the paper-account
  guard; that same value is now threaded into the returned `BasketReport.account`. Preview path
  leaves it at the default `""`.
- `forex/run/basket_track.py`: `log_basket_positions` now writes a `complete` column (from
  `report.complete`); header is `timestamp, account, symbol, shares, weight, allocation, applied,
  complete`.
- `scripts/basket_rebalance.py`: CSV logging call now passes `report.account or args.account` —
  prefers the real traded account, falls back to the CLI `--account` value (relevant only for
  preview, which isn't logged anyway since logging is gated on `report.applied`).
- `tests/test_basket_track.py`: all fake `SimpleNamespace` reports now carry `.account` and
  `.complete`; assertions added for the new `complete` column (including a `False` case in the
  append test).

## Fix 4 — partial-fill test (`tests/test_basket_execution.py`)
Added `test_partial_fill_marks_incomplete`: sets `fake._fill_frac = 0.5` on a placement across two
symbols and asserts `report.complete is False` and that filled order quantities are below the
intended target — exercising the settle-wait loop's under-fill branch, previously untested.

## Verification
- `.venv/bin/python -m pytest tests/test_basket_weights.py tests/test_basket_execution.py
  tests/test_basket_track.py -q` → 32 passed.
- `.venv/bin/python -m pytest -q` (full suite) → 274 passed.

## Self-review
- No order-direction/sign logic touched (`BUY`/`SELL` selection in the placement loop and
  `_unwind`'s opposite-side flatten are unchanged).
- `_unwind` still wraps everything in `try/except` and never raises.
- Preview path (`self.preview` branch) still only reads data (`readonly=True` connect) and returns
  before any `placeOrder` call; `account` stays `""` there.
- Default `BasketExecution()` construction (`preview=True`) remains a no-op on IBKR beyond reads —
  safe by default.
