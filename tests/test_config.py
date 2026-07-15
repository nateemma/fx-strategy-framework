from forex.config import CURRENCIES


def test_default_universe_is_g10():
    from forex.config import DEFAULT_CODES
    assert set(DEFAULT_CODES) == {"EUR","JPY","GBP","CHF","AUD","NZD","CAD","NOK","SEK"}
    assert "USD" not in DEFAULT_CODES


def test_em_currencies_present_but_opt_in():
    from forex.config import DEFAULT_CODES, EM
    assert set(EM) == {"MXN","ZAR","BRL","INR","KRW"}
    assert all(c in CURRENCIES for c in EM)                 # loadable
    assert not any(c in DEFAULT_CODES for c in EM)          # but not in the default universe


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


def test_arming_flags_not_loaded_from_toml(tmp_path):
    # confirm/allow_live must be CLI-only — a config file cannot silently arm live placement
    from forex.core.config import RunConfig
    p = tmp_path / "run.toml"
    p.write_text('strategy = "carry"\nconfirm = true\nallow_live = true\n')
    cfg = RunConfig.from_toml(str(p))
    assert cfg.strategy == "carry" and cfg.confirm is False and cfg.allow_live is False
