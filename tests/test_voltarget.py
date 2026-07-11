import pandas as pd
from forex.backtest.voltarget import vol_target
from forex.features.volforecast import ewma_vol
from forex.backtest.portfolio import metrics

def test_cap_and_no_lookahead():
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    carry = pd.Series([0.0, 0.02, 0.0], index=idx)
    vf = pd.Series([0.05, 0.05, 0.05], index=idx)  # target/vf = 0.10/0.05 = 2.0 -> capped to 1.5
    out = vol_target(carry, vf, target_vol=0.10, cap=1.5, cadence="D", cost_bps=0.0)
    # day2 return = day1 scale (1.5, from day0->carry not used until shifted) * 0.02 = 0.03
    assert round(out.iloc[1], 4) == 0.03   # cap enforced (1.5 not 2.0) AND lagged scale

def test_first_period_leverage_cost_charged():
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    carry = pd.Series([0.0, 0.0], index=idx)
    vf = pd.Series([0.10, 0.10], index=idx)  # scale = 1.0
    out = vol_target(carry, vf, target_vol=0.10, cap=1.5, cadence="D", cost_bps=10.0)
    # day0: leverage 0->1.0, turnover 1.0, cost = 10/1e4 * 1.0 = 0.001; no P&L -> -0.001
    assert round(out.iloc[0], 6) == -0.001

def test_overlay_reduces_realized_vol_when_base_is_wild():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    base = pd.Series([0.02, -0.02] * 150, index=idx)   # ~31% annualized vol
    vf = ewma_vol(base)
    out = vol_target(base, vf, target_vol=0.10, cap=1.5, cadence="D", cost_bps=0.0)
    assert metrics(out)["ann_vol"] < metrics(base)["ann_vol"]   # de-risked toward target

def test_monthly_cadence_steps_and_holds_no_lookahead():
    # Jan vol 0.10 (scale target/vf = 1.0); Feb vol 0.05 (scale 2.0 -> capped 1.5).
    idx = pd.date_range("2020-01-01", "2020-02-28", freq="B")
    carry = pd.Series(0.01, index=idx)
    vf = pd.Series(0.10, index=idx)
    vf.loc["2020-02-03":] = 0.05
    out = vol_target(carry, vf, target_vol=0.10, cap=1.5, cadence="MS", cost_bps=0.0)
    # mid-Jan: leverage 1.0 -> 0.01
    assert round(out.loc["2020-01-15"], 4) == 0.01
    # last Jan day is NOT levered up by February's lower vol (no lookahead into next month)
    assert round(out.loc["2020-01-31"], 4) == 0.01
    # mid-Feb: leverage held at the capped 1.5 for the whole month -> 0.015
    assert round(out.loc["2020-02-14"], 4) == 0.015
