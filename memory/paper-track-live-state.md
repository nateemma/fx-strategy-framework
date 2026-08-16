---
name: paper-track-live-state
description: What is actually holding in the IBKR paper account DUQ218063 — the FX book runs as a cash overlay on top of three ETF sleeves that are ~90% of NAV
metadata: 
  node_type: memory
  type: project
  originSessionId: 844844bf-ae57-49de-90f7-44d806550f05
  modified: 2026-08-16T21:28:10.947Z
---

The forward paper track (IBKR paper account **DUQ218063**, IB Gateway on port 4002) is not
"the FX book plus some sleeves" — as of 2026-08-16 it is **~90% ETF sleeves by market value with the
FX carry book layered on top as a financed cash overlay**:

- `GrossPositionValue` ≈ 910k of NAV ≈ 1,005k. All of it is the three ETF sleeves, each ~300k:
  basket (SPY/TLT/IEF/GLD/DBC), Treasury ladder (IBTG–IBTL iBonds), income (BIZD/JEPI).
  All three still hold exactly the share counts written on 2026-07-17/18.
- The FX book (`carry_cot_mom`) holds **no stock positions at all**. It exists purely as long/short
  settled cash balances across 14 currencies — see [[fx-legs-are-cash-not-positions]].
- CZK is the one universe currency sitting flat; the other 14 non-USD legs are open.

Forward record started **2026-07-17** at NAV 994,314. Two FX rebalances so far: 2026-07-17
(turnover 0.284) and 2026-08-12 (turnover 0.434). Early realised numbers are far above the
walk-forward expectation (Sharpe ~3.7 vs ~1.15 expected) but the sample is ~1 month — not yet
meaningful, and the ETF sleeves, not the FX book, dominate the NAV move.

**Why:** the README describes the sleeves as running "alongside" the FX book, which understates how
lopsided the capital split is. Any read of `nav.csv` or NAV performance is mostly measuring the ETF
sleeves, not `carry_cot_mom`.

**How to apply:** don't attribute paper-track NAV moves to the FX strategy. To judge `carry_cot_mom`
you need FX-only P&L, which nothing currently isolates. The factor research itself is converged and
closed — `docs/strategy-research-backlog.md` is the decision log; don't relitigate rejected factors
(value, slope, skew, regime conditioning, NLP, learned vol, all intraday).
