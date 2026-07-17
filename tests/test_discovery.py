import pytest
from forex.core.discovery import build_strategy, available, load_strategies

def test_available_lists_all_22():
    assert set(available("strategies")) == {
        "carry", "carry_voltarget", "carry_voltarget_ml", "carry_voltarget_xasset", "carry_voltarget_xasset_anchored", "carry_voltarget_xasset_gbm",
        "momentum", "momentum_voltarget",
        "value", "value_voltarget", "trend", "trend_voltarget",
        "carry_trend", "carry_trend_value", "carry_trend_voltarget", "carry_trend_value_voltarget",
        "carry_trend_crash", "carry_trend_crash_voltarget", "carry_cot", "positioning", "carry_mom", "carry_cot_mom"}

def test_build_primitive_and_composed():
    from strategies.carry import CarryStrategy
    from strategies.overlay import VolTargetOverlay
    assert isinstance(build_strategy("carry", {"n_long": 2, "n_short": 2}, "strategies"), CarryStrategy)
    s = build_strategy("carry_voltarget", {"n_long": 1, "n_short": 1, "target_vol": 0.1}, "strategies")
    assert isinstance(s, VolTargetOverlay) and s.base.n_long == 1 and s.target_vol == 0.1

def test_composed_default_and_override():
    s = build_strategy("carry_trend", {"trend_lookback": 50}, "strategies")
    assert s.components["trend"].lookback == 50 and s.components["trend"].signal_type == "ema"
    assert s.components["carry"].n_long == 3

def test_unknown_raises():
    with pytest.raises(KeyError):
        build_strategy("nope", package="strategies")

_ALL = ["carry", "carry_voltarget", "carry_voltarget_ml", "carry_voltarget_xasset", "carry_voltarget_xasset_anchored", "carry_voltarget_xasset_gbm",
        "momentum", "momentum_voltarget",
        "value", "value_voltarget", "trend", "trend_voltarget",
        "carry_trend", "carry_trend_value", "carry_trend_voltarget", "carry_trend_value_voltarget",
        "carry_trend_crash", "carry_trend_crash_voltarget", "carry_cot", "positioning", "carry_mom", "carry_cot_mom"]

@pytest.mark.parametrize("name", _ALL)
def test_every_name_builds_with_defaults(name):
    from forex.core.strategy import Strategy
    s = build_strategy(name, {}, "strategies")     # empty params -> defaults
    assert isinstance(s, Strategy)
    s.params(); s.search_space()                          # do not raise

def test_voltarget_variants_route_params():
    m = build_strategy("momentum_voltarget", {"lookback": 30, "target_vol": 0.09}, "strategies")
    assert m.base.lookback == 30 and m.target_vol == 0.09
    v = build_strategy("value_voltarget", {"window": 48, "target_vol": 0.09}, "strategies")
    assert v.base.window == 48 and v.target_vol == 0.09
    t = build_strategy("trend_voltarget", {"signal_type": "donchian", "cap": 1.8}, "strategies")
    assert t.base.signal_type == "donchian" and t.cap == 1.8

def test_three_way_blend_routes_prefixed_params():
    s = build_strategy("carry_trend_value", {}, "strategies")
    assert set(s.components) == {"carry", "trend", "value"} and s.components["value"].window == 42
    sv = build_strategy("carry_trend_value_voltarget", {"value_window": 50, "target_vol": 0.09}, "strategies")
    assert sv.base.components["value"].window == 50 and sv.target_vol == 0.09

def test_trend_voltarget_routes_band():
    s = build_strategy("trend_voltarget", {"band": 0.05, "target_vol": 0.1}, "strategies")
    assert s.base.band == 0.05 and s.target_vol == 0.1      # band -> base, not overlay

def test_duplicate_name_raises(tmp_path, monkeypatch):
    from forex.core import discovery
    pkg = tmp_path / "dup_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    body = ("from forex.core.strategy import Strategy\n"
            "class {cls}(Strategy):\n"
            "    NAME = 'dup'\n"
            "    def target_weights(self, view):\n"
            "        return None\n")
    (pkg / "a.py").write_text(body.format(cls="A"))
    (pkg / "b.py").write_text(body.format(cls="B"))
    monkeypatch.syspath_prepend(str(tmp_path))
    discovery._CACHE.pop("dup_pkg", None)            # ensure a fresh scan
    with pytest.raises(ValueError):
        discovery.load_strategies("dup_pkg")


def test_carry_voltarget_xasset_uses_macro():
    from strategies.mloverlay import MLVolTargetOverlay
    from strategies.carry import CarryStrategy
    s = build_strategy("carry_voltarget_xasset", {"n_long": 1, "n_short": 1, "target_vol": 0.1}, "strategies")
    assert isinstance(s, MLVolTargetOverlay) and s.use_macro is True
    assert isinstance(s.base, CarryStrategy) and s.base.n_long == 1 and s.target_vol == 0.1

def test_carry_trend_voltarget_tuned_defaults():
    s = build_strategy("carry_trend_voltarget", package="strategies")
    assert abs(s.target_vol - 0.062) < 1e-9 and abs(s.cap - 1.20) < 1e-9   # validated bests
    s2 = build_strategy("carry_trend_voltarget", {"target_vol": 0.1}, "strategies")
    assert s2.target_vol == 0.1 and abs(s2.cap - 1.20) < 1e-9              # override target_vol, keep cap default
