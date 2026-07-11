import pandas as pd
from forex.config import CURRENCIES
from forex.data.fred import load_series

def build_spot_panel(cache_dir, loader=load_series, codes=None) -> pd.DataFrame:
    """USD per 1 unit of each foreign currency (spot_invert series inverted)."""
    if codes is None:
        codes = [c for c in CURRENCIES if c != "USD"]
    cols = {}
    for code in codes:
        cur = CURRENCIES[code]
        s = loader(cur.spot_fred, cache_dir=cache_dir).astype("float64")
        cols[code] = (1.0 / s) if cur.spot_invert else s
    panel = pd.DataFrame(cols).sort_index()
    panel = panel.ffill().dropna(how="all")
    panel.index.name = "date"
    return panel

def spot_returns(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.pct_change().dropna(how="all")
