import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from strategies.features.trend import trend_signal, directional_weights
from strategies.overlay import VolTargetOverlay
from forex.core.compose import split_params

class TrendStrategy(Strategy):
    NAME = "trend"
    def __init__(self, signal_type: str = "tsmom", lookback: int = 252, band: float = 0.0):
        self.signal_type = signal_type
        self.lookback = lookback
        self.band = band

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sig = trend_signal(view.spot[view.codes], self.signal_type, self.lookback, self.band)
        return directional_weights(sig)

    def params(self) -> dict:
        return {"signal_type": self.signal_type, "lookback": self.lookback, "band": self.band}

    def search_space(self) -> dict:
        from forex.core.space import Categorical, Int, Float
        return {"signal_type": Categorical(["tsmom", "ema", "donchian"]),
                "lookback": Int(21, 252),
                "band": Float(0.0, 0.10)}

class TrendVolTarget(VolTargetOverlay):
    NAME = "trend_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("signal_type", "lookback", "band"))
        return cls(TrendStrategy(**base), **overlay)
