import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.carry import carry_signal
from strategies.features.basket import basket_weights

class CarryMomStrategy(Strategy):
    """Carry momentum: rank by the CHANGE in the rate differential over `lookback` days (is the carry
    widening or narrowing?). A diversifying sleeve — orthogonal to the carry level and to positioning."""
    NAME = "carry_mom"
    def __init__(self, lookback: int = 252, n_long: int = 3, n_short: int = 3):
        self.lookback = lookback
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        mom = carry_signal(view.calendar, view.rates).diff(self.lookback)
        return basket_weights(mom[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"lookback": self.lookback, "n_long": self.n_long, "n_short": self.n_short}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"lookback": Int(63, 378), "n_long": Int(2, 4), "n_short": Int(2, 4)}
