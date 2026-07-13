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
