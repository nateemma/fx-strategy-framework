from forex.core.config import RunConfig

def test_defaults_and_from_dict():
    c = RunConfig.from_dict({"strategy": "carry_voltarget", "cost_bps": 2.0, "junk": 1})
    assert c.strategy == "carry_voltarget" and c.cost_bps == 2.0
    assert not hasattr(c, "junk")                 # unknown keys ignored

def test_merge_overrides_and_params_merge():
    base = RunConfig(strategy_params={"n_long": 3, "n_short": 3})
    m = base.merge({"cost_bps": 5.0, "strategy_params": {"n_long": 1}, "strategy": None})
    assert m.cost_bps == 5.0
    assert m.strategy_params == {"n_long": 1, "n_short": 3}   # key-wise merge
    assert m.strategy == "carry"                              # None override ignored

def test_from_toml(tmp_path):
    p = tmp_path / "run.toml"
    p.write_text('strategy = "carry"\ncost_bps = 3.0\n[strategy_params]\nn_long = 2\n')
    c = RunConfig.from_toml(p)
    assert c.strategy == "carry" and c.cost_bps == 3.0 and c.strategy_params == {"n_long": 2}
