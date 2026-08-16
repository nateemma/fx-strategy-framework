---
name: cash-sleeve-never-deployed
description: scripts/cash_sleeve.py exists and is documented in the README but has never been run — no SGOV is held and ~96k sits unparked
metadata: 
  node_type: memory
  type: project
  originSessionId: 844844bf-ae57-49de-90f7-44d806550f05
  modified: 2026-08-16T21:28:27.263Z
---

The README lists a **cash sleeve** (`scripts/cash_sleeve.py`, parks the cash buffer in SGOV) as one of
the four ETF sleeves in the multi-sleeve track. Verified against the live account on 2026-08-16:
**there is no SGOV position and never has been.** The runner was built and documented but never
executed. There is also no `*_positions.csv` for it, unlike the other three sleeves.

Meanwhile `TotalCashValue` on DUQ218063 is ~96k base — the buffer the sleeve was written to park.

**Why:** the README's sleeve table reads as a description of what is deployed, so it is easy to assume
all four sleeves are live. Only three are (basket, bond ladder, income). This is the gap between the
documented design and the actual account.

**How to apply:** treat the README sleeve table as the design, not the deployment state — check
positions before assuming a sleeve is live. If deploying the cash sleeve, keep its symbols disjoint
from the other sleeves (BasketExecution reconciles by conId against the whole account and cannot tell
one sleeve's holding from another's), and note it would need a schedule too — see
[[launchd-schedule-gaps]] and [[paper-track-live-state]].
