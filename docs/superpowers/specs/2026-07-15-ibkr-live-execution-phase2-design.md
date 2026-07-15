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
2. **Paper-account guard (primary, ground-truth)** — after connecting, read `ib.managedAccounts()`;
   refuse to place unless the account ID starts with **`DU`** (IBKR paper prefix; the funded live account
   is `U…`) OR `allow_live=True` (a separate, deliberately awkward flag we do NOT use yet). The account ID
   is the ground truth for paper-vs-live, not the port. Port `∈ {4002, 7497}` is a secondary sanity check
   only. A non-`DU` account without `allow_live` → raise, place nothing.
3. **Size caps** — reject the WHOLE rebalance (raise, place nothing) if any single order's
   `|notional|/NAV > max_order_frac` (default **0.25**) or total gross `sum|w| > max_gross`
   (default **2.5**). Caps are constructor params / CLI flags. NOTES: (a) a dollar-neutral long-short book
   is inherently ~**2.0× gross** (long 1.0 + short 1.0), so the gross cap must sit ABOVE 2.0 — 2.5 admits
   the normal book plus vol-target leverage headroom and still catches a price-error blowup; a 1.2× cap
   would reject every carry rebalance. (b) A 3/3 carry book has **33% legs** and trips the 0.25 per-order
   cap on the first (from-flat) rebalance — run 4/4 (25% legs) or pass a higher `--max-order-frac` at
   validation; intended friction, surfaced not silently widened.
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
    ib = connect(readonly=False)
    acct = (ib.managedAccounts() or [""])[0]
    if not acct.startswith("DU") and not self.allow_live:
        raise RuntimeError(f"refusing to place on non-paper account {acct!r} (not DU-prefixed) without allow_live")
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
- **paper-account guard:** fake `managedAccounts()` returns a live-style `U1234567` with `allow_live=False`,
  confirm=True ⇒ `RuntimeError`, **zero** `placeOrder` calls; a `DU…` account passes the guard.
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
