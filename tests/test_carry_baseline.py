import numpy as np, pandas as pd
from forex.research.carry_baseline import run_baseline

def _synthetic_loader():
    """A tiny deterministic FRED stand-in: 2 currencies, AUD high-yield & rising."""
    dates = pd.date_range("2018-01-01", periods=600, freq="B")
    series = {
        "DEXUSAL": pd.Series(1.0 + np.linspace(0, 0.2, 600), index=dates, name="value"), # AUD up
        "DEXUSEU": pd.Series(1.1 + np.zeros(600), index=dates, name="value"),            # EUR flat
        "IR3TIB01USM156N": pd.Series(1.0, index=dates, name="value"),
        "IR3TIB01AUM156N": pd.Series(6.0, index=dates, name="value"),  # high carry
        "IR3TIB01EZM156N": pd.Series(0.0, index=dates, name="value"),  # low carry
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

def test_rates_normalized_from_percent_keeps_carry_sane():
    dates = pd.date_range("2018-01-01", periods=400, freq="B")
    series = {
        "DEXUSAL": pd.Series(1.0, index=dates, name="value"),   # flat spot
        "DEXUSEU": pd.Series(1.1, index=dates, name="value"),   # flat spot
        "IR3TIB01USM156N": pd.Series(1.0, index=dates, name="value"),  # 1% in percent units
        "IR3TIB01AUM156N": pd.Series(6.0, index=dates, name="value"),  # 6%
        "IR3TIB01EZM156N": pd.Series(0.0, index=dates, name="value"),  # 0%
    }
    def loader(series_id, *, cache_dir, client=None):
        return series[series_id]
    _, m = run_baseline(cache_dir="unused", loader=loader, codes=["AUD", "EUR"],
                        n_long=1, n_short=1, cost_bps=0.0)
    # Long AUD carry 5% + short EUR carry (0-1=-1%, short earns +1%) ~ single-digit annualized.
    # Un-normalized (percent treated as decimal) would be ~hundreds of percent.
    assert m["ann_return"] < 0.5

def test_run_baseline_matches_backtest_of_carry_strategy():
    from forex.core.dataview import DataView
    from forex.strategies.carry import CarryStrategy
    from forex.run.backtest import backtest
    loader = _synthetic_loader()   # existing helper in this test file
    daily, m = run_baseline(cache_dir="unused", loader=loader, codes=["AUD","EUR"], n_long=1, n_short=1)
    view = DataView.from_fred("unused", loader=loader, codes=["AUD","EUR"])
    r = backtest(CarryStrategy(1,1), view, cost_bps=1.0)
    assert (daily.round(10) == r.returns.round(10)).all()     # byte-identical delegation
    assert m == r.metrics
