from forex.config import CURRENCIES


def test_universe_is_g10():
    assert set(CURRENCIES) == {"USD","EUR","JPY","GBP","CHF","AUD","NZD","CAD","NOK","SEK"}


def test_usd_is_base():
    assert CURRENCIES["USD"].spot_fred is None


def test_jpy_is_inverted():
    # DEXJPUS is JPY-per-USD, so it must be flagged for inversion to USD-per-JPY
    assert CURRENCIES["JPY"].spot_invert is True
    assert CURRENCIES["EUR"].spot_invert is False  # DEXUSEU is already USD-per-EUR
