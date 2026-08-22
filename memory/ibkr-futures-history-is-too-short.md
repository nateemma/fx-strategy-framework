---
name: ibkr-futures-history-is-too-short
description: IBKR futures data works without any subscription, but retains only ~2 years of micros and ~8 expired contracts — the trend sleeve is blocked on retention, which no subscription can buy
metadata:
  node_type: memory
  type: project
---

Probed the live Gateway read-only on 2026-08-21, after three documents had recommended buying a
market-data subscription to unblock the futures trend sleeve.

**Futures data already works, with no subscription.** All eight markets (M2K MES M6E M6A ZT ZF ZC MCL)
return daily bars, no entitlement error, `usfuture` farm connects, US Futures Trading Permissions are in
place.

**What actually blocks the sleeve is history retention.** CONTFUT continuous series: MES/M2K from
2024-09, M6E/M6A from **2025-06** (298 bars), ZT/ZF from 2025-01, ZC from 2021-12, MCL from 2023-10.
`reqContractDetails(includeExpired=True)` returns only **8 contracts per market, earliest expiry
2025-12**. That is IBKR's contract-database retention and **a market-data subscription does not change
it** — there are no older contracts to buy data for.

So the A2 gate cannot be re-run on IBKR data (an era split needs ≥2 distant windows; 2 years is one),
and `strategies/trend_book.py` refuses anyway — `MIN_HISTORY` is 315 bars and M6E/M6A have 298.
Validating futures trend and testing commodity carry (Tier C1) now need the **same** purchase:
Databento roll-adjusted history.

**Beware the competing-session artifact.** Before this, every request returned 0 bars with error 10197
"No market data during competing live session" / "Trading TWS session is connected from a different IP
address". A second IBKR login anywhere — Client Portal counts, and the paper account draws entitlement
from the linked live account — cuts market data to the API entirely. **SPY failed identically**, so the
tell is that a known-good symbol breaks too. Account values keep flowing, so the connection looks fine.
0 bars is never by itself evidence about entitlement.

**Why:** two successive recommendations were wrong from documentation alone — first the product (the
$5 "Futures Value Bundle PLUS" is an L2 add-on requiring the $10 base bundle), then the premise
(entitlement was never the constraint). One read-only probe settled both.

**How to apply:** probe the live system before pricing a fix. Re-verify with
`scratchpad`-style read-only probes (`reqContractDetails`, `reqHistoricalData`, `ContFuture`) rather
than reading IBKR's pricing pages. See [[launchd-schedule-state]] and [[paper-track-live-state]].
