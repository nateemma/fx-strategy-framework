import numpy as np, pandas as pd
from strategies.research.overlay import run_overlay

def _synthetic_loader():
    dates = pd.date_range("2018-01-01", periods=600, freq="B")
    series = {
        "DEXUSAL": pd.Series(1.0 + np.linspace(0, 0.2, 600), index=dates, name="value"),
        "DEXUSEU": pd.Series(1.1 + np.zeros(600), index=dates, name="value"),
        "IR3TIB01USM156N": pd.Series(1.0, index=dates, name="value"),  # percent units
        "IR3TIB01AUM156N": pd.Series(6.0, index=dates, name="value"),
        "IR3TIB01EZM156N": pd.Series(0.0, index=dates, name="value"),
        "RBAUBIS": pd.Series(100.0, index=dates, name="value"),
        "RBXMBIS": pd.Series(100.0, index=dates, name="value"),
        "VIXCLS": pd.Series(20.0, index=dates, name="value"),
        "BAA10Y": pd.Series(4.0, index=dates, name="value"),
        "T10Y2Y": pd.Series(1.0, index=dates, name="value"),
    }
    def loader(series_id, *, cache_dir, client=None):
        return series[series_id]
    return loader

def test_run_overlay_returns_bare_and_overlay():
    out = run_overlay(cache_dir="unused", loader=_synthetic_loader(),
                      codes=["AUD", "EUR"], n_long=1, n_short=1, cadence="D")
    assert set(out) == {"bare", "overlay", "metrics_bare", "metrics_overlay"}
    assert isinstance(out["bare"], pd.Series) and isinstance(out["overlay"], pd.Series)
    assert "sharpe" in out["metrics_bare"] and "sharpe" in out["metrics_overlay"]
    assert len(out["overlay"]) == len(out["bare"])

def test_run_overlay_delegates_and_overlay_differs_from_bare():
    out = run_overlay(cache_dir="unused", loader=_synthetic_loader(),
                      codes=["AUD","EUR"], n_long=1, n_short=1, cadence="D")
    assert set(out) == {"bare","overlay","metrics_bare","metrics_overlay"}
    # overlay is a levered version -> its return series is not identical to bare
    assert not out["bare"].equals(out["overlay"])
    assert "sharpe" in out["metrics_overlay"]
