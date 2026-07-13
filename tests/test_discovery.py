import pytest
from forex.core.discovery import build_strategy, available, load_strategies

def test_available_lists_all_13():
    assert set(available("forex.strategies")) == {
        "carry", "carry_voltarget", "carry_voltarget_ml", "momentum", "momentum_voltarget",
        "value", "value_voltarget", "trend", "trend_voltarget",
        "carry_trend", "carry_trend_value", "carry_trend_voltarget", "carry_trend_value_voltarget"}

def test_build_primitive_and_composed():
    from forex.strategies.carry import CarryStrategy
    from forex.strategies.overlay import VolTargetOverlay
    assert isinstance(build_strategy("carry", {"n_long": 2, "n_short": 2}, "forex.strategies"), CarryStrategy)
    s = build_strategy("carry_voltarget", {"n_long": 1, "n_short": 1, "target_vol": 0.1}, "forex.strategies")
    assert isinstance(s, VolTargetOverlay) and s.base.n_long == 1 and s.target_vol == 0.1

def test_composed_default_and_override():
    s = build_strategy("carry_trend", {"trend_lookback": 50}, "forex.strategies")
    assert s.components["trend"].lookback == 50 and s.components["trend"].signal_type == "ema"
    assert s.components["carry"].n_long == 3

def test_unknown_raises():
    with pytest.raises(KeyError):
        build_strategy("nope", package="forex.strategies")

_ALL = ["carry", "carry_voltarget", "carry_voltarget_ml", "momentum", "momentum_voltarget",
        "value", "value_voltarget", "trend", "trend_voltarget",
        "carry_trend", "carry_trend_value", "carry_trend_voltarget", "carry_trend_value_voltarget"]

@pytest.mark.parametrize("name", _ALL)
def test_every_name_builds_with_defaults(name):
    from forex.core.strategy import Strategy
    s = build_strategy(name, {}, "forex.strategies")     # empty params -> defaults
    assert isinstance(s, Strategy)
    s.params(); s.search_space()                          # do not raise

def test_voltarget_variants_route_params():
    m = build_strategy("momentum_voltarget", {"lookback": 30, "target_vol": 0.09}, "forex.strategies")
    assert m.base.lookback == 30 and m.target_vol == 0.09
    v = build_strategy("value_voltarget", {"window": 48, "target_vol": 0.09}, "forex.strategies")
    assert v.base.window == 48 and v.target_vol == 0.09
    t = build_strategy("trend_voltarget", {"signal_type": "donchian", "cap": 1.8}, "forex.strategies")
    assert t.base.signal_type == "donchian" and t.cap == 1.8

def test_three_way_blend_routes_prefixed_params():
    s = build_strategy("carry_trend_value", {}, "forex.strategies")
    assert set(s.components) == {"carry", "trend", "value"} and s.components["value"].window == 42
    sv = build_strategy("carry_trend_value_voltarget", {"value_window": 50, "target_vol": 0.09}, "forex.strategies")
    assert sv.base.components["value"].window == 50 and sv.target_vol == 0.09
