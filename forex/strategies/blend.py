import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.volforecast import ewma_vol

class BlendStrategy(Strategy):
    def __init__(self, components: dict, lam: float = 0.94,
                 cadence: str = "MS", cost_bps: float = 1.0):
        self.components = components
        self.lam = lam
        self.cadence = cadence
        self.cost_bps = cost_bps

    def fit(self, train: DataView) -> None:
        for sub in self.components.values():
            sub.fit(train)

    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import backtest
        sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
        any_w = next(iter(sub_w.values()))
        idx, cols = any_w.index, any_w.columns
        inv = {}
        for p, s in self.components.items():
            r = backtest(s, view, cost_bps=self.cost_bps).returns
            inv[p] = 1.0 / ewma_vol(r, lam=self.lam).reindex(idx).ffill()
        inv_df = pd.DataFrame(inv, index=idx)
        norm = inv_df.div(inv_df.sum(axis=1), axis=0)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        for p in self.components:
            out = out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
        return out

    def params(self) -> dict:
        return {f"{p}_{k}": v for p, s in self.components.items()
                for k, v in s.params().items()}

    def search_space(self) -> dict:
        return {f"{p}_{k}": sp for p, s in self.components.items()
                for k, sp in s.search_space().items()}
