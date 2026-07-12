import random
from forex.core.space import Float, Int, Categorical

def test_ranges_respected():
    rng = random.Random(0)
    assert 0.0 <= Float(0.0, 1.0).sample(rng) <= 1.0
    assert 2 <= Int(2, 5).sample(rng) <= 5
    assert Categorical(["a", "b", "c"]).sample(rng) in ("a", "b", "c")

def test_deterministic_with_seed():
    a, b = random.Random(42), random.Random(42)
    assert Float(0, 10).sample(a) == Float(0, 10).sample(b)
    assert Int(0, 100).sample(a) == Int(0, 100).sample(b)
