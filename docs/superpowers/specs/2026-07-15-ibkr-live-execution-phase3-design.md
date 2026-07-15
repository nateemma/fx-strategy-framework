# IBKR LiveExecution — Phase 3 (Rollback & Partial-Fill Handling) Design Spec

*Design spec. Status: approved 2026-07-15. The pre-live safety gate for `LiveExecution` placement. Two
additions: (1) **auto-unwind** — if a `placeOrder` fails mid-loop, best-effort cancel unfilled + flatten
filled orders from THIS rebalance and raise, so a partial placement never leaves a lopsided book
unattended; (2) **partial-fill flagging** — after settling, mark the rebalance INCOMPLETE (no auto-retry)
when any leg fills short of intent, so under-fills are surfaced, not silently reported as success.*

## Design decisions (user-approved)
- **Mid-loop failure → auto-unwind** (cancel unfilled + flatten filled from this batch, return toward the
  pre-rebalance state), then raise. The unwind itself places (flatten) orders — best-effort, each wrapped.
- **Partial fill → flag, do NOT retry.** Report intended-vs-actual, set `complete=False`, stop. No chasing
  fills (avoids churning cost in the illiquid moments where fills fail).

## Components

### 1. `RebalanceReport` (`forex/run/execution.py`)
Add `complete: bool = True` (a default — SimExecution and preview construct it unchanged / always True).
LiveExecution placement sets it False on any under-fill.

### 2. `LiveExecution` placement path
Track each placed order so both unwind and reconciliation can use it:
```python
placed = []   # list of (pair, trade, contract, intended_units)
try:
    make_order = self._make_order()
    for pair, units in c["orders"].items():
        if abs(units) < self.min_order_units:
            continue
        order = make_order("BUY" if units > 0 else "SELL", round(abs(units))); order.tif = self.tif
        tr = ib.placeOrder(c["contract"][pair], order)
        placed.append((pair, tr, c["contract"][pair], units))
except Exception as e:
    self._unwind(ib, placed)                       # cancel unfilled + flatten filled (best-effort)
    raise RuntimeError(f"placement failed after {len(placed)} orders; auto-unwound: {e}") from e
# settle + reconcile (all placed)
TERMINAL = ("Filled", "Cancelled", "ApiCancelled", "Inactive")
for _ in range(60):
    if all(tr.orderStatus.status in TERMINAL for _, tr, _, _ in placed): break
    ib.sleep(1)
fills, complete = {}, True
for pair, tr, _c, intended in placed:
    sgn = 1.0 if tr.order.action == "BUY" else -1.0
    qty = sum(float(f.execution.shares) for f in getattr(tr, "fills", [])) or float(tr.orderStatus.filled)
    fills[pair] = sgn * qty
    if abs(qty) < abs(intended) - 1.0:             # under-filled (1-unit tolerance)
        complete = False
return RebalanceReport(orders=fills, positions=c["positions"], equity=c["nav"],
                       turnover=c["turnover"], cost=cost, applied=True, complete=complete)
```

`_unwind(self, ib, placed)`:
```python
def _unwind(self, ib, placed):
    ib.sleep(2)                                    # let statuses settle
    for pair, tr, contract, _intended in placed:
        try:
            if tr.orderStatus.status not in ("Filled",):
                ib.cancelOrder(tr.order)           # unfilled remainder -> cancel
            filled = sum(float(f.execution.shares) for f in getattr(tr, "fills", [])) or float(tr.orderStatus.filled)
            if filled:                              # already filled -> flatten opposite
                opp = "SELL" if tr.order.action == "BUY" else "BUY"
                o = self._make_order()(opp, round(abs(filled))); o.tif = self.tif
                ib.placeOrder(contract, o)          # contract carries exchange=IDEALPRO already
        except Exception:
            pass                                    # best-effort: never let unwind raise
    ib.sleep(3)
```
- The unwind reuses the qualified `Forex(pair)` contract from `_compute` (exchange set) — avoids the
  "Missing order exchange" failure that a raw `positions()` contract would hit.

### 3. CLI `_format` (`forex/cli.py`)
When `rep.applied and not rep.complete`, prepend a prominent `"⚠ INCOMPLETE — partial fills; review"`
line to the ORDERS PLACED table. Complete placements unchanged.

## Testing (offline, hermetic — fake IB, no real orders)
Extend `_FakeIB`: add `cancelOrder(order)` (records `cancel_calls`); allow a per-call `placeOrder` failure
(e.g. `fail_on=2` → raise on the 2nd placeOrder) and configurable fill shortfall.
- **auto-unwind on mid-loop failure:** fake raises on the 2nd `placeOrder`; assert `rebalance` raises
  RuntimeError, and the unwind ran — the 1st (already-placed) order was cancelled and/or flattened
  (a flatten `placeOrder` recorded, or `cancel_calls > 0`). Assert the unwind never itself raises.
- **partial-fill flags incomplete:** fake fills a leg short of the order qty → `rep.complete is False`;
  a full-fill book → `rep.complete is True`.
- **_unwind is best-effort:** a fake whose cancel/flatten raises does not propagate out of `_unwind`.
- Existing placement/guard/sign tests unchanged (add `complete=True` default doesn't break them).
- `_format` shows the INCOMPLETE note when `complete=False`.
- Full suite green.

## Validation (paper, user runs)
1. Normal rebalance → `complete=True`, report unchanged.
2. (If reproducible) force a bad leg (e.g. a size that IBKR rejects) mid-book → confirm the auto-unwind
   cancels/flattens the placed legs and the account returns ~flat, with a clear raised error.
3. Confirm a partial fill (hard to force on paper) at least reports `complete` correctly on the happy path.
Then flatten. **After Phase 3 passes, the placement path is trusted for paper**; LIVE remains a separate,
explicit gate (`allow_live` + live account/port + a deliberate go), out of scope here.

## Out of scope
- Auto-retry of unfilled remainder (explicitly rejected — flag, don't chase).
- Restoring exact prior positions on a *maintenance* rebalance (unwind targets this-batch fills only;
  good enough — the deployable runs from flat monthly).
- Live account. Scheduling.
