from forex.strategies.blend import BlendStrategy
from forex.strategies.carry import CarryStrategy
from forex.strategies.mloverlay import MLVolTargetOverlay
from forex.strategies.momentum import MomentumStrategy
from forex.strategies.overlay import VolTargetOverlay
from forex.strategies.trend import TrendStrategy
from forex.strategies.value import ValueStrategy

_BASE_KEYS = ("n_long", "n_short")
_MOM_KEYS = ("lookback", "n_long", "n_short")

def _carry(p: dict):
    return CarryStrategy(**p)

def _carry_voltarget(p: dict):
    base = CarryStrategy(**{k: p[k] for k in _BASE_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _BASE_KEYS}
    return VolTargetOverlay(base, **overlay)

def _carry_voltarget_ml(p: dict):
    base = CarryStrategy(**{k: p[k] for k in _BASE_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _BASE_KEYS}
    return MLVolTargetOverlay(base, **overlay)

def _momentum(p: dict):
    return MomentumStrategy(**p)

def _momentum_voltarget(p: dict):
    base = MomentumStrategy(**{k: p[k] for k in _MOM_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _MOM_KEYS}
    return VolTargetOverlay(base, **overlay)

_TREND_KEYS = ("signal_type", "lookback")

def _trend(p: dict):
    return TrendStrategy(**p)

def _trend_voltarget(p: dict):
    base = TrendStrategy(**{k: p[k] for k in _TREND_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _TREND_KEYS}
    return VolTargetOverlay(base, **overlay)

_VAL_KEYS = ("window", "n_long", "n_short")

def _value(p: dict):
    return ValueStrategy(**p)

def _value_voltarget(p: dict):
    base = ValueStrategy(**{k: p[k] for k in _VAL_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _VAL_KEYS}
    return VolTargetOverlay(base, **overlay)

_BLEND_SPECS = {
    "carry_trend": [
        ("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
        ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108}),
    ],
    "carry_trend_value": [
        ("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
        ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108}),
        ("value", ValueStrategy, {"window": 42, "n_long": 4, "n_short": 4}),
    ],
}

def _build_components(specs: list, p: dict) -> dict:
    comps = {}
    for prefix, cls, defaults in specs:
        sub_p = dict(defaults)
        for k, v in p.items():
            if k.startswith(prefix + "_"):
                sub_p[k[len(prefix) + 1:]] = v
        comps[prefix] = cls(**sub_p)
    return comps

def _blend(name: str):
    specs = _BLEND_SPECS[name]
    return lambda p: BlendStrategy(_build_components(specs, p))

def _blend_voltarget(name: str):
    specs = _BLEND_SPECS[name]
    prefixes = tuple(pre for pre, _, _ in specs)
    def build(p):
        blend_p = {k: v for k, v in p.items() if any(k.startswith(pre + "_") for pre in prefixes)}
        overlay_p = {k: v for k, v in p.items() if k not in blend_p}
        return VolTargetOverlay(BlendStrategy(_build_components(specs, blend_p)), **overlay_p)
    return build

_BUILDERS = {
    "carry": _carry,
    "carry_voltarget": _carry_voltarget,
    "carry_voltarget_ml": _carry_voltarget_ml,
    "momentum": _momentum,
    "momentum_voltarget": _momentum_voltarget,
    "trend": _trend,
    "trend_voltarget": _trend_voltarget,
    "value": _value,
    "value_voltarget": _value_voltarget,
    "carry_trend": _blend("carry_trend"),
    "carry_trend_value": _blend("carry_trend_value"),
    "carry_trend_voltarget": _blend_voltarget("carry_trend"),
    "carry_trend_value_voltarget": _blend_voltarget("carry_trend_value"),
}

def build_strategy(name: str, params: dict | None = None):
    if name not in _BUILDERS:
        raise KeyError(f"unknown strategy '{name}'; available: {sorted(_BUILDERS)}")
    return _BUILDERS[name](params or {})

def available() -> list:
    return sorted(_BUILDERS)
