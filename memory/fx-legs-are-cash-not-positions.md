---
name: fx-legs-are-cash-not-positions
description: "IBKR reports settled FX spot as CashBalance, never in positions() — so nav.csv's open_legs column counts ETFs, not FX legs"
metadata: 
  node_type: memory
  type: project
  originSessionId: 844844bf-ae57-49de-90f7-44d806550f05
  modified: 2026-08-16T21:28:19.159Z
---

At IBKR, **settled FX spot does not appear in `ib.positions()`** — it lands in `CashBalance` per
currency. Positions only shows FX transiently, between trade and settlement.

Consequence found on 2026-08-16: `scripts/snapshot_nav.py` computes
`n_pos = sum(1 for p in ib.positions() ...)` and writes it to `nav.csv` as **`open_legs`**, with the
inline comment "open FX legs (FX = cash, so gross=0)". That comment is wrong about what the line
does. The number is really **the 13 ETF stock positions**, plus any unsettled FX trades. That is why
`open_legs` reads 13 on quiet days, spiked to 20 on 2026-08-12/13 (13 ETFs + 7 unsettled FX orders
from that day's rebalance), and fell back to 13 by 2026-08-14 once they settled.

Commit `e95699b` ("read settled FX from CashBalance instead of positions()") fixed this in the
reconcile path. **`snapshot_nav.py` was never fixed** and still carries the misleading name and
comment.

**Why:** `open_legs` looks like an FX-book health metric and isn't one. Reading it as "the FX book has
13 legs open" is wrong in both directions — it would keep reading 13 even if every FX leg were closed.

**How to apply:** to count real FX legs, read non-zero non-USD `CashBalance` entries from
`ib.accountValues()`. Treat any `open_legs` spike in `nav.csv` as unsettled-trade noise, not a
position change. See [[paper-track-live-state]].
