import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.carry import carry_signal
from strategies.features.basket import basket_weights
from strategies.overlay import VolTargetOverlay
from strategies.mloverlay import MLVolTargetOverlay
from forex.core.compose import split_params

class CarryStrategy(Strategy):
    NAME = "carry"
    def __init__(self, n_long: int = 3, n_short: int = 3):
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        signal = carry_signal(view.calendar, view.rates)
        return basket_weights(signal[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"n_long": self.n_long, "n_short": self.n_short}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"n_long": Int(2, 4), "n_short": Int(2, 4)}

class CarryVolTarget(VolTargetOverlay):
    NAME = "carry_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), **overlay)

class CarryVolTargetML(MLVolTargetOverlay):
    NAME = "carry_voltarget_ml"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), **overlay)
