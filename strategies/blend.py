import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.volforecast import ewma_vol
from strategies.carry import CarryStrategy
from strategies.trend import TrendStrategy
from strategies.value import ValueStrategy
from strategies.overlay import VolTargetOverlay
from forex.core.compose import split_prefixed, build_components

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
        from forex.run.backtest import returns_of
        sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
        any_w = next(iter(sub_w.values()))
        idx, cols = any_w.index, any_w.columns
        inv = {}
        for p in self.components:
            r = returns_of(sub_w[p], view, self.cost_bps)
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

class CarryTrend(BlendStrategy):
    NAME = "carry_trend"
    SPECS = [("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
             ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108})]
    @classmethod
    def build(cls, params):
        return cls(build_components(cls.SPECS, params))

class CarryTrendValue(BlendStrategy):
    NAME = "carry_trend_value"
    SPECS = [("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
             ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108}),
             ("value", ValueStrategy, {"window": 42, "n_long": 4, "n_short": 4})]
    @classmethod
    def build(cls, params):
        return cls(build_components(cls.SPECS, params))

class CarryTrendVolTarget(VolTargetOverlay):
    NAME = "carry_trend_voltarget"
    DEFAULTS = {"target_vol": 0.062, "cap": 1.20}      # validated bests (hyperopt target_vol,cap)
    @classmethod
    def build(cls, params):
        blend_p, overlay = split_prefixed(params, ("carry", "trend"))
        return cls(BlendStrategy(build_components(CarryTrend.SPECS, blend_p)),
                   **{**cls.DEFAULTS, **overlay})

class CarryTrendValueVolTarget(VolTargetOverlay):
    NAME = "carry_trend_value_voltarget"
    @classmethod
    def build(cls, params):
        blend_p, overlay = split_prefixed(params, ("carry", "trend", "value"))
        return cls(BlendStrategy(build_components(CarryTrendValue.SPECS, blend_p)), **overlay)
