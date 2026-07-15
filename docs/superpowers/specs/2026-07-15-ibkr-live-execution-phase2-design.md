# IBKR LiveExecution — Phase 2 (Paper Order Placement) Design Spec

*Design spec. Status: approved 2026-07-15. Implement the order-PLACEMENT path in `LiveExecution`
(the non-preview branch), PAPER-ONLY, behind explicit software guards. Phase 1 (preview) already proves
the order computation; the conId reconciliation gate is validated on paper (FX reports as conId-matched
Position objects). Phase 2 adds: place the computed orders, wait for fills, reconcile, report — with a
confirmation flag, a paper-port guard, size caps, min-order rounding, and explicit TIF.*

## Safety model (the point of Phase 2)
Phase 1's hardware guard (`readonly=True`) is removed on the placement path; it is replaced by software
guards, ALL of which must pass before any `placeOrder`:
1. **`confirm` flag** — placement requires `confirm=True` (CLI `--confirm`). Without it, `rebalance`
   raises `RuntimeError("placement requires confirm=True")` before connecting. Dropping `--preview` alone
   does NOT place.
2. **Paper-port guard** — refuse unless `port in {4002, 7497}` (paper) OR `allow_live=True` (a separate,
   deliberately awkward flag we do NOT use yet). Non-paper port without `allow_live` → raise.
3. **Size caps** — reject the WHOLE rebalance (raise, place nothing) if any single order's
   `|notional|/NAV > max_order_frac` (default **0.25**) or total gross `sum|target_notional|/NAV >
   max_gross` (default **1.2**). Caps are constructor params / CLI flags. NOTE: a 3/3 carry book has 33%
   legs and will trip 0.25 on the first (from-flat) rebalance — run 4/4 (25% legs) or pass a higher
   `--max-order-frac`; this is intended friction, surfaced not silently widened.
4. **Min-order rounding** — orders with `|units| < min_order_units` (default IDEALPRO ~20k base units,
   configurable) are skipped (rounded to zero), not placed.
5. **Explicit TIF** — every order carries an explicit TIF (default `"DAY"`) to avoid the Error-10349
   preset-cancel noise seen in the gate test.

Connect `readonly=False` ONLY on the confirmed placement path; the preview path keeps `readonly=True`.

## Components

### 1. `LiveExecution` (`forex/run/execution.py`)
Factor the shared computation out of `rebalance` into `_compute(ib, target_weights) -> dict` returning
`{nav, orders{pair:units}, positions{pair:units}, base_usd{pair:bool}, price{pair:p}, turnover}` (exactly
the Phase-1 math, unchanged — the preview path and placement path both use it, so the validated sign
logic is shared). Add constructor params: `confirm=False, max_order_frac=0.25, max_gross=1.2,
min_order_units=20000, allow_live=False, tif="DAY"`.

```python
def rebalance(self, target_weights, prices) -> RebalanceReport:
    if self.preview:
        ib = connect(readonly=True); c = self._compute(ib, target_weights)
        return RebalanceReport(..., applied=False)          # Phase 1, unchanged
    # ---- placement path ----
    if not self.confirm:
        raise RuntimeError("placement requires confirm=True (pass --confirm)")
    if self.port not in (4002, 7497) and not self.allow_live:
        raise RuntimeError(f"refusing to place on non-paper port {self.port} without allow_live")
    ib = connect(readonly=False)
    c = self._compute(ib, target_weights)
    # size caps (reject whole rebalance, place nothing)
    gross = sum(abs(c["positions"][p]) * (c["price"][p] if not c["base_usd"][p] else 1) ... )/nav  # use USD-notional = |w*NAV|; simpler: gross = sum|w|
    for pair, units in c["orders"].items():
        notional = abs(units) * (1 if c["base_usd"][pair] else c["price"][pair])   # USD-notional of the order
        if notional / c["nav"] > self.max_order_frac:
            raise RuntimeError(f"order {pair} {notional/nav:.0%} exceeds max_order_frac {self.max_order_frac:.0%}")
    if gross > self.max_gross:
        raise RuntimeError(f"gross {gross:.2f}x exceeds max_gross {self.max_gross}")
    # place (skip sub-min), wait fills, reconcile
    from ib_async import MarketOrder
    trades = []
    for pair, units in c["orders"].items():
        if abs(units) < self.min_order_units:  # min-order rounding
            continue
        contract = <qualified contract for pair>          # reuse from _compute
        order = MarketOrder("BUY" if units > 0 else "SELL", round(abs(units)))
        order.tif = self.tif
        trades.append((pair, ib.placeOrder(contract, order)))
    fills = self._await_fills(ib, trades)                 # poll orderStatus to Filled/timeout
    return RebalanceReport(orders={p: filled_signed_units}, positions=c["positions"],
                           equity=c["nav"], turnover=c["turnover"], cost=<from fills>, applied=True)
```
- `_await_fills` polls each trade's `orderStatus.status` to `Filled` (or timeout → report partial +
  raise/flag). Uses `ib.sleep`.
