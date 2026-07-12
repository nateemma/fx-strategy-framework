import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.run.hyperopt import optimize

def _view():
    idx = pd.date_range("2016-01-01", periods=900, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.4,900), "EUR": 1.1+np.zeros(900),
                         "SEK": 1.0+np.linspace(0,0.2,900), "NZD": 1.0+np.linspace(0,0.3,900)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.04, index=idx),
             "NZD": pd.Series(0.05, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_optimize_returns_best_and_gap():
    r = optimize("carry", _view(), train_days=250, test_days=125,
                 n_samples=8, seed=1, tune=["n_long", "n_short"])
    assert 2 <= r["best_params"]["n_long"] <= 4          # sampled within the Int space
    assert r["objective"] == "sharpe"
    assert "sharpe" in r["oos"] and "sharpe" in r["in_sample"]
    assert r["n_samples"] == 8

def test_optimize_is_deterministic():
    v = _view()
    a = optimize("carry", v, train_days=250, test_days=125, n_samples=6, seed=7, tune=["n_long","n_short"])
    b = optimize("carry", v, train_days=250, test_days=125, n_samples=6, seed=7, tune=["n_long","n_short"])
    assert a["best_params"] == b["best_params"] and a["score"] == b["score"]
