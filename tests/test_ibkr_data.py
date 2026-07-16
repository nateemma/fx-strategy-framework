import numpy as np, pandas as pd
from forex.data.ibkr import build_intraday_view, bars_per_year, _pair


def test_pair_convention_matches_spot_invert():
    assert _pair("EUR") == ("EURUSD", False)     # spot_invert=False -> C.USD
    assert _pair("MXN") == ("USDMXN", True)      # spot_invert=True  -> USD.C


def test_build_intraday_view_from_cache(tmp_path):
    idx = pd.date_range("2026-06-01", periods=200, freq="15min")
    for code, val in [("EUR", 1.1), ("MXN", 18.0)]:
        pd.Series(val + np.linspace(0, 0.01, 200), index=idx, name=code).to_frame().to_parquet(
            tmp_path / f"{code}_15mins.parquet")
    v = build_intraday_view(["EUR", "MXN"], cache_dir=str(tmp_path), bar_size="15 mins")
    assert list(v.spot.columns) == ["EUR", "MXN"] and len(v.spot) == 200
    assert set(v.rates) == {"USD", "EUR", "MXN"}
    assert (v.rates["EUR"] == 0.0).all()          # zero rates -> carry off


def test_bars_per_year_intraday_factor():
    idx = pd.date_range("2026-01-01", periods=96, freq="15min")   # 1 day of 15-min bars
    ppy = bars_per_year(idx)
    assert 30_000 < ppy < 40_000                  # ~96 bars/day * 365 (much larger than daily 252)