- Injectable `order_factory` seam (mirroring `ib_factory`/`contract_factory`) so a fake records placed
  orders in tests WITHOUT ib_async and WITHOUT any real placement.
- `_compute` must retain the qualified contract per pair (return `contract{pair}`) so placement reuses it
  rather than re-qualifying.

### 2. CLI (`forex/cli.py`, dryrun)
Add `--confirm` (store_true), `--max-order-frac` (float, default 0.25), `--allow-live` (store_true,
hidden/awkward). Thread into `RunConfig` + `LiveExecution(confirm=..., max_order_frac=..., allow_live=...)`.
`--broker ib` without `--preview` and without `--confirm` → the executor raises the clear "requires
confirm" error (fails safe). `_format` prints, for `applied=True`, the actual FILLS (pair, filled units,
avg price) and a "ORDERS PLACED" header.

## Testing (offline — NO real IBKR, NO real orders)
Fake IB extended with a `placeOrder` that returns a fake Trade whose `orderStatus` is `Filled` at a set
price, and records calls. Inject via `ib_factory` + `order_factory`. Cover:
- **confirm guard:** `confirm=False`, preview=False ⇒ `RuntimeError`, and fake records **zero**
  `placeOrder` calls.
- **paper-port guard:** `port=7496` (live), `allow_live=False`, confirm=True ⇒ `RuntimeError`, zero orders.
- **size caps:** an order > `max_order_frac` ⇒ raise, zero orders placed (whole rebalance rejected);
  gross > `max_gross` ⇒ raise. A book within caps ⇒ orders placed.
- **min-order rounding:** an order below `min_order_units` is skipped (not placed).
- **placement happy path:** within caps, confirm=True, paper port ⇒ correct number of `placeOrder` calls,
  correct BUY/SELL actions + signs (reuse Phase-1 sign assertions), explicit `tif` set on each order,
  `applied=True`, fills reported.
- **Phase-1 preview path unchanged** (still `applied=False`, readonly, zero orders).
- Full suite green; hermetic (no ib_async needed via the injected seams).

## Validation (manual, PAPER — user runs, then flatten)
1. `forex dryrun --strategy carry --universe …,MXN,ZAR --broker ib --confirm` on a book that FITS the
   0.25 cap (n_long=4/n_short=4, or `--max-order-frac 0.4` for 3/3) → confirm it places the carry orders
   on paper, reports fills, account reconciles to target. Read positions back to verify.
2. Re-run to confirm it computes ~zero orders when already at target (reconciliation works).
3. Flatten (a one-shot flatten helper or a zero-weight rebalance) to leave the paper account clean.
Only after this passes cleanly is any live discussion (a *separate*, later, explicitly-gated step).

## Out of scope
- Live (funded) account — `allow_live` exists but stays off; live is a separate future decision.
- Limit/algo orders, partial-fill retry loops, scheduling. Market orders + explicit TIF only.
