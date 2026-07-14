import numpy as np
import pandas as pd
from forex.core.dataview import DataView
from strategies.overlay import VolTargetOverlay
from strategies.features.mlvol import HARVolForecaster
from forex.features.volforecast import ewma_vol

class MLVolTargetOverlay(VolTargetOverlay):
    def __init__(self, base, *, horizon: int = 21, ridge_alpha: float = 1.0,
                 use_macro: bool = False, **kw):
        super().__init__(base, **kw)
        self.horizon = horizon
        self.ridge_alpha = ridge_alpha
        self.use_macro = use_macro
        self.forecaster = HARVolForecaster()

    def _build_exog(self, view, index):
        m = view.macro
        ex = pd.DataFrame(index=index)
        ex["vix"] = np.log(m["vix"].reindex(index, method="ffill"))
        ex["credit"] = np.log(m["credit"].reindex(index, method="ffill"))
        ex["term"] = m["term"].reindex(index, method="ffill")
        return ex

    def fit(self, train: DataView) -> None:
        from forex.run.backtest import backtest
        self.base.fit(train)
        base_ret = backtest(self.base, train, cost_bps=self.cost_bps).returns
        exog = self._build_exog(train, base_ret.index) if self.use_macro else None
        self.forecaster.fit(base_ret, exog=exog, horizon=self.horizon, alpha=self.ridge_alpha)

    def _vol_forecast(self, base_ret, view):
        exog = self._build_exog(view, base_ret.index) if self.use_macro else None
        if not self.forecaster.fitted:
            self.forecaster.fit(base_ret, exog=exog, horizon=self.horizon, alpha=self.ridge_alpha)
        har = self.forecaster.predict(base_ret, exog=exog)
        return har.fillna(ewma_vol(base_ret, lam=self.lam))

    def params(self) -> dict:
        return {**super().params(), "horizon": self.horizon, "ridge_alpha": self.ridge_alpha}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {**super().search_space(), "horizon": Int(10, 42)}
