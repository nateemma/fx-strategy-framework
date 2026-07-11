import pandas as pd

def vol_target(carry_ret: pd.Series, vol_forecast: pd.Series,
               target_vol: float = 0.10, cap: float = 1.5,
               cadence: str = "MS", cost_bps: float = 1.0) -> pd.Series:
    """Scale carry returns to a volatility target.

    scale = clip(target_vol / vol_forecast, upper=cap), stepped at `cadence`
    (held constant between steps), applied to the NEXT day via .shift(1) so
    there is no lookahead, minus turnover cost on leverage changes.
    """
    vf = vol_forecast.reindex(carry_ret.index).ffill()
    raw = (target_vol / vf).clip(upper=cap)
    stepped = raw.resample(cadence).first().reindex(carry_ret.index, method="ffill")
    held = stepped.shift(1).fillna(0.0)                 # no lookahead
    turnover = stepped.diff().abs().fillna(stepped.abs())
    cost = (cost_bps / 1e4) * turnover
    out = (held * carry_ret - cost).rename("ret")
    out.index.name = "date"
    return out
