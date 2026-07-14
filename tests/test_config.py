from forex.config import CURRENCIES


def test_universe_is_g10():
    assert set(CURRENCIES) == {"USD","EUR","JPY","GBP","CHF","AUD","NZD","CAD","NOK","SEK"}


def test_usd_is_base():
    assert CURRENCIES["USD"].spot_fred is None


def test_jpy_is_inverted():
    # DEXJPUS is JPY-per-USD, so it must be flagged for inversion to USD-per-JPY
    assert CURRENCIES["JPY"].spot_invert is True
    assert CURRENCIES["EUR"].spot_invert is False  # DEXUSEU is already USD-per-EUR


def test_reer_fred_set_for_non_usd_none_for_usd():
    assert CURRENCIES["USD"].reer_fred is None
    assert CURRENCIES["AUD"].reer_fred == "RBAUBIS"
    assert all(CURRENCIES[c].reer_fred is not None for c in CURRENCIES if c != "USD")


def test_macro_series():
    from forex.config import MACRO_SERIES
    assert MACRO_SERIES == {"vix": "VIXCLS", "credit": "BAA10Y", "term": "T10Y2Y"}
