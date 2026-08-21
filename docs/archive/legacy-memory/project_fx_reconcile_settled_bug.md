---
name: project_fx_reconcile_settled_bug
description: "FIXED (2026-08-12) — FX reconcile now reads settled positions from CashBalance, not ib.positions(); monthly agent RE-ENABLED."
metadata: 
  node_type: memory
  type: project
  originSessionId: e1399a6e-effc-415c-9b11-ad051d604f86
---

**FIXED 2026-08-12 (commits e95699b + f21e721 on main).** Was: FX monthly rebalance
(`carry_cot_mom` via `LiveExecution._compute`) read current exposure from `ib.positions()`,
which is EMPTY for settled (T+2) FX — those live as per-ccy CASH BALANCES (accountValues
`CashBalance`). At monthly cadence (always settled) the reconcile saw the book FLAT and re-placed
the full target → doubled exposure. Verified live: preview turnover **0.879 (bug) → 0.086 (fix)**.

**The fix** (`forex/run/execution.py._compute`): current units come from the currency balance —
`cash_by_ccy = {v.currency: float(v.value) for v in ib.accountValues() if v.tag == "CashBalance"}`,
then per pair: **`XXXUSD` (non-inverted) → current = B_code ; `USDXXX` (inverted) → current = -B_code/price**
(consistent with the `target_units`/`_cexp` sign conventions). Plus a **guard**: if `cash_by_ccy` is
empty (cold-connect race, snapshot not populated) it RAISES rather than reading spurious-flat and
over-trading — a real account always carries ≥1 CashBalance (USD/base) once loaded. Tests in
`tests/test_live_execution.py` (settled-FX nets to 0 for both mappings; half-balance → half order;
empty-snapshot → refuse). Full suite 284 passed; live `forex dryrun --preview` through the patched
CLI = turnover 0.086.

**Validated in a REAL placement (2026-08-12)** — first live FX rebalance since deployment.
`monthly_paper_rebalance.sh` (refresh + `--confirm`) placed 7 legs, turnover **0.434** (a month of
genuine signal drift, correctly netted — NOT the 0.879 double-up; e.g. JPY flipped +7.5M long →
−4.9M short). All 7 filled; re-running the preview immediately after = turnover **0.082**
(placed legs net to ~0, only the deliberately-skipped sub-$25k odd-lot legs remain) — proving the
reconcile is **idempotent**. KEY FACT that closes the settlement question both ways: **IBKR updates
the per-ccy CashBalance on TRADE date** (fills showed in balances instantly), so the balance-based
reconcile is always current — no T+2 gap in either direction. (Unsettled trades ALSO appear
transiently in `ib.positions()`; that's why the OLD positions-only read missed them once settled.)

**`com.fx.paper-rebalance` launchd agent is RE-ENABLED** (next fires 1st of month). The carry
sleeve resumes safe monthly rebalancing. This is the deployed [[project_fx_cot_positioning]]
carry_cot_mom book; repo at [[project_repo_moved_to_projects]].

Known residual limits (out of scope, single paper account): multi-account / model-code
`accountValues` aren't account-filtered; a settled balance in a currency the strategy has since
dropped from the universe is never unwound (pre-existing, same as the old positions-based path).
`snapshot_nav.py` open_legs still counts only STK via `ib.positions()` (cosmetic; NAV correct).
