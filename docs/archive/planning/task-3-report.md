# Task 3 Report: Basket-Sleeve Runner + Tracking + Docs

**STATUS**: Complete (+ fixes applied)

**Commits**: f6fa022 (initial), 5704145 (fixes)

**Tests**: 4 new (test_basket_track.py) + 271 total passing; all green

**Summary**:
- `forex/run/basket_track.py`: log_basket_positions() with CSV header+append, missing-weight handling, parent-dir creation
- `scripts/basket_rebalance.py`: argparse CLI (preview default, --confirm arms placement only)
- `scripts/basket_rebalance.sh`: forwards IB_PORT env var to Python CLI
- `docs/basket-sleeve.md`: updated to show preview as default, --confirm for placement

**Fixes Applied**:
1. Shell script now forwards IB_PORT to Python (`--port "${IB_PORT:-4002}"`)
2. Removed no-op --preview flag; preview is safe default
3. Updated docs to reflect default behavior

**Concerns**: None. All tests pass; safe defaults enforced; spec compliant.
