---
name: sleeve-table-is-design-not-deployment
description: The README's sleeve table describes the design, not what the account holds — check positions before assuming a sleeve is live
metadata:
  node_type: memory
  type: project
---

The README lists the ETF sleeves as though the table were the deployment state. It is not — it is the
design. Sleeves have repeatedly existed as built, tested, documented runners with **no position in the
account**.

The worked example: the **cash sleeve** (`scripts/cash_sleeve.py`, parks the buffer in SGOV) was
written, documented and listed for weeks while ~96k sat unparked and no SGOV had ever been held.
Verified against the live account 2026-08-16. It was deployed 2026-08-17 (SGOV 845 sh, ~85k) — and
only then did the guard bug surface that had made placement *impossible*: a single-symbol sleeve is
100% of its allocation, which exceeded the 0.6 `max_order_frac` cap, so every run aborted. It had to be
set to 1.0. **A sleeve that has never placed has never had its guards exercised.**

As of 2026-08-21 five sleeves are live: basket (~268k), Treasury ladder (~300k), income BIZD/JEPI
(~298k), cash SGOV (~85k), VIX carry SVXY (~30k). The futures trend sleeve is built and scheduled but
**not deployed** — it is blocked on a market-data subscription and refuses at 0 bars.

**Why:** documentation describes intent; only `*_positions.csv` and the account describe fact. The gap
between them is where silent non-deployment hides.

**How to apply:** before assuming a sleeve is live, check for its `*_positions.csv` and the actual
position. Expect the first real placement of any sleeve to surface a guard bug — the basket's per-order
cap aborted its first run, the cash sleeve's made placement impossible. Keep every sleeve's symbols
disjoint; `BasketExecution` reconciles by conId against the whole account. See
[[launchd-schedule-state]] and [[paper-track-live-state]].
