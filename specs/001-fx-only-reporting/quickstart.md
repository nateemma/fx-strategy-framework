# Quickstart: Validating FX-Only Performance Reporting

**Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md) | **Contract**: [contracts/cli-output.md](./contracts/cli-output.md)

How to prove the feature works. Everything here runs offline — no broker, no network, no API key
(FR-011).

## Prerequisites

```bash
cd ~/projects/forex
.venv/bin/python -m pytest -q        # baseline green before you start
```

Only one snapshot in the live `nav.csv` carries FX values, so the meaningful scenarios run against
**constructed histories** written to a temp directory. That is the point of the offline constraint:
the report is a pure function of its input file.

## Scenario 1 — FX figures are independent of the ETF sleeves (SC-002)

The load-bearing property. Build two histories identical in their FX columns but with wildly
different `nav`, and confirm the FX section is byte-identical between them while the whole-account
section differs.

- **Setup**: same `fx_net_base`/`fx_gross_base`/`fx_accrued_base` series; `nav` flat in one, +20% in
  the other.
- **Run**: the report against each.
- **Expect**: FX block identical; whole-account block different. Traces to C-01.

## Scenario 2 — Carry and spot reconcile (SC-003, C-05)

- **Setup**: a history where accrual falls while net rises — carry negative, spot positive, as the
  live book actually behaves.
- **Expect**: reported carry + spot equals reported total P&L exactly, and the negative carry is
  displayed rather than netted away.

## Scenario 3 — Rebalance days are excluded and counted (FR-008, C-04)

- **Setup**: a history with a `stock_positions` excursion (e.g. 13 → 20 → 20 → 13) mirroring the real
  2026-08-12 rebalance documented in [research.md R1](./research.md).
- **Expect**: the excursion days are excluded from ratio statistics, the excluded count is printed
  with its reason, and cumulative P&L (computed from endpoints) still spans the whole period.

## Scenario 4 — Statistics are suppressed below the threshold (FR-007, C-07)

- **Setup**: histories with 1, 4, and 25 FX-bearing observations.
- **Expect**: 1 → levels only; 4 → P&L and carry/spot split, ratios withheld with the count stated;
  25 → full statistics. No `nan`, `inf`, or `0` stand-ins at any size.

## Scenario 5 — Legacy histories still work (FR-010, C-08)

- **Setup**: a history with **no** FX columns at all — the pre-2026-08-16 schema.
- **Expect**: whole-account output matches today's, and the FX section reports itself unavailable
  rather than erroring.

## Scenario 6 — Guards hold on degenerate input

- Zero `fx_gross_base` (book fully closed) → no division error, observation dropped from returns.
- A multi-day gap in the curve → not annualised as a single-day move.
- Two snapshots on one day → collapsed to the day's last, same as the whole-account path.

## Live smoke test

```bash
.venv/bin/python scripts/track_report.py
```

Against today's real `nav.csv` this must print the whole-account section as before, plus an FX
section in **single-observation** mode (net 129, gross 996,532, accrued −841, P&L withheld). If it
prints a Sharpe from one row, C-07 is broken.

## Done when

```bash
.venv/bin/python -m pytest -q     # all green, including new tests
ruff check .                      # no NEW violations (21 pre-existing, see Backlog #8)
```

Plus each scenario above verified, and the live smoke test showing single-observation mode.
