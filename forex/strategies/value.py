import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.value import value_signal
from forex.features.carry import basket_weights
from forex.strategies.overlay import VolTargetOverlay
from forex.core.compose import split_params

class ValueStrategy(Strategy):
    NAME = "value"
    def __init__(self, window: int = 60, n_long: int = 3, n_short: int = 3):
        self.window = window
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        signal = value_signal(view.calendar, view.reer, self.window)
        return basket_weights(signal[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"window": self.window, "n_long": self.n_long, "n_short": self.n_short}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"window": Int(36, 84), "n_long": Int(2, 4), "n_short": Int(2, 4)}

class ValueVolTarget(VolTargetOverlay):
    NAME = "value_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("window", "n_long", "n_short"))
        return cls(ValueStrategy(**base), **overlay)
