from forex.strategies.carry import CarryStrategy
from forex.strategies.momentum import MomentumStrategy
from forex.strategies.overlay import VolTargetOverlay

_BASE_KEYS = ("n_long", "n_short")
_MOM_KEYS = ("lookback", "n_long", "n_short")

def _carry(p: dict):
    return CarryStrategy(**p)

def _carry_voltarget(p: dict):
    base = CarryStrategy(**{k: p[k] for k in _BASE_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _BASE_KEYS}
    return VolTargetOverlay(base, **overlay)

def _momentum(p: dict):
    return MomentumStrategy(**p)

def _momentum_voltarget(p: dict):
    base = MomentumStrategy(**{k: p[k] for k in _MOM_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _MOM_KEYS}
    return VolTargetOverlay(base, **overlay)

_BUILDERS = {
    "carry": _carry,
    "carry_voltarget": _carry_voltarget,
    "momentum": _momentum,
    "momentum_voltarget": _momentum_voltarget,
}

def build_strategy(name: str, params: dict | None = None):
    if name not in _BUILDERS:
        raise KeyError(f"unknown strategy '{name}'; available: {sorted(_BUILDERS)}")
    return _BUILDERS[name](params or {})

def available() -> list:
    return sorted(_BUILDERS)
