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
