import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.volforecast import ewma_vol

class VolTargetOverlay(Strategy):
    def __init__(self, base: Strategy, target_vol: float = 0.10, cap: float = 1.5,
                 cadence: str = "MS", lam: float = 0.94, cost_bps: float = 1.0):
        self.base = base
        self.target_vol = target_vol
        self.cap = cap
        self.cadence = cadence
        self.lam = lam
        self.cost_bps = cost_bps

    def fit(self, train: DataView) -> None:
        self.base.fit(train)

    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import backtest
        w = self.base.target_weights(view)
        base_ret = backtest(self.base, view, cost_bps=self.cost_bps).returns
        vf = self._vol_forecast(base_ret).reindex(w.index).ffill()
        raw = (self.target_vol / vf).clip(upper=self.cap)
        L = raw.resample(self.cadence).first().reindex(w.index, method="ffill")
        return w.mul(L, axis=0)   # causal, NOT pre-shifted; backtest applies shift(1)

    def _vol_forecast(self, base_ret: pd.Series) -> pd.Series:
        return ewma_vol(base_ret, lam=self.lam)

    def params(self) -> dict:
        return {"target_vol": self.target_vol, "cap": self.cap,
                "cadence": self.cadence, "lam": self.lam}

    def search_space(self) -> dict:
        from forex.core.space import Float
        return {**self.base.search_space(),
                "target_vol": Float(0.06, 0.15), "cap": Float(1.0, 2.0)}
