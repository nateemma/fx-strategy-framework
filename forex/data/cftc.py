"""CFTC Commitments of Traders (COT) loader — weekly net non-commercial (speculative) positioning
per currency, from the CFTC legacy futures-only report (Socrata dataset 6dca-aqww). Free, no key.
Keyed on the stable cftc_contract_market_code (contract NAMES change across history: CME<->IMM etc.).
Net spec = noncomm_long - noncomm_short; the classic contrarian crowding signal (fade extremes)."""
from pathlib import Path
import pandas as pd

# Stable CME FX contract codes (cftc_contract_market_code). PLN/HUF/CZK/ILS have no liquid CME contract,
# so the positioning overlay covers the G10+MXN+ZAR part of the carry book, not the CE-Europe legs.
COT_CODES = {
    "EUR": "099741", "JPY": "097741", "GBP": "096742", "CHF": "092741", "CAD": "090741",
    "AUD": "232741", "NZD": "112741", "MXN": "095741", "ZAR": "122741",
}

_DATASET = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

def _cache_path(cache_dir: Path, contract_code: str) -> Path:
    return Path(cache_dir) / f"cot_{contract_code}.parquet"

def _read_cache(cache_dir: Path, contract_code: str) -> pd.Series | None:
    p = _cache_path(cache_dir, contract_code)
    return pd.read_parquet(p)["value"] if p.exists() else None

def _write_cache(cache_dir: Path, contract_code: str, s: pd.Series) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    s.rename("value").to_frame().to_parquet(_cache_path(cache_dir, contract_code))

def _default_fetch(contract_code: str) -> list:
    import json
    import urllib.parse
    import urllib.request
    q = {"$select": "report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all",
         "$where": f"cftc_contract_market_code='{contract_code}'",
         "$order": "report_date_as_yyyy_mm_dd", "$limit": "50000"}
    with urllib.request.urlopen(f"{_DATASET}?{urllib.parse.urlencode(q)}", timeout=40) as r:
        return json.load(r)

def load_cot(contract_code: str, *, cache_dir, client=None, force: bool = False) -> pd.Series:
    """Weekly net non-commercial position (long - short) for a CFTC contract code. Cache-first parquet."""
    if not force:
        cached = _read_cache(cache_dir, contract_code)
        if cached is not None:
            return cached
    if client is None:
        client = _default_fetch
    df = pd.DataFrame(client(contract_code))
    net = df["noncomm_positions_long_all"].astype("float64") - df["noncomm_positions_short_all"].astype("float64")
    s = pd.Series(net.values, index=pd.DatetimeIndex(pd.to_datetime(df["report_date_as_yyyy_mm_dd"])).tz_localize(None))
    s = s.sort_index()
    s.index.name = "date"
    s.name = "value"
    _write_cache(cache_dir, contract_code, s)
    return s
