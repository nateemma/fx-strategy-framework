# Contract: `track_report.py` Command-Line Output

**Date**: 2026-08-16 | **Spec**: [spec.md](../spec.md)

The report is a CLI tool whose contract is its **invocation** and its **printed output**. Nothing
else consumes it programmatically, so the human-readable text *is* the interface.

## Invocation

```bash
.venv/bin/python scripts/track_report.py
```

- No arguments, no network, no broker connection, no API key (FR-011).
- Reads `nav.csv` from the working directory.
- Exit code `0` on success, including when statistics are suppressed for want of data.
- Exit non-zero only when `nav.csv` is absent or unreadable — unchanged from today.

## Output structure

Two clearly separated sections. Existing whole-account output is preserved (FR-010); the FX section
is added below it.

```
forward paper track — carry_cot_mom  (DUQ218063)

WHOLE ACCOUNT  (FX book + ETF sleeves)
  snapshots  : <n> over <start> -> <end>  (<days> days)
  NAV        : <first> -> <last>
  total return / annualized / vol / Sharpe / max drawdown
  note: the ETF sleeves are ~<pct>% of NAV, so these figures mostly measure them.

FX BOOK ONLY  (carry_cot_mom)
  observations : <n> over <start> -> <end>   (<k> excluded: rebalance flow)
  gross exposure: <gross>
  P&L          : <total>   (carry <carry>  +  spot <spot>)
  total return / annualized / vol / Sharpe / max drawdown
  returns are on gross FX exposure.
  backtest expectation (walk-forward): Sharpe ~1.15
```

## Required guarantees

| # | Guarantee | Traces to |
|---|---|---|
| C-01 | Both sections always labelled; FX figures never presented as whole-account or vice versa | FR-001, SC-006 |
| C-02 | The `~1.15` expectation appears **only** in the FX section | FR-004 |
| C-03 | Every FX figure is accompanied by its period and observation count | FR-006, SC-005 |
| C-04 | Excluded-observation count is always shown when non-zero, with the reason | FR-008 |
| C-05 | Carry + spot always sum to the reported total P&L | FR-005, SC-003 |
| C-06 | The return basis (gross FX exposure) is stated in the output | FR-009 |
| C-07 | Below minimum sample, ratios are replaced by an explanation — never printed as `nan`, `0`, or `inf` | FR-007, SC-004 |
| C-08 | With no FX-bearing rows, the whole-account section is byte-comparable to today's output and the FX section states it is unavailable | FR-010 |

## Degraded-mode outputs

**No FX data at all** (history predates the schema change):

```
FX BOOK ONLY  (carry_cot_mom)
  unavailable — no snapshot in this history records FX values.
  FX columns were added 2026-08-16; earlier rows cannot be reconstructed.
```

**Below the statistics threshold** (2–19 observations):

```
FX BOOK ONLY  (carry_cot_mom)
  observations : 4 over 2026-08-16 -> 2026-08-20
  P&L          : +312   (carry -108  +  spot +420)
  return / vol / Sharpe / drawdown need >= 20 observations (have 4) — not shown.
```

**Single FX-bearing row** (today's actual state):

```
FX BOOK ONLY  (carry_cot_mom)
  observations : 1 over 2026-08-16 -> 2026-08-16
  net value    : 129   gross exposure: 996,532   accrued: -841
  P&L needs at least 2 observations to difference — not shown.
```

## Explicit non-goals

- No machine-readable output (JSON/CSV) — nothing consumes this programmatically today, and adding a
  format would be speculative.
- No flags or options. The report answers one question; parameterising it invites the sample-slicing
  the project's methodology warns against.
- No writing. The report is strictly read-only over `nav.csv`.
