import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.positioning import positioning_signal

class PositioningStrategy(Strategy):
    """Contrarian CFTC positioning: fade crowded speculative positions, dollar-neutral continuous
    weights (unit gross) over the currencies with COT coverage. Uncorrelated diversifier for carry."""
    NAME = "positioning"
    def __init__(self, window: int = 156, lag_days: int = 6):
        self.window = window
        self.lag_days = lag_days

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sig = positioning_signal(view.calendar, view.positioning, self.window, self.lag_days)
        cov = [c for c in view.codes if c in sig.columns]
        if not cov:                                        # no COT coverage -> no positioning tilt
            return pd.DataFrame(0.0, index=view.calendar, columns=view.codes)
        s = sig[cov].sub(sig[cov].mean(axis=1), axis=0)    # cross-sectional demean (dollar-neutral)
        w = s.div(s.abs().sum(axis=1), axis=0)             # unit gross
        return w.reindex(columns=view.codes).fillna(0.0)

    def params(self) -> dict:
        return {"window": self.window, "lag_days": self.lag_days}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"window": Int(104, 208), "lag_days": Int(3, 10)}
