---
name: paper-track-live-state
description: What the IBKR paper account DUQ218063 held when the track STOPPED on 2026-10-14 — the FX book ran as a cash overlay on top of ETF sleeves that were ~90% of NAV. Positions left in place, not liquidated
metadata: 
  node_type: memory
  type: project
  originSessionId: 844844bf-ae57-49de-90f7-44d806550f05
  modified: 2026-08-16T21:28:10.947Z
---

**STOPPED 2026-10-14**, after 89 days (2026-07-17 → 2026-10-14). Final NAV ~990k from 994k at
inception, −0.4%. The automation was shut down but the **positions were deliberately left in place**,
so the account is a frozen snapshot rather than a flat one — 14 FX legs and 15 ETF positions. Read the
present tense below as "as at 2026-10-14".

The forward paper track (IBKR paper account **DUQ218063**, IB Gateway on port 4002) is not
"the FX book plus some sleeves" — it is **~90% ETF sleeves by market value with the FX carry book
layered on top as a financed cash overlay**:

- Substantially all of `GrossPositionValue` (~910k of NAV ~1,005k at 2026-08-16) is ETF sleeves. As of
  2026-08-21 there are five: basket ~268k (SPY/TLT/IEF/GLD/DBC), Treasury ladder ~300k (IBTG–IBTL
  iBonds), income ~298k (BIZD/JEPI), cash ~85k (SGOV, deployed 08-17), VIX carry ~30k (SVXY, deployed
  08-20, funded by trimming the basket 298k → 268k).
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

**How to apply:** don't attribute paper-track NAV moves to the FX strategy. FX-only P&L is now
isolated by `forex/run/fxtrack.py` (feature 001) — use it rather than NAV. Note the realised FX figure
is pre-financing; charging IBKR's actual spreads takes `carry_cot_mom` from Sharpe 1.15 to 0.17, which
is the finding that governs any deployment question. The factor research itself is converged and
closed — `docs/strategy-research-backlog.md` is the decision log; don't relitigate rejected factors
(value, slope, skew, regime conditioning, NLP, learned vol, all intraday).
