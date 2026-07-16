"""IBKR intraday historical bars -> DataView, for backtesting/running PRICE strategies on IBKR data.
Requires TWS/Gateway running + ib_async (optional 'live' extra). Fetches N-minute MIDPOINT bars, caches
to parquet, builds a spot panel (USD-per-FX) with zero rates (carry is irrelevant intraday). IBKR gives
prices only, not rate series — so this is for price strategies (trend/momentum), not carry."""
import pandas as pd
from pathlib import Path
from forex.config import CURRENCIES


def _pair(code):
    inv = CURRENCIES[code].spot_invert
    return (f"USD{code}", inv) if inv else (f"{code}USD", False)


def fetch_intraday(codes, bar_size="15 mins", duration="30 D", cache_dir="data_cache/ibkr",
                   host="127.0.0.1", port=7497, client_id=80) -> list:
    """Fetch MIDPOINT bars for each code from IBKR and cache to parquet (as USD-per-FX series). Returns codes."""
    from ib_async import IB, Forex          # lazy: module imports without ib_async
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    tag = bar_size.replace(" ", "")
    ib = IB(); ib.connect(host, port, clientId=client_id, timeout=20, readonly=True)
    try:
        for code in codes:
            ps, inv = _pair(code)
            c = Forex(ps); ib.qualifyContracts(c)
            bars = ib.reqHistoricalData(c, "", duration, bar_size, "MIDPOINT", useRTH=False)
            s = pd.Series({pd.Timestamp(b.date): float(b.close) for b in bars})
            s = (1.0 / s) if inv else s       # -> USD-per-FX (consistent panel convention)
            s.name = code
            s.to_frame().to_parquet(Path(cache_dir) / f"{code}_{tag}.parquet")
    finally:
        ib.disconnect()
    return list(codes)


def fetch_daily(codes, duration="15 Y", cache_dir="data_cache/ibkr_daily",
                host="127.0.0.1", port=7497, client_id=90) -> list:
    """Fetch DAILY MIDPOINT bars for each code from IBKR, cache to parquet (as USD-per-FX series).
    Spot source for the tradeable carry book (FRED lacks CE-Europe spot). Returns codes."""
    from ib_async import IB, Forex          # lazy: module imports without ib_async
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    ib = IB(); ib.connect(host, port, clientId=client_id, timeout=20, readonly=True)
    try:
        for code in codes:
            ps, inv = _pair(code)
            c = Forex(ps); ib.qualifyContracts(c)
            bars = ib.reqHistoricalData(c, "", duration, "1 day", "MIDPOINT", useRTH=False)
            s = pd.Series({pd.Timestamp(b.date): float(b.close) for b in bars})
            s = (1.0 / s) if inv else s       # -> USD-per-FX (consistent panel convention)
            s.name = code
            s.to_frame().to_parquet(Path(cache_dir) / f"{code}.parquet")
    finally:
        ib.disconnect()
    return list(codes)


def build_carry_view(codes, spot_cache="data_cache/ibkr_daily", rate_cache="data_cache", rate_loader=None):
    """Load cached IBKR daily spot (USD-per-FX) + FRED OECD rates into a carry DataView.
    Spot from IBKR (one consistent, deliverable source); rates from FRED 3-month interbank (percent
    -> fraction). This is the reproducible loader for the TRADEABLE_CARRY book."""
    from forex.core.dataview import DataView
    if rate_loader is None:
        from forex.data.fred import load_series
        rate_loader = load_series
    cols = {c: pd.read_parquet(Path(spot_cache) / f"{c}.parquet").squeeze("columns") for c in codes}
    spot = pd.DataFrame(cols)
    spot.index = pd.DatetimeIndex(
        [pd.Timestamp(t).tz_localize(None).normalize() for t in spot.index]).as_unit("us")
    spot = spot[~spot.index.duplicated()].sort_index().dropna(how="any")
    spot.index.name = "date"
    rates = {"USD": rate_loader(CURRENCIES["USD"].rate_fred, cache_dir=rate_cache) / 100.0}
    for code in codes:
        rates[code] = rate_loader(CURRENCIES[code].rate_fred, cache_dir=rate_cache) / 100.0
    return DataView(spot=spot, rates=rates)


def build_intraday_view(codes, cache_dir="data_cache/ibkr", bar_size="15 mins"):
    """Load cached bars into a DataView: spot USD-per-FX panel + zero rates (pure price, carry off)."""
    from forex.core.dataview import DataView
    tag = bar_size.replace(" ", "")
    cols = {c: pd.read_parquet(Path(cache_dir) / f"{c}_{tag}.parquet").squeeze("columns") for c in codes}
    spot = pd.DataFrame(cols).sort_index().dropna(how="any")
    spot.index.name = "date"
    rates = {"USD": pd.Series(0.0, index=spot.index)}
    for code in codes:
        rates[code] = pd.Series(0.0, index=spot.index)
    return DataView(spot=spot, rates=rates)


def bars_per_year(index) -> float:
    """Annualization factor for intraday returns: ACTUAL bars per calendar year (NOT the daily 252).
    Use to annualize Sharpe/vol on intraday returns — the framework's metrics() hardcode 252."""
    span_yr = (index[-1] - index[0]).total_seconds() / (365.25 * 86400)
    return len(index) / span_yr if span_yr > 0 else 252.0
