import pandas as pd
from forex.data.cftc import load_cot, COT_CODES

ROWS = [
    {"report_date_as_yyyy_mm_dd": "2026-01-06T00:00:00.000",
     "noncomm_positions_long_all": "100", "noncomm_positions_short_all": "40", "open_interest_all": "500"},
    {"report_date_as_yyyy_mm_dd": "2026-01-13T00:00:00.000",
     "noncomm_positions_long_all": "60", "noncomm_positions_short_all": "90", "open_interest_all": "520"},
]

def test_load_cot_net_spec_and_cache(tmp_path):
    s = load_cot("099741", cache_dir=str(tmp_path), client=lambda code: ROWS)
    assert list(s.values) == [60.0, -30.0]          # net non-commercial = long - short
    assert s.index[0] == pd.Timestamp("2026-01-06") and s.name == "value"
    # second call must hit the cache, not the client (client here would raise)
    def _boom(code): raise AssertionError("should have used cache")
    s2 = load_cot("099741", cache_dir=str(tmp_path), client=_boom)
    assert list(s2.values) == [60.0, -30.0]

def test_load_cot_passes_contract_code(tmp_path):
    got = {}
    def client(code):
        got["code"] = code
        return ROWS
    load_cot("095741", cache_dir=str(tmp_path), client=client)
    assert got["code"] == "095741"

def test_cot_codes_cover_tradeable_carry_majors():
    for c in ["EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "MXN", "ZAR"]:
        assert c in COT_CODES and COT_CODES[c].isdigit()
