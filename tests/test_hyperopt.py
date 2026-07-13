import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.discovery import build_strategy
from forex.run.hyperopt import optimize

def _view():
    idx = pd.date_range("2016-01-01", periods=900, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.4,900), "EUR": 1.1+np.zeros(900),
                         "SEK": 1.0+np.linspace(0,0.2,900), "NZD": 1.0+np.linspace(0,0.3,900)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.04, index=idx),
             "NZD": pd.Series(0.05, index=idx)}
    return DataView(spot=spot, rates=rates)

build = lambda p: build_strategy("carry", p, "forex.strategies")

def test_optimize_returns_best_and_gap():
    r = optimize(build, _view(), train_days=250, test_days=125,
                 n_samples=8, seed=1, tune=["n_long", "n_short"])
    assert 2 <= r["best_params"]["n_long"] <= 4          # sampled within the Int space
    assert r["objective"] == "sharpe"
    assert "sharpe" in r["oos"] and "sharpe" in r["in_sample"]
    assert r["n_samples"] == 8

def test_optimize_is_deterministic():
    v = _view()
    a = optimize(build, v, train_days=250, test_days=125, n_samples=6, seed=7, tune=["n_long","n_short"])
    b = optimize(build, v, train_days=250, test_days=125, n_samples=6, seed=7, tune=["n_long","n_short"])
    assert a["best_params"] == b["best_params"] and a["score"] == b["score"]

def test_on_step_fires_once_per_sample_with_correct_flags():
    calls = []
    r = optimize(build, _view(), train_days=250, test_days=125,
                 n_samples=8, seed=1, tune=["n_long", "n_short"],
                 on_step=lambda i, n, score, params, improved: calls.append(
                     (i, n, score, dict(params), improved)))
    # one call per sample, i is 1..n in order, n constant
    assert len(calls) == 8
    assert [c[0] for c in calls] == list(range(1, 9))
    assert all(c[1] == 8 for c in calls)
    # first sample is always a new best
    assert calls[0][4] is True
    # `improved` marks exactly the running-maximum samples
    running = float("-inf")
    for _i, _n, score, _params, improved in calls:
        assert improved == (score > running)
        if improved:
            running = score
    # the reported best equals the max improved score
    assert r["score"] == running

def test_on_step_none_is_backward_compatible():
    v = _view()
    a = optimize(build, v, train_days=250, test_days=125, n_samples=6, seed=7,
                 tune=["n_long", "n_short"])
    b = optimize(build, v, train_days=250, test_days=125, n_samples=6, seed=7,
                 tune=["n_long", "n_short"], on_step=None)
    assert a["best_params"] == b["best_params"] and a["score"] == b["score"]
