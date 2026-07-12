import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.carry import carry_signal, basket_weights

class CarryStrategy(Strategy):
    def __init__(self, n_long: int = 3, n_short: int = 3):
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        signal = carry_signal(view.calendar, view.rates)
        return basket_weights(signal[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"n_long": self.n_long, "n_short": self.n_short}
