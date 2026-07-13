import importlib
import pkgutil
from forex.core.strategy import Strategy

_CACHE: dict[str, dict] = {}

def load_strategies(package: str = "strategies") -> dict:
    if package in _CACHE:
        return _CACHE[package]
    mod = importlib.import_module(package)
    reg: dict[str, type] = {}
    for info in pkgutil.iter_modules(mod.__path__, mod.__name__ + "."):
        if info.ispkg:
            continue                                    # skip subpackages
        m = importlib.import_module(info.name)
        for obj in vars(m).values():
            if (isinstance(obj, type) and issubclass(obj, Strategy)
                    and "NAME" in obj.__dict__ and obj.NAME):
                if obj.NAME in reg and reg[obj.NAME] is not obj:
                    raise ValueError(f"duplicate strategy NAME '{obj.NAME}'")
                reg[obj.NAME] = obj
    _CACHE[package] = reg
    return reg

def build_strategy(name: str, params: dict | None = None, package: str = "strategies") -> Strategy:
    reg = load_strategies(package)
    if name not in reg:
        raise KeyError(f"unknown strategy '{name}'; available: {sorted(reg)}")
    return reg[name].build(params or {})

def available(package: str = "strategies") -> list:
    return sorted(load_strategies(package))
