import numpy as np, pandas as pd
from forex.backtest.portfolio import simulate, metrics, attribution

def test_simulate_applies_lagged_weights_and_carry():
    idx = pd.to_datetime(["2020-01-01","2020-01-02","2020-01-03"])
    weights = pd.DataFrame({"A":[1.0,1.0,1.0]}, index=idx)
    spot = pd.DataFrame({"A":[0.0, 0.10, 0.0]}, index=idx)  # +10% on day 2
    carry = pd.DataFrame({"A":[0.0, 0.0, 0.0]}, index=idx)
    ret = simulate(weights, spot, carry, cost_bps=0.0)
    # day 1: no prior weight -> 0 ; day 2: weight from day1 (1.0) * 10% = 0.10
    assert round(ret.loc["2020-01-02"], 4) == 0.10

def test_carry_accrues_daily():
    idx = pd.to_datetime(["2020-01-01","2020-01-02"])
    weights = pd.DataFrame({"A":[1.0,1.0]}, index=idx)
    spot = pd.DataFrame({"A":[0.0,0.0]}, index=idx)
    carry = pd.DataFrame({"A":[0.0, 2.52]}, index=idx)   # 252% annual -> 1%/day
    ret = simulate(weights, spot, carry, cost_bps=0.0)
    assert round(ret.loc["2020-01-02"], 4) == 0.01

def test_first_day_entry_cost_is_charged():
    idx = pd.to_datetime(["2020-01-01", "2020-01-02"])
    weights = pd.DataFrame({"A": [1.0, 1.0]}, index=idx)
    spot = pd.DataFrame({"A": [0.0, 0.0]}, index=idx)
    carry = pd.DataFrame({"A": [0.0, 0.0]}, index=idx)
    ret = simulate(weights, spot, carry, cost_bps=10.0)
    # day 0: enter weight 1.0 => turnover 1.0 => cost = 10/1e4 * 1.0 = 0.001; no P&L yet
    assert round(ret.loc["2020-01-01"], 6) == -0.001

def test_metrics_shape():
    r = pd.Series([0.01,-0.02,0.03,0.00],
                  index=pd.to_datetime(["2020-01-01","2020-01-02","2020-01-03","2020-01-04"]))
    m = metrics(r)
    assert {"total_return","ann_return","ann_vol","sharpe","max_drawdown","calmar"} <= set(m)
    assert m["max_drawdown"] <= 0

def test_attribution_splits_spot_and_carry_per_currency():
    idx = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    weights = pd.DataFrame({"A": [1.0, 1.0, 1.0], "B": [-1.0, -1.0, -1.0]}, index=idx)
    spot = pd.DataFrame({"A": [0.0, 0.10, 0.0], "B": [0.0, 0.0, 0.0]}, index=idx)
    carry = pd.DataFrame({"A": [0.0, 0.0, 0.0], "B": [0.0, 2.52, 0.0]}, index=idx)  # B: 1%/day
    att = attribution(weights, spot, carry)
    assert round(att.loc["A", "spot"], 4) == 0.10   # A held from day1 earns +10% spot day2
    assert round(att.loc["A", "carry"], 4) == 0.00
    assert round(att.loc["B", "carry"], 4) == -0.01  # short B, +1%/day carry -> -0.01
    assert round(att.loc["B", "total"], 4) == -0.01

def test_sortino_present_and_downside_only():
    idx = pd.date_range("2020-01-01", periods=6, freq="B")
    r = pd.Series([0.01, -0.02, 0.01, -0.01, 0.02, 0.01], index=idx)
    m = metrics(r)
    assert "sortino" in m and np.isfinite(m["sortino"])
    # hand-computed downside deviation (MAR=0), annualized
    downside = r.clip(upper=0.0)
    dd = (downside.pow(2).mean() ** 0.5) * np.sqrt(252)
    assert abs(m["sortino"] - m["ann_return"] / dd) < 1e-9
    # right-skewed (mostly-up) series -> downside dev < total std -> sortino > sharpe
    assert m["sortino"] > m["sharpe"]

def test_sortino_zero_when_no_downside():
    idx = pd.date_range("2020-01-01", periods=4, freq="B")
    m = metrics(pd.Series([0.01, 0.02, 0.0, 0.01], index=idx))
    assert m["sortino"] == 0.0        # no negative returns -> dd == 0 -> guarded to 0.0
