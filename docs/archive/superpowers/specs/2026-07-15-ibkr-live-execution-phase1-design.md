# IBKR LiveExecution — Phase 1 (Order Preview) Design Spec

*Design spec. Status: approved 2026-07-15. Implement the stubbed `LiveExecution` (forex/run/execution.py)
against IBKR via `ib_async`, PREVIEW-ONLY: connect to the account, source current prices, compute the exact
FX orders to move from current positions to the strategy's target weights, and DISPLAY them — placing
NOTHING. This is the safe milestone that proves the strategy→weights→IBKR-orders chain end-to-end with
zero order risk. Order PLACEMENT is Phase 2 and is a hard `NotImplementedError` here.*

## Safety model (non-negotiable)
Phase 1 physically cannot place an order, guarded three independent ways:
1. **`readonly=True`** on `ib.connect(...)` — the library never attempts a write/order op.
2. **No order API is called** — the code contains zero `placeOrder`/`ib.placeOrder` calls. The
   non-preview branch raises `NotImplementedError("live order placement is Phase 2")`.
3. The user's TWS/Gateway **Read-Only API** setting (their guard).
Additionally: detect **Error 10197** (competing live session) and surface a clear "log out of your other
IBKR session" warning; never hardcode account IDs or credentials.

## The FX order math (the crux — must be exact)
The book is **USD-funded** (NAV, cash in USD). Target weights are per-currency, signed, as a fraction of
NAV (long positive / short negative). Each non-USD currency maps to ONE IBKR IDEALPRO pair, whose form is
given by the existing `CURRENCIES[c].spot_invert`:
- **`spot_invert=False`** (EUR, GBP, AUD, NZD): pair is **`{C}USD`** → `Forex("EURUSD")` = `EUR.USD`, base=C, native price = USD per C.
- **`spot_invert=True`** (JPY, CHF, CAD, NOK, SEK, MXN, ZAR, KRW): pair is **`USD{C}`** → `Forex("USDMXN")` = `USD.MXN`, base=USD, native price = C per USD.

(Verified against live conIds: EUR.USD, USD.JPY, USD.MXN, USD.ZAR all qualify with this rule.)

**Order in the pair's base-currency units** (how IBKR orders are placed), for target weight `w`, NAV `N`,
IBKR native midpoint `p`:
- `spot_invert=False` (base C): `target_base_units = (w * N) / p`  (long C ⇒ buy C.USD)
- `spot_invert=True`  (base USD): `target_base_units = -(w * N)`   (long C ⇒ sell USD.C; base is USD, so units are USD)

`order_units = target_base_units - current_base_units` (current from `ib.positions()`, matched by conId;
0 for a fresh account). Action = BUY if `order_units > 0` else SELL. The **USD-notional exposure**
per currency is simply `w * N` (convention-independent) — report it for readability.

## Price sourcing (competing-session-proof)
Streaming quotes fail under a competing login (Error 10197), but historical works. Source each pair's
current price via **`reqHistoricalData(contract, '', '2 D', '1 day', 'MIDPOINT', useRTH=False)`**, take
the last bar's `close` as the native midpoint `p`. One call per pair; no streaming.

## Components

### 1. `LiveExecution` (`forex/run/execution.py` — replace the stub)
```python
class LiveExecution:
    def __init__(self, host="127.0.0.1", port=4002, client_id=23, cost_bps=1.0, preview=True):
        ...  # store; do NOT connect in __init__

    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        # 1. connect(readonly=True); register Error-10197 handler -> self._competing flag
        # 2. read NAV (accountSummary NetLiquidation)
        # 3. for each non-USD currency with |w|>0: build pair (spot_invert), qualify,
        #    reqHistoricalData MIDPOINT -> native price p; compute target_base_units;
        #    read current from ib.positions() by conId; order_units = target - current
        # 4. if self._competing: print the log-out WARNING (prices unreliable) and still return preview
        # 5. build RebalanceReport(orders={pair: order_units}, positions={pair: target_units},
        #    equity=NAV, turnover=sum|w|, cost=cost_bps/1e4*turnover*NAV, applied=False)
        # 6. if not self.preview: raise NotImplementedError("live order placement is Phase 2")
        # 7. finally: ib.disconnect()
```
- Uses the passed `prices` (FRED USD-per-FX) only as an optional sanity cross-check, not for sizing.
- `RebalanceReport.applied` is always `False` in Phase 1.

### 2. CLI wiring (`forex/cli.py`, `dryrun` mode)
Add `--broker {sim,ib}` (default `sim`) and `--ib-port` (default 4002) to the `dryrun` subparser. When
`--broker ib`: construct `LiveExecution(port=..., cost_bps=cfg.cost_bps, preview=cfg.preview)` instead of
`SimExecution`, and call the same `rebalance_now`. Extend `_format`'s dryrun branch to print a readable
per-currency table (weight, USD-notional, pair, price, target units, current units, order BUY/SELL units)
and a header noting PREVIEW / no orders placed.

Run shape: `forex dryrun --strategy carry --universe EUR,JPY,...,MXN,ZAR --broker ib --preview`.

## Testing (offline — NO live IBKR in tests)
`ib_async` must not be imported at module top level (lazy import inside methods) so the suite runs without
it and without a broker. Tests inject a **fake IB** (a small stub exposing `connect/disconnect/
accountSummary/positions/qualifyContracts/reqHistoricalData/reqMarketDataType/errorEvent`) via a seam —
`LiveExecution` takes an optional `ib_factory` (default builds a real `ib_async.IB`); tests pass a fake.
Cover:
- **FX sign/units correctness** (the crux): a long-C `spot_invert=False` currency ⇒ positive base units =
  `w*N/p` and action BUY; a long-C `spot_invert=True` currency ⇒ negative USD base units = `-(w*N)` and
  action SELL; shorts flip. Assert exact numbers for a hand-computed 2-currency book.
- `applied` is always False; `not preview` ⇒ `NotImplementedError` and **no order method is ever called**
  on the fake IB (assert the fake records zero placeOrder calls).
- Error-10197 handler sets the competing flag and the warning is emitted.
- `rebalance_now` + `LiveExecution(fake)` produces a finite report.
- CLI `--broker ib --preview` builds a `LiveExecution` and formats the table (fake IB).
- Full suite green; `ib_async` optional dep added under `[project.optional-dependencies] live`.

## Validation (post-merge, manual — user runs against paper)
`forex dryrun --strategy carry --universe EUR,JPY,GBP,CHF,AUD,NZD,CAD,NOK,SEK,MXN,ZAR --broker ib
--preview` against the paper account (Gateway :4002). Confirm: connects, prints NAV $1M, computes a
sensible per-currency order table (longs = high-rate, shorts = low-rate), places nothing. This is the
Phase-1 acceptance gate.

## Out of scope (Phase 2+)
- Actual order placement / fill reconciliation / min-order-size rounding (Phase 2, paper first).
- Live streaming quotes (unneeded; historical midpoints suffice).
- Scheduling / automated monthly runs.
