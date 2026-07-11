import numpy as np, pandas as pd
from forex.research.carry_baseline import run_baseline

def _synthetic_loader():
    """A tiny deterministic FRED stand-in: 2 currencies, AUD high-yield & rising."""
    dates = pd.date_range("2018-01-01", periods=600, freq="B")
    series = {
        "DEXUSAL": pd.Series(1.0 + np.linspace(0, 0.2, 600), index=dates, name="value"), # AUD up
        "DEXUSEU": pd.Series(1.1 + np.zeros(600), index=dates, name="value"),            # EUR flat
        "IR3TIB01USM156N": pd.Series(0.01, index=dates, name="value"),
        "IR3TIB01AUM156N": pd.Series(0.06, index=dates, name="value"),  # high carry
        "IR3TIB01EZM156N": pd.Series(0.00, index=dates, name="value"),  # low carry
    }
    def loader(series_id, *, cache_dir, client=None):
        return series[series_id]
    return loader

def test_baseline_runs_and_high_carry_rising_currency_makes_money():
    # Restrict universe to AUD (long) vs EUR (short) via n_long=n_short=1.
    rets, m = run_baseline(cache_dir="unused", loader=_synthetic_loader(),
                           codes=["AUD", "EUR"], n_long=1, n_short=1)
    assert isinstance(rets, pd.Series) and len(rets) > 100
    assert set(["sharpe","max_drawdown","calmar"]).issubset(m)
    assert m["total_return"] > 0    # long high-carry rising AUD, short flat EUR -> positive
