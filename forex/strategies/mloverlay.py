import pandas as pd
from forex.core.dataview import DataView
from forex.strategies.overlay import VolTargetOverlay
from forex.features.mlvol import HARVolForecaster
from forex.features.volforecast import ewma_vol

class MLVolTargetOverlay(VolTargetOverlay):
    def __init__(self, base, *, horizon: int = 21, ridge_alpha: float = 1.0, **kw):
        super().__init__(base, **kw)
        self.horizon = horizon
        self.ridge_alpha = ridge_alpha
        self.forecaster = HARVolForecaster()

    def fit(self, train: DataView) -> None:
        from forex.run.backtest import backtest
        self.base.fit(train)
        base_ret = backtest(self.base, train, cost_bps=self.cost_bps).returns
        self.forecaster.fit(base_ret, horizon=self.horizon, alpha=self.ridge_alpha)

    def _vol_forecast(self, base_ret: pd.Series) -> pd.Series:
        if not self.forecaster.fitted:      # plain-backtest self-fit (in-sample); causal-checks must fit() first
            self.forecaster.fit(base_ret, horizon=self.horizon, alpha=self.ridge_alpha)
        har = self.forecaster.predict(base_ret)
        return har.fillna(ewma_vol(base_ret, lam=self.lam))

    def params(self) -> dict:
        return {**super().params(), "horizon": self.horizon, "ridge_alpha": self.ridge_alpha}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {**super().search_space(), "horizon": Int(10, 42)}
