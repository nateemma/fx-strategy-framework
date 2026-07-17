# ETF Risk-Parity Basket Sleeve

## Overview

The basket sleeve is a **quarterly-rebalanced inverse-volatility basket** of five ETFs:
- **SPY** (US equities)
- **TLT** (long-duration Treasuries)
- **IEF** (intermediate Treasuries)
- **GLD** (gold)
- **DBC** (commodities)

Each is weighted inversely to its 60-day rolling volatility, then scaled to integer shares. Default allocation: **$400k USD**.

Deployed on the IBKR PAPER account alongside the FX book (carry_cot_mom):
- **Basket** uses **cash** (no leverage).
- **FX book** uses **margin**.
- Both are tracked in the same account.

## Usage

### Preview (dry-run, read-only, default)

```bash
python scripts/basket_rebalance.py
```

Prints (read-only, no orders placed):
- Current NAV
- Proposed weights (inverse-vol computed from historical prices)
- Target share counts
- Orders needed (delta from current positions)
- Any legs skipped below `min_order_usd` (default 500)

### Place Orders

```bash
python scripts/basket_rebalance.py --confirm
```

- **Arms placement**: `--confirm` is **required** to place real orders (default is safe preview mode).
- **Safety gates**:
  - Paper-account check: refuses non-DU accounts unless `--allow-live`.
  - Per-order cap: no single leg > 50% of allocation.
  - Minimum order: skips legs < $500.
- Waits for all orders to settle, logs fills.
- **Appends position snapshot** to `basket_positions.csv` (timestamp, account, symbol, shares, weight, allocation, applied).

### Shell Wrapper

```bash
scripts/basket_rebalance.sh --confirm
```

Sourced with the venv; forwards all args to the Python CLI.

## Options

| Flag | Default | Purpose |
|------|---------|---------|
| `--allocation` | 400000 | Total USD to allocate |
| `--port` | 4002 | IB Gateway port |
| `--client-id` | 24 | IB client identifier |
| `--account` | env `FOREX_IB_ACCOUNT` or `DUQ218063` | Account name for CSV logging |
| `--csv` | `basket_positions.csv` | CSV path for position log |
| `--allow-live` | (flag) | Permit placement on live accounts (not recommended) |

## Scheduling

Quarterly rebalance is typically driven by:
- A cron job or launchd schedule.
- Manual run before major market close (e.g., month-end).

## Monitoring

- **Whole-account NAV**: tracked by `snapshot_nav.py` (daily).
- **Per-sleeve positions**: appended to `basket_positions.csv` on each placement.
- **Orders + fills**: printed to stdout/logged.

## Coexistence with FX Book

Both sleeves share the same IBKR paper account:

```
Account NAV (e.g., $1M)
├─ FX Book (carry_cot_mom, margin-based, ~$2M notional)
└─ Basket Sleeve (cash, $400k allocation)
```

No cross-sleeve coordination is needed; BasketExecution queries current positions and computes deltas independently.

## Troubleshooting

- **"refusing to place on non-paper account"**: Check `IB_PORT` and logged account. Ensure Gateway is logged into paper.
- **"order X exceeds max_order_frac"**: Single ETF delta > 50% of allocation. Reduce `--allocation` or split across multiple runs.
- **"placement failed after N orders; attempted best-effort unwind"**: Broker error mid-placement. Verify positions in IBKR; may need manual cleanup.
- **No historical data for symbol**: ETF not traded on IBKR, or API data stale. Retry; may be a brief connectivity issue.
