import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.volforecast import ewma_vol
from strategies.carry import CarryStrategy
from strategies.trend import TrendStrategy
from strategies.value import ValueStrategy
from strategies.positioning import PositioningStrategy
from strategies.carrymom import CarryMomStrategy
from strategies.overlay import VolTargetOverlay
from forex.core.compose import split_prefixed, build_components, split_params

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

    def _sub_weights(self, view: DataView):
        sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
        any_w = next(iter(sub_w.values()))
        return sub_w, any_w.index, any_w.columns

    def _base_norm(self, view: DataView, sub_w, idx) -> pd.DataFrame:
        from forex.run.backtest import returns_of
        inv = {}
        for p in self.components:
            r = returns_of(sub_w[p], view, self.cost_bps)
            inv[p] = 1.0 / ewma_vol(r, lam=self.lam).reindex(idx).ffill()
        inv_df = pd.DataFrame(inv, index=idx)
        return inv_df.div(inv_df.sum(axis=1), axis=0)

    def _combine(self, sub_w, norm, idx, cols) -> pd.DataFrame:
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        for p in self.components:
            out = out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
        return out

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sub_w, idx, cols = self._sub_weights(view)
        norm = self._base_norm(view, sub_w, idx)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        return self._combine(sub_w, norm, idx, cols)

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

class CarryCot(BlendStrategy):
    NAME = "carry_cot"
    SPECS = [("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
             ("positioning", PositioningStrategy, {})]
    @classmethod
    def build(cls, params):
        return cls(build_components(cls.SPECS, params))

class CarryCotMom(BlendStrategy):
    NAME = "carry_cot_mom"
    SPECS = [("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
             ("positioning", PositioningStrategy, {}),
             ("carrymom", CarryMomStrategy, {"lookback": 252, "n_long": 3, "n_short": 3})]
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

class CarryTrendCrash(BlendStrategy):
    NAME = "carry_trend_crash"
    SPECS = CarryTrend.SPECS
    def __init__(self, components, dd_threshold: float = 0.05, tilt: float = 0.30, **kw):
        super().__init__(components, **kw)
        self.dd_threshold = dd_threshold
        self.tilt = tilt

    def _crash_stress(self, view, sub_w, idx):
        from forex.run.backtest import returns_of
        rc = returns_of(sub_w["carry"], view, self.cost_bps).reindex(idx).fillna(0.0)
        eq = (1.0 + rc).cumprod()
        depth = -(eq / eq.cummax() - 1.0)
        return ((depth - self.dd_threshold) / self.dd_threshold).clip(lower=0.0, upper=1.0)

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sub_w, idx, cols = self._sub_weights(view)
        norm = self._base_norm(view, sub_w, idx)

        if self.tilt > 0:
            norm = norm.copy()
            shift = self.tilt * self._crash_stress(view, sub_w, idx)
            norm["trend"] = (norm["trend"] + shift).clip(lower=0.0, upper=1.0)
            norm["carry"] = (norm["carry"] - shift).clip(lower=0.0, upper=1.0)
            norm = norm.div(norm.sum(axis=1), axis=0)

        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        return self._combine(sub_w, norm, idx, cols)

    def params(self) -> dict:
        return {**super().params(), "dd_threshold": self.dd_threshold, "tilt": self.tilt}

    def search_space(self) -> dict:
        from forex.core.space import Float
        return {**super().search_space(),
                "dd_threshold": Float(0.02, 0.15), "tilt": Float(0.0, 0.5)}

    @classmethod
    def build(cls, params):
        own, comps = split_params(params, ("dd_threshold", "tilt"))
        return cls(build_components(cls.SPECS, comps), **own)

class CarryTrendCrashVolTarget(VolTargetOverlay):
    NAME = "carry_trend_crash_voltarget"
    DEFAULTS = {"target_vol": 0.062, "cap": 1.20}
    @classmethod
    def build(cls, params):
        crash_p, rest = split_params(params, ("dd_threshold", "tilt"))
        blend_p, overlay = split_prefixed(rest, ("carry", "trend"))
        inner = CarryTrendCrash(build_components(CarryTrend.SPECS, blend_p), **crash_p)
        return cls(inner, **{**cls.DEFAULTS, **overlay})
