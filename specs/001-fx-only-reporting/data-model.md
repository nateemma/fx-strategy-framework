# Phase 1 Data Model: FX-Only Performance Reporting

**Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

No new persisted data. This feature reads the existing snapshot history and derives a P&L series from
it. The entities below are in-memory only.

---

## Source: Snapshot (existing, `nav.csv`)

One dated observation of the account. Written by `scripts/snapshot_nav.py`; unchanged by this feature.

| Field | Meaning | Notes |
|---|---|---|
| `timestamp` | UTC instant of the snapshot | Multiple rows per day possible |
| `account` | Broker account id | |
| `nav` | Whole-account net liquidation | Includes ETF sleeves (~90%) |
| `unrealized_pnl`, `realized_pnl` | Broker-reported P&L | Always 0 on this account; unused here |
| `stock_positions` | Count of broker positions | ETF holdings + **unsettled FX trades** |
| `fx_legs` | Open non-base currency legs | Empty before 2026-08-16 |
| `fx_net_base` | FX book value incl. accrued, base ccy | **The P&L level.** Empty before 2026-08-16 |
| `fx_gross_base` | Gross FX exposure, base ccy | The return denominator. Empty before 2026-08-16 |
| `fx_accrued_base` | Accrued-interest component of net | The carry leg. Empty before 2026-08-16 |

**Validation rules**

- A row is *FX-bearing* only if `fx_net_base`, `fx_gross_base`, and `fx_accrued_base` are all present
  and numeric. Rows failing this are excluded from FX statistics but retained for whole-account
  statistics (FR-006, FR-010).
- Rows are ordered by `timestamp` and collapsed to one observation per day, taking the day's last —
  the same convention the whole-account section already uses, so both cover identical days (FR-001
  edge case).

---

## Derived: FxObservation

One trading day of the FX book, built from consecutive FX-bearing daily snapshots.

| Field | Derivation |
|---|---|
| `date` | The day |
| `net_base` | `fx_net_base` of the day's last snapshot |
| `gross_base` | `fx_gross_base` of the day's last snapshot |
| `accrued_base` | `fx_accrued_base` of the day's last snapshot |
| `pnl` | `net_base` − previous observation's `net_base` |
| `carry_pnl` | `accrued_base` − previous observation's `accrued_base` |
| `spot_pnl` | `pnl` − `carry_pnl` |
| `ret` | `pnl` ÷ previous observation's `gross_base` |
| `gap_days` | Calendar days since the previous observation |
| `contaminated` | True when rebalance flow is present — see below |

**Validation rules**

- `carry_pnl + spot_pnl == pnl` exactly, by construction (SC-003). Spot is defined as the residual so
  the identity cannot drift.
- `ret` is undefined when the previous `gross_base` is zero or absent; such an observation is dropped
  from return statistics rather than yielding infinity (FR-011 edge case).
- The first FX-bearing day produces no observation — there is no prior to difference against.

---

## Derived: RebalanceFlag

Marks observations whose `pnl` contains trade flow rather than pure P&L (FR-008).

| Field | Derivation |
|---|---|
| `etf_baseline` | Mode of `stock_positions` over a trailing window of quiet days |
| `unsettled` | `stock_positions` − `etf_baseline`, floored at 0 |
| `contaminated` | `unsettled > 0`, **and** the observation immediately following one where it was |

The trailing observation is included because the settling trade's own P&L is split across the
settlement boundary. Validated in [research.md R1](./research.md): the 2026-08-12 rebalance placed 7
orders and drove `stock_positions` 13 → 20, returning to 13 at T+2 on 08-14.

**Validation rules**

- Contaminated observations are excluded from every FX *statistic* but MUST be counted and the count
  reported (FR-008) — silence would be indistinguishable from missing data.
- Cumulative P&L to date is reported from the raw endpoints and therefore *includes* contaminated
  days; this is correct, since the endpoints are levels, not differences.

---

## Derived: FxPerformance

The reported result. Suppressed below the minimum sample (FR-007; 20 observations per
[research.md R3](./research.md)).

| Field | Derivation | Gated? |
|---|---|---|
| `period_start`, `period_end`, `n_obs` | From the retained observations | No |
| `n_excluded` | Contaminated observations dropped | No |
| `total_pnl` | Last `net_base` − first `net_base` | No |
| `carry_pnl`, `spot_pnl` | Cumulative components | No |
| `total_return` | `total_pnl` ÷ first `gross_base` | No |
| `ann_return`, `ann_vol` | Annualised on 252 days | **Yes** |
| `sharpe` | Mean ÷ sd of `ret`, annualised | **Yes** |
| `max_drawdown` | On the cumulative P&L curve | **Yes** |

**State transitions**

```
no FX-bearing rows        → whole-account section only; FX section states "unavailable"
1 FX-bearing row          → FX levels shown; no P&L (nothing to difference)
2..19 observations        → P&L + carry/spot split; ratios withheld with reason
>= 20 observations        → full statistics, compared against walk-forward Sharpe ~1.15
```

---

## Relationships

```
nav.csv
  └─ Snapshot (many)
       └─ [filter FX-bearing, collapse to daily last]
            └─ FxObservation (many)   ──┐
                 └─ RebalanceFlag       ├─→ FxPerformance (one)
                                      ──┘
```

Whole-account statistics derive from `Snapshot.nav` on a path that never touches the FX entities —
which is what makes SC-002 (sleeve activity cannot move FX figures) structurally true rather than a
property to be tested for.
