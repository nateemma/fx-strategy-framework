import numpy as np
import pandas as pd

def simulate(weights: pd.DataFrame, spot_rets: pd.DataFrame,
             carry: pd.DataFrame, cost_bps: float = 1.0) -> pd.Series:
    cols = weights.columns
    idx = weights.index
    spot = spot_rets.reindex(index=idx, columns=cols).fillna(0.0)
    car = carry.reindex(index=idx, columns=cols).fillna(0.0) / 252.0
    held = weights.shift(1).fillna(0.0)                      # act on next day -> no lookahead
    gross = (held * (spot + car)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1, min_count=1).fillna(weights.abs().sum(axis=1))
    cost = (cost_bps / 1e4) * turnover
    ret = (gross - cost).rename("ret")
    ret.index.name = "date"
    return ret

def metrics(returns: pd.Series) -> dict:
    r = returns.dropna()
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1.0)
    ann_return = (1 + r).prod() ** (252 / len(r)) - 1 if len(r) else 0.0
    ann_vol = r.std() * np.sqrt(252)
    mdd = dd.min() if len(dd) else 0.0
    return {
        "total_return": eq.iloc[-1] - 1 if len(eq) else 0.0,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": (ann_return / ann_vol) if ann_vol else 0.0,
        "max_drawdown": mdd,
        "calmar": (ann_return / abs(mdd)) if mdd < 0 else 0.0,
    }
