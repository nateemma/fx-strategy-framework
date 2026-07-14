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


def test_build_view_timerange_preserves_reer_and_macro(monkeypatch):
    import pandas as pd
    import forex.cli as cli
    from forex.core.dataview import DataView
    from forex.core.config import RunConfig
    from forex.core.env import EnvConfig
    idx = pd.date_range("2015-01-01", periods=100, freq="D")
    full = DataView(spot=pd.DataFrame({"AUD": range(100)}, index=idx).astype(float),
                    rates={"USD": pd.Series(0.01, index=idx)},
                    reer={"AUD": pd.Series(100.0, index=idx)},
                    macro={"vix": pd.Series(20.0, index=idx)})
    monkeypatch.setattr(DataView, "from_fred", classmethod(lambda cls, *a, **k: full))
    v = cli._build_view(RunConfig(timerange=["2015-02-01", "2015-03-01"]), EnvConfig())
    assert v.reer and v.macro                                   # not dropped by timerange
    assert v.reer["AUD"].index.min() >= pd.Timestamp("2015-02-01")
    assert v.macro["vix"].index.max() <= pd.Timestamp("2015-03-01")
