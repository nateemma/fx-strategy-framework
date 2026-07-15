import numpy as np, pandas as pd
import forex.cli as cli
from forex.cli import build_parser, resolve
from forex.core.dataview import DataView
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _view():
    idx = pd.date_range("2018-01-01", periods=300, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.2,300), "EUR": 1.1+np.zeros(300)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_env_starting_equity_default_and_override():
    assert EnvConfig.load(environ={}).starting_equity == 10000.0
    assert EnvConfig.load(environ={"FOREX_STARTING_EQUITY": "5000"}).starting_equity == 5000.0

def test_resolve_dryrun_flags():
    cfg, env, mode = resolve(build_parser().parse_args(
        ["dryrun", "--strategy", "carry", "--preview", "--equity", "5000"]))
    assert mode == "dryrun" and cfg.preview is True and env.starting_equity == 5000.0

def test_run_dryrun_preview(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long": 1, "n_short": 1}, preview=True),
                  EnvConfig(output_dir=str(tmp_path)), "dryrun")
    rep = out["dryrun"]
    assert rep.applied is False and set(rep.positions) == {"AUD", "EUR"}
    assert not (tmp_path / "portfolio.json").exists()      # preview wrote nothing

def test_main_dryrun_prints(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["dryrun", "--strategy", "carry", "--param", "n_long=1", "--param", "n_short=1", "--preview"])
    assert rc == 0 and "rebalance" in capsys.readouterr().out

def test_run_dryrun_broker_ib_constructs_live_execution(monkeypatch):
    import forex.run.execution as exmod
    from forex.run.execution import RebalanceReport
    captured = {}
    class _Fake:
        def __init__(self, **kw): captured.update(kw)
        def rebalance(self, tw, px):
            return RebalanceReport(orders={"USDMXN": -333.0}, positions={"USDMXN": -333.0},
                                   equity=1_000_000.0, turnover=0.5, cost=50.0, applied=False)
    monkeypatch.setattr(exmod, "LiveExecution", _Fake)
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long": 1, "n_short": 1},
                            broker="ib", ib_port=4002, preview=True), EnvConfig(), "dryrun")
    assert captured["port"] == 4002 and captured["preview"] is True      # LiveExecution built with ib params
    assert out["broker"] == "ib" and out["dryrun"].applied is False

def test_format_ib_dryrun_table():
    from forex.run.execution import RebalanceReport
    out = {"broker": "ib", "dryrun": RebalanceReport(
        orders={"USDMXN": -333333.0, "EURUSD": 100000.0}, positions={},
        equity=1_000_000.0, turnover=2.0, cost=200.0, applied=False)}
    s = cli._format(out)
    assert "PREVIEW" in s and "IBKR" in s
    assert "USDMXN" in s and "SELL" in s and "EURUSD" in s and "BUY" in s

def test_dryrun_ib_confirm_threads_placement_params(monkeypatch):
    import forex.run.execution as exmod
    captured = {}
    class _Fake:
        def __init__(self, **kw): captured.update(kw)
        def rebalance(self, tw, px):
            from forex.run.execution import RebalanceReport
            return RebalanceReport(orders={"USDMXN": -20000.0}, positions={}, equity=1e6,
                                   turnover=0.6, cost=60.0, applied=True)
    monkeypatch.setattr(exmod, "LiveExecution", _Fake)
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long": 1, "n_short": 1},
                            broker="ib", ib_port=4002, confirm=True, max_order_frac=0.4), EnvConfig(), "dryrun")
    assert captured["confirm"] is True and captured["max_order_frac"] == 0.4
    assert out["dryrun"].applied is True

def test_format_ib_fills_table():
    from forex.run.execution import RebalanceReport
    s = cli._format({"broker": "ib", "dryrun": RebalanceReport(
        orders={"USDMXN": -20000.0}, positions={}, equity=1e6, turnover=0.6, cost=60.0, applied=True)})
    assert "PLACED" in s and "USDMXN" in s and "SELL" in s

def test_format_ib_incomplete_flagged():
    from forex.run.execution import RebalanceReport
    s = cli._format({"broker": "ib", "dryrun": RebalanceReport(
        orders={"USDMXN": -20000.0}, positions={}, equity=1e6, turnover=0.6, cost=60.0,
        applied=True, complete=False)})
    assert "INCOMPLETE" in s
