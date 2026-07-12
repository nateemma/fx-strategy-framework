import pytest
from forex.strategies.registry import build_strategy, available
from forex.strategies.carry import CarryStrategy
from forex.strategies.momentum import MomentumStrategy
from forex.strategies.overlay import VolTargetOverlay

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

def test_unknown_raises_and_available_lists():
    with pytest.raises(KeyError):
        build_strategy("nope")
    assert set(available()) == {"carry", "carry_voltarget", "momentum", "momentum_voltarget"}
