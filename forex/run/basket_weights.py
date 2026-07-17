import math
import pandas as pd


def inverse_vol_weights(prices: pd.DataFrame, lookback: int = 60) -> pd.Series:
    """Risk-parity weights (inverse volatility) over last `lookback` daily returns."""
    returns = prices.pct_change().iloc[1:]
    recent_returns = returns.iloc[-lookback:]

    vols = recent_returns.std()
    counts = recent_returns.count()

    # Drop: NaN std, zero vol, or insufficient non-NaN returns
    valid = vols[(~vols.isna()) & (vols > 0.0) & (counts >= lookback)]

    if len(valid) == 0:
        n = len(prices.columns)
        return pd.Series({col: 1.0 / n for col in prices.columns})

    inv_vols = 1.0 / valid
    weights = inv_vols / inv_vols.sum()
    return weights


def target_shares(weights: pd.Series, allocation_usd: float, prices: pd.Series) -> dict:
    """Convert weights to integer share counts."""
    result = {}
    for symbol in weights.index:
        w = float(weights[symbol])
        if symbol not in prices.index:
            continue
        p = float(prices[symbol])
        if not math.isfinite(p) or p <= 0:
            continue
        shares = round(w * allocation_usd / p)
        if shares > 0:
            result[symbol] = int(shares)
    return result
