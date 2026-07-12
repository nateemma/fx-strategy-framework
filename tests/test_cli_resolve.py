from forex.cli import build_parser, resolve

def _resolve(argv):
    return resolve(build_parser().parse_args(argv))

def test_flags_override_into_runconfig():
    cfg, env, mode = _resolve(["backtest", "--strategy", "carry_voltarget",
                               "--param", "n_long=2", "--param", "target_vol=0.08",
                               "--cost-bps", "2.0", "--universe", "AUD,EUR", "--cache-dir", "/tmp/c"])
    assert mode == "backtest"
    assert cfg.strategy == "carry_voltarget"
    assert cfg.strategy_params == {"n_long": 2, "target_vol": 0.08}   # int + float coerced
    assert cfg.cost_bps == 2.0 and cfg.universe == ["AUD", "EUR"]
    assert env.data_cache_dir == "/tmp/c"

def test_timerange_split():
    cfg, _, _ = _resolve(["walkforward", "--timerange", "2000-01-01:2020-12-31"])
    assert cfg.timerange == ["2000-01-01", "2020-12-31"]

def test_config_file_then_flag(tmp_path):
    p = tmp_path / "r.toml"
    p.write_text('strategy = "carry"\ncost_bps = 9.0\n')
    cfg, _, _ = _resolve(["backtest", "--config", str(p), "--cost-bps", "1.0"])
    assert cfg.strategy == "carry"    # from file
    assert cfg.cost_bps == 1.0        # flag beats file
