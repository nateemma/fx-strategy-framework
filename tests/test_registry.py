import pytest
from forex.strategies.registry import build_strategy, available
from forex.strategies.carry import CarryStrategy
from forex.strategies.momentum import MomentumStrategy
from forex.strategies.mloverlay import MLVolTargetOverlay
from forex.strategies.overlay import VolTargetOverlay
from forex.strategies.trend import TrendStrategy
from forex.strategies.value import ValueStrategy

def test_build_carry():
    s = build_strategy("carry", {"n_long": 2, "n_short": 2})
    assert isinstance(s, CarryStrategy) and s.n_long == 2

def test_build_composed_splits_params():
    s = build_strategy("carry_voltarget", {"n_long": 1, "n_short": 1, "target_vol": 0.08, "cap": 2.0})
    assert isinstance(s, VolTargetOverlay)
    assert isinstance(s.base, CarryStrategy) and s.base.n_long == 1
    assert s.target_vol == 0.08 and s.cap == 2.0

def test_build_momentum():
    s = build_strategy("momentum", {"lookback": 30, "n_long": 2, "n_short": 2})
    assert isinstance(s, MomentumStrategy) and s.lookback == 30 and s.n_long == 2

def test_build_momentum_voltarget_splits_params():
    s = build_strategy("momentum_voltarget",
                       {"lookback": 30, "n_long": 1, "n_short": 1, "target_vol": 0.08, "cap": 2.0})
    assert isinstance(s, VolTargetOverlay)
    assert isinstance(s.base, MomentumStrategy) and s.base.lookback == 30 and s.base.n_long == 1
    assert s.target_vol == 0.08 and s.cap == 2.0

def test_build_value():
    s = build_strategy("value", {"window": 48, "n_long": 2, "n_short": 2})
    assert isinstance(s, ValueStrategy) and s.window == 48 and s.n_long == 2

def test_build_value_voltarget_splits_params():
    s = build_strategy("value_voltarget",
                       {"window": 48, "n_long": 1, "n_short": 1, "target_vol": 0.08, "cap": 2.0})
    assert isinstance(s, VolTargetOverlay)
    assert isinstance(s.base, ValueStrategy) and s.base.window == 48 and s.base.n_long == 1
    assert s.target_vol == 0.08 and s.cap == 2.0

def test_build_carry_voltarget_ml_splits_params():
    s = build_strategy("carry_voltarget_ml",
                       {"n_long": 1, "n_short": 1, "target_vol": 0.10, "cap": 1.5, "horizon": 21})
    assert isinstance(s, MLVolTargetOverlay)
    assert isinstance(s.base, CarryStrategy) and s.base.n_long == 1
    assert s.target_vol == 0.10 and s.horizon == 21

def test_build_trend():
    s = build_strategy("trend", {"signal_type": "ema", "lookback": 60})
    assert isinstance(s, TrendStrategy) and s.signal_type == "ema" and s.lookback == 60

def test_build_trend_voltarget_splits_params():
    s = build_strategy("trend_voltarget",
                       {"signal_type": "donchian", "lookback": 60, "target_vol": 0.10, "cap": 1.5})
    assert isinstance(s, VolTargetOverlay)
    assert isinstance(s.base, TrendStrategy) and s.base.signal_type == "donchian"
    assert s.target_vol == 0.10 and s.cap == 1.5

def test_unknown_raises_and_available_lists():
    with pytest.raises(KeyError):
        build_strategy("nope")
    assert set(available()) == {"carry", "carry_voltarget", "carry_voltarget_ml",
                                "momentum", "momentum_voltarget", "value", "value_voltarget",
                                "trend", "trend_voltarget"}
