import numpy as np, pandas as pd
import forex.cli as cli
from forex.core.dataview import DataView
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_run_backtest(monkeypatch):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long":1,"n_short":1}),
                  EnvConfig(), "backtest")
    assert "sharpe" in out["metrics"]

def test_run_causal_check(monkeypatch):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long":1,"n_short":1}),
                  EnvConfig(), "causal-check")
    assert out["causal"] == "PASS"

def test_main_end_to_end(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["backtest", "--strategy", "carry", "--param", "n_long=1", "--param", "n_short=1"])
    assert rc == 0
    assert "sharpe" in capsys.readouterr().out
