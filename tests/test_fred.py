from pathlib import Path
import pandas as pd
from forex.data.fred import load_series

class FakeFred:
    """Stand-in for fredapi.Fred that reads a CSV fixture."""
    def __init__(self, fixture): self.fixture = fixture
    def get_series(self, series_id):
        df = pd.read_csv(self.fixture, parse_dates=["date"]).set_index("date")["value"]
        return df

def test_load_series_from_client_and_caches(tmp_path):
    client = FakeFred("tests/fixtures/DEXUSEU.csv")
    s = load_series("DEXUSEU", cache_dir=tmp_path, client=client)
    assert s.index.name == "date"
    assert s.iloc[0] == 1.1194
    assert (tmp_path / "DEXUSEU.parquet").exists()   # cache written

def test_load_series_reads_cache_without_client(tmp_path):
    client = FakeFred("tests/fixtures/DEXUSEU.csv")
    load_series("DEXUSEU", cache_dir=tmp_path, client=client)   # populate cache
    s = load_series("DEXUSEU", cache_dir=tmp_path, client=None)  # no client -> must hit cache
    assert len(s) == 3
