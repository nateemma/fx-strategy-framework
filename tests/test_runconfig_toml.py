import tomllib
from forex.core.config import RunConfig

def test_hyperopt_fields_default():
    c = RunConfig()
    assert c.n_samples == 200 and c.seed == 0 and c.objective == "sharpe" and c.tune is None

def test_to_toml_str_roundtrips():
    c = RunConfig(strategy="carry_voltarget", cost_bps=2.0,
                  strategy_params={"n_long": 3, "target_vol": 0.083}, universe=["AUD", "EUR"])
    parsed = tomllib.loads(c.to_toml_str())
    assert parsed["strategy"] == "carry_voltarget"
    assert parsed["cost_bps"] == 2.0
    assert parsed["universe"] == ["AUD", "EUR"]
    assert parsed["strategy_params"] == {"n_long": 3, "target_vol": 0.083}
