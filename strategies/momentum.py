import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from strategies.features.momentum import momentum_signal
from strategies.features.basket import basket_weights
from strategies.overlay import VolTargetOverlay
from forex.core.compose import split_params

class MomentumStrategy(Strategy):
    NAME = "momentum"
    def __init__(self, lookback: int = 63, n_long: int = 3, n_short: int = 3):
        self.lookback = lookback
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        signal = momentum_signal(view.spot, self.lookback)
        return basket_weights(signal[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"lookback": self.lookback, "n_long": self.n_long, "n_short": self.n_short}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"lookback": Int(21, 126), "n_long": Int(2, 4), "n_short": Int(2, 4)}

class MomentumVolTarget(VolTargetOverlay):
    NAME = "momentum_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("lookback", "n_long", "n_short"))
        return cls(MomentumStrategy(**base), **overlay)
