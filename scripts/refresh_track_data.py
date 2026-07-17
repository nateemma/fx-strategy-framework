"""Refresh the three data sources carry_cot_mom depends on, before a forward-track rebalance:
  - IBKR daily spot (data_cache/ibkr_daily) via Gateway  [needs IB Gateway on IB_PORT]
  - FRED 3-month rates (IR3TIB01)                          [needs FRED_API_KEY]
  - CFTC COT net-spec positioning (data_cache/cot_*)       [free, no key]
Each source is refreshed independently; a failure in one is logged, not fatal, so the rebalance can
still run on the last-good cache for that source (and the log shows what was stale)."""
import os
from forex.config import TRADEABLE_CARRY, CURRENCIES
from forex.data.ibkr import fetch_daily
from forex.data.fred import load_series
from forex.data.cftc import load_cot, COT_CODES

port = int(os.environ.get("IB_PORT", "4002"))

def step(name, fn):
    try:
        fn()
        print(f"refresh OK: {name}", flush=True)
    except Exception as e:
        print(f"refresh FAILED: {name} -> {type(e).__name__}: {e} (using last-good cache)", flush=True)

step("IBKR daily spot", lambda: fetch_daily(TRADEABLE_CARRY, port=port, client_id=95))
step("FRED rates", lambda: [load_series(CURRENCIES[c].rate_fred, cache_dir="data_cache", force=True)
                            for c in ["USD"] + list(TRADEABLE_CARRY)])
step("CFTC COT", lambda: [load_cot(COT_CODES[c], cache_dir="data_cache", force=True)
                          for c in TRADEABLE_CARRY if c in COT_CODES])
print("refresh done", flush=True)
