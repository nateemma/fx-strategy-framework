import pandas as pd

def ewma_vol(returns: pd.Series, lam: float = 0.94,
             periods_per_year: int = 252) -> pd.Series:
    """Annualized RiskMetrics EWMA volatility of a return series.

    EWMA variance with adjust=False: var_t = lam*var_{t-1} + (1-lam)*r_t^2.
    Causality is the caller's responsibility — the vol-target overlay applies
    this forecast with a .shift(1) so day t is sized from data through t-1.
    """
    var = returns.pow(2).ewm(alpha=1.0 - lam, adjust=False).mean()
    return (var * periods_per_year) ** 0.5
