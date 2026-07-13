from forex.core.compose import split_params, split_prefixed, build_components

def test_split_params():
    base, rest = split_params({"n_long": 3, "n_short": 3, "target_vol": 0.1}, ("n_long", "n_short"))
    assert base == {"n_long": 3, "n_short": 3} and rest == {"target_vol": 0.1}

def test_split_prefixed():
    inside, outside = split_prefixed({"carry_n_long": 3, "trend_lookback": 50, "target_vol": 0.1},
                                     ("carry", "trend"))
    assert inside == {"carry_n_long": 3, "trend_lookback": 50} and outside == {"target_vol": 0.1}

def test_build_components_applies_defaults_then_overrides():
    class Dummy:
        def __init__(self, a=1, b=2): self.a, self.b = a, b
    comps = build_components([("x", Dummy, {"a": 9})], {"x_b": 7, "ignore": 1})
    assert comps["x"].a == 9 and comps["x"].b == 7      # default a=9 kept, b overridden to 7

def test_strategy_defaults():
    from forex.core.strategy import Strategy
    assert Strategy.NAME is None and hasattr(Strategy, "build")
