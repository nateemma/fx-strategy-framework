from strategies.carry import CarryStrategy
from strategies.overlay import VolTargetOverlay
from forex.core.space import Int, Float

def test_carry_search_space():
    s = CarryStrategy().search_space()
    assert set(s) == {"n_long", "n_short"} and isinstance(s["n_long"], Int)

def test_overlay_merges_base_space():
    s = VolTargetOverlay(CarryStrategy()).search_space()
    assert set(s) == {"n_long", "n_short", "target_vol", "cap"}   # base keys + overlay knobs
    assert isinstance(s["target_vol"], Float) and isinstance(s["n_long"], Int)
