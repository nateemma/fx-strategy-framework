import numpy as np, pandas as pd
import forex.cli as cli
from forex.core.dataview import DataView
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _view():
    idx = pd.date_range("2016-01-01", periods=900, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.4,900), "EUR": 1.1+np.zeros(900),
                         "SEK": 1.0+np.linspace(0,0.2,900), "NZD": 1.0+np.linspace(0,0.3,900)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.04, index=idx),
             "NZD": pd.Series(0.05, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_resolve_hyperopt_args():
    from forex.cli import build_parser, resolve
    cfg, _, mode = resolve(build_parser().parse_args(
        ["hyperopt", "--strategy", "carry", "--n-samples", "8", "--seed", "3",
         "--tune", "n_long,n_short", "--train-days", "250", "--test-days", "125"]))
    assert mode == "hyperopt" and cfg.n_samples == 8 and cfg.seed == 3
    assert cfg.tune == ["n_long", "n_short"] and cfg.train_days == 250

def test_run_hyperopt(monkeypatch):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", n_samples=6, seed=1, tune=["n_long","n_short"],
                            train_days=250, test_days=125), EnvConfig(), "hyperopt")
    r = out["hyperopt"]
    assert "best_params" in r and r["strategy"] == "carry"
    assert "sharpe" in r["oos"]

def test_main_hyperopt_prints_winning_config(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["hyperopt", "--strategy", "carry", "--n-samples", "6", "--seed", "1",
                   "--tune", "n_long,n_short", "--train-days", "250", "--test-days", "125"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "strategy = \"carry\"" in out and "[strategy_params]" in out   # winning RunConfig TOML

def test_main_hyperopt_prints_progress_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["hyperopt", "--strategy", "carry", "--n-samples", "6", "--seed", "1",
                   "--tune", "n_long,n_short", "--train-days", "250", "--test-days", "125"])
    assert rc == 0
    cap = capsys.readouterr()
    assert "new best" in cap.err                       # progress went to stderr
    assert "new best" not in cap.out                   # stdout stays clean
    assert "strategy = \"carry\"" in cap.out            # winning-config TOML still on stdout
