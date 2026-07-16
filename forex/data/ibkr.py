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
