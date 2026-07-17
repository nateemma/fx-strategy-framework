import math
import pandas as pd


def inverse_vol_weights(prices: pd.DataFrame, lookback: int = 60) -> pd.Series:
    """Compute risk-parity weights (inverse volatility) over the last `lookback` daily returns.

    Args:
        prices: DataFrame with symbols as columns, daily closes as rows (ascending dates).
        lookback: Number of recent daily returns to use for volatility estimation.

    Returns:
        pd.Series indexed by symbol, normalized weights summing to 1.0.
        Symbols with NaN or zero volatility are dropped.
        If all symbols are invalid, returns equal weights (1/N) over ALL input columns.
    """
    # Compute daily pct-change returns
    returns = prices.pct_change().iloc[1:]  # skip first NaN row

    # Take the last `lookback` rows
    recent_returns = returns.iloc[-lookback:]

    # Compute volatility (std) for each symbol
    vols = recent_returns.std()

    # Drop symbols with NaN or zero volatility
    valid = vols[(~vols.isna()) & (vols > 0.0)]

    if len(valid) == 0:
        # All invalid: return equal weights over ALL input columns
        n = len(prices.columns)
        return pd.Series({col: 1.0 / n for col in prices.columns})

    # Inverse volatility: weight ∝ 1 / vol
    inv_vols = 1.0 / valid

    # Normalize to sum to 1.0
    weights = inv_vols / inv_vols.sum()

    return weights


def target_shares(weights: pd.Series, allocation_usd: float, prices: pd.Series) -> dict:
    """Convert weights to integer share counts.

    Args:
        weights: pd.Series of normalized weights (symbol -> weight).
        allocation_usd: Total USD to allocate.
        prices: pd.Series of current prices (symbol -> price).

    Returns:
        dict mapping symbol (str) -> shares (int).
        Omits symbols with: non-positive or NaN price, or zero resulting shares.
    """
    result = {}
    for symbol in weights.index:
        w = float(weights[symbol])
        if w <= 0.0:  # Skip zero or negative weights
            continue
        if symbol not in prices.index:
            continue
        p = float(prices[symbol])
        if not math.isfinite(p) or p <= 0:  # Skip NaN, inf, or non-positive prices
            continue

        shares = round(w * allocation_usd / p)
        if shares > 0:  # Only include if at least 1 share
            result[symbol] = int(shares)

    return result
