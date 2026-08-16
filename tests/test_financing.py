import pytest

from forex.run.financing import (
    MIN_ABS_BENCHMARK,
    annual_carry,
    financing_summary,
    leg_ratios,
)


def leg(ccy, balance, accrued, rate, benchmark, asof="2026-06-01"):
    """One open currency leg: native balance/accrued, USD rate, and its FRED benchmark."""
    return {"ccy": ccy, "balance": balance, "accrued": accrued,
            "rate": rate, "benchmark": benchmark, "asof": asof}


# ---------------------------------------------------------------- Phase 2: per-leg measurement

def test_ratio_is_the_accrual_period_when_financing_is_at_benchmark():
    """accrued/balance = rate * period, so dividing by the rate leaves the period."""
    period = 0.05
    legs = [leg("CAD", 100_000, 100_000 * 0.0227 * period, 0.72, 0.0227),
            leg("MXN", -2_000_000, -2_000_000 * 0.0676 * period, 0.0587, 0.0676)]
    ratios = leg_ratios(legs)
    assert all(r.ratio == pytest.approx(period) for r in ratios)


def test_ratio_is_period_independent_across_currencies():
    """The load-bearing property: currencies differ, the shared period cancels."""
    period = 0.031
    legs = [leg("EUR", 90_000, 90_000 * 0.0203 * period, 1.157, 0.0203),
            leg("ZAR", 500_000, 500_000 * 0.0711 * period, 0.0618, 0.0711),
            leg("PLN", -300_000, -300_000 * 0.0385 * period, 0.2686, 0.0385)]
    ratios = [r.ratio for r in leg_ratios(legs)]
    assert max(ratios) - min(ratios) < 1e-9


def test_a_leg_earning_less_than_benchmark_shows_a_smaller_ratio():
    legs = [leg("CAD", 100_000, 100_000 * 0.0227 * 0.05, 0.72, 0.0227),      # at benchmark
            leg("EUR", 100_000, 100_000 * 0.0203 * 0.05 * 0.25, 1.157, 0.0203)]  # quarter of it
    by = {r.ccy: r for r in leg_ratios(legs)}
    assert by["EUR"].ratio == pytest.approx(by["CAD"].ratio * 0.25)


def test_side_is_derived_from_the_balance_sign():
    by = {r.ccy: r for r in leg_ratios([leg("CAD", 100.0, 1.0, 0.72, 0.0227),
                                        leg("MXN", -100.0, -1.0, 0.0587, 0.0676)])}
    assert by["CAD"].side == "LONG"
    assert by["MXN"].side == "SHORT"


def test_usd_exposure_uses_the_exchange_rate():
    r = leg_ratios([leg("HUF", 20_000_000, 14_000, 0.0031865, 0.0598)])[0]
    assert r.usd == pytest.approx(20_000_000 * 0.0031865)


# ---------------------------------------------------------------- Phase 3 (US1): the asymmetry

def test_long_and_short_medians_are_reported_separately():
    legs = [leg("CAD", 100_000, 100_000 * 0.0227 * 0.01, 0.72, 0.0227),
            leg("EUR", 100_000, 100_000 * 0.0203 * 0.01, 1.157, 0.0203),
            leg("MXN", -100_000, -100_000 * 0.0676 * 0.05, 0.0587, 0.0676),
            leg("PLN", -100_000, -100_000 * 0.0385 * 0.05, 0.2686, 0.0385)]
    s = financing_summary(legs)
    assert s.long_median == pytest.approx(0.01)
    assert s.short_median == pytest.approx(0.05)
    assert s.asymmetry == pytest.approx(5.0)


def test_near_zero_benchmark_legs_are_excluded_from_medians_and_counted():
    """CHF at -0.045% makes the ratio explode; it must not move the summary."""
    legs = [leg("CAD", 100_000, 100_000 * 0.0227 * 0.01, 0.72, 0.0227),
            leg("NOK", 100_000, 100_000 * 0.0457 * 0.01, 0.106, 0.0457),
            leg("CHF", -80_000, -32.0, 1.23, -0.00045)]
    s = financing_summary(legs)
    assert s.n_excluded_near_zero == 1
    assert s.long_median == pytest.approx(0.01)
    assert all(r.ccy != "CHF" for r in s.ratios_used)


def test_a_leg_at_exactly_the_threshold_is_excluded():
    legs = [leg("XXX", 100_000, 10.0, 1.0, MIN_ABS_BENCHMARK / 2)]
    assert financing_summary(legs).n_excluded_near_zero == 1


