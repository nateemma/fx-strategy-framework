---
name: project_repo_moved_to_projects
description: "Repo MOVED ~/Documents/forex -> ~/projects/forex (macOS TCC fix). Install = pip install -e \".[dev,probe,live]\". Old memory paths are stale."
metadata: 
  node_type: memory
  type: project
  originSessionId: e1399a6e-effc-415c-9b11-ad051d604f86
---

**The forex repo now lives at `~/projects/forex`** (moved 2026-08-01 from `~/Documents/forex`).
Reason: macOS TCC protects `~/Documents`/`~/Desktop`/`~/Downloads`, so launchd agents got
`Operation not permitted` / `ModuleNotFoundError` when running scheduled jobs there. `~/projects`
is NOT TCC-protected → scheduled jobs work without any Full Disk Access grant. Verified: the NAV
snapshot launchd agent now writes `nav.csv` (test-fired 2026-08-01, NAV 986,689).

**Any memory or doc that says `~/Documents/forex` is a stale path — read it as `~/projects/forex`.**
Other older path notes may reference the old location.

**Venv rebuild (do this after any move / fresh clone):**
```
cd ~/projects/forex
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,probe,live]"   # NOT just .[dev] — probe=scikit-learn, live=ib_async
```
`.[dev]` alone gives only pytest + base (pandas/numpy/pyarrow/fredapi); the full test suite
(281) needs `probe` (sklearn, for the ML-overlay strategies) and the paper track needs `live`
(ib_async). README setup + this were fixed/pushed (commit 476593c). IBC (`~/ibc`) and git remote
are unaffected by the move.

launchd agents regenerated at the new path via `scripts/install_schedules.sh`:
`com.fx.nav-snapshot` (daily 21:00) + `com.fx.basket-rebalance` (quarterly) are ENABLED;
`com.fx.paper-rebalance` (monthly FX) is DISABLED pending [[project_fx_reconcile_settled_bug]].
