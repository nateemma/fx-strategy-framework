---
name: fx-legs-are-cash-not-positions
description: "IBKR reports settled FX spot as CashBalance and holds the carry in a separate AccruedCash tag — read the FX book via forex.run.fxbook, never from positions()"
metadata: 
  node_type: memory
  type: project
  originSessionId: 844844bf-ae57-49de-90f7-44d806550f05
  modified: 2026-08-16T21:28:19.159Z
---

Two IBKR reporting facts that together decide how the FX book must be measured:

1. **Settled FX spot never appears in `ib.positions()`** — it lands in `CashBalance` per currency.
   positions() carries an FX trade only between execution and settlement.
2. **`CashBalance` excludes accrued interest**, which sits in a separate `AccruedCash` tag. For a
   carry book the interest differential *is* the return, so cash alone omits the strategy's P&L
   until it settles.

`forex/run/fxbook.py` (`fx_book`, added 2026-08-16) encapsulates both: it values
`CashBalance + AccruedCash` at each currency's `ExchangeRate`, excluding USD and IBKR's synthetic
`BASE` row. **Use it rather than re-deriving the arithmetic.** Its `net_base` reproduces IBKR's own
`NetLiquidationByCurrency` aggregation exactly — a useful cross-check if it is ever changed.

`net_base` is the FX P&L level: ETF trades move only USD cash, so they leave it untouched, and its
change between snapshots is FX-only P&L (plus that day's net flow on a rebalance day).

**Reconciliation gotcha:** the cash part of `net_base` will *not* equal IBKR's `BASE` minus `USD`
CashBalance to the cent. IBKR aggregates BASE on its own rate snapshot, which drifts from the
`ExchangeRate` rows by a small fraction of the ~1M gross book (~225 base, 0.025%, on 2026-08-16).
Don't chase that gap — it is rate drift, not a maths error.

**Historical note:** `nav.csv` had an `open_legs` column until 2026-08-16 that actually counted ETF
stock positions, not FX legs (13 on quiet days; 20 on 2026-08-12/13 = 13 ETFs + 7 unsettled FX
orders). It is now `stock_positions`, with real FX legs in `fx_legs`. Rows before 2026-08-16 have
empty FX columns — that history cannot be reconstructed.

**How to apply:** never infer FX-book state from `positions()` or from NAV. See
[[paper-track-live-state]] for why NAV mostly measures the ETF sleeves.