def test_zero_accrual_is_measured_not_missing():
    """NZD earns exactly nothing — a real finding, not absent data."""
    r = leg_ratios([leg("NZD", 43_914, 0.0, 0.589, 0.0268)])[0]
    assert r.accrued_usd == 0.0
    assert r.ratio == 0.0
    assert r.ratio is not None


def test_negative_accrual_on_a_long_leg_is_preserved():
    """ZAR is long at a 7.1% benchmark and still accrues negative."""
    r = leg_ratios([leg("ZAR", 594_607, -42.03, 0.0618, 0.0711)])[0]
    assert r.side == "LONG"
    assert r.accrued_usd < 0
    assert r.ratio < 0


def test_negligible_legs_do_not_distort_the_medians():
    legs = [leg("CAD", 100_000, 100_000 * 0.0227 * 0.02, 0.72, 0.0227),
            leg("NOK", 100_000, 100_000 * 0.0457 * 0.02, 0.106, 0.0457),
            leg("AUD", -2.0, -0.5, 0.708, 0.0446)]     # ~$1.4 of exposure
    s = financing_summary(legs)
    assert all(r.ccy != "AUD" for r in s.ratios_used)


# ---------------------------------------------------------------- Phase 5 (US3): the drag

def test_benchmark_annual_carry_sums_exposure_times_rate():
    legs = [leg("CAD", 100_000, 0.0, 1.0, 0.02), leg("MXN", -50_000, 0.0, 1.0, 0.10)]
    assert annual_carry(legs) == pytest.approx(100_000 * 0.02 - 50_000 * 0.10)


def test_a_book_positioned_for_positive_carry_shows_positive_benchmark_carry():
    legs = [leg("ZAR", 100_000, 0.0, 1.0, 0.0711),      # long high-yielder
            leg("JPY", -100_000, 0.0, 1.0, 0.0127)]     # short low-yielder
    assert annual_carry(legs) > 0


def test_realised_gap_is_benchmark_minus_realised():
    """A book earning nothing while benchmark says +2000 has a -2000 gap."""
    legs = [leg("CAD", 100_000, 0.0, 1.0, 0.02)]
    s = financing_summary(legs, period_years=0.05)
    assert s.benchmark_annual == pytest.approx(2000.0)
    assert s.realised_annual == pytest.approx(0.0)
    assert s.gap_annual == pytest.approx(-2000.0)


def test_gap_is_also_expressed_against_gross_exposure():
    legs = [leg("CAD", 1_000_000, 0.0, 1.0, 0.02)]
    s = financing_summary(legs, period_years=0.05)
    assert s.gross_usd == pytest.approx(1_000_000.0)
    assert s.gap_pct_of_gross == pytest.approx(-0.02)


def test_realised_annual_scales_with_the_assumed_period():
    """FR-005: the annualised figure depends on the period, which is why a range is reported."""
    legs = [leg("CAD", 100_000, -100.0, 1.0, 0.02)]
    short_period = financing_summary(legs, period_years=0.02).realised_annual
    long_period = financing_summary(legs, period_years=0.08).realised_annual
    assert short_period < long_period < 0
    assert short_period == pytest.approx(long_period * 4.0)


def test_empty_book_does_not_divide_by_zero():
    s = financing_summary([])
    assert s.gross_usd == 0.0
    assert s.gap_pct_of_gross is None
    assert s.long_median is None
    assert s.asymmetry is None


# ---------------------------------------------------------------- benchmark rate lookup

def test_benchmark_rate_returns_the_latest_value_and_its_asof_date(tmp_path):
    import pandas as pd
    from forex.config import CURRENCIES
    from forex.run.financing import benchmark_rate
    idx = pd.to_datetime(["2026-05-01", "2026-06-01"])
    pd.DataFrame({"v": [2.10, 2.27]}, index=idx).to_parquet(
        tmp_path / f"{CURRENCIES['CAD'].rate_fred}.parquet")
    rate, asof = benchmark_rate("CAD", cache_dir=tmp_path)
    assert rate == pytest.approx(0.0227)      # percent -> decimal
    assert asof == "2026-06-01"


def test_benchmark_rate_is_absent_rather_than_guessed_when_uncached(tmp_path):
    from forex.run.financing import benchmark_rate
    assert benchmark_rate("CAD", cache_dir=tmp_path) == (None, None)


def test_benchmark_rate_rejects_an_unknown_currency(tmp_path):
    from forex.run.financing import benchmark_rate
    assert benchmark_rate("XYZ", cache_dir=tmp_path) == (None, None)


def test_benchmark_rate_reads_the_real_cache():
    from forex.run.financing import benchmark_rate
    rate, asof = benchmark_rate("MXN")
    assert rate is not None and 0.0 < rate < 0.5
    assert asof and asof.startswith("202")
