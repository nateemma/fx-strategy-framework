import numpy as np
import pandas as pd
import pytest

from forex.backtest.financing import CREDIT_SPREAD, DEBIT_SPREAD, SCHEDULE_SOURCE, financing_spreads
from forex.backtest.portfolio import simulate
from forex.config import TRADEABLE_CARRY


def idx4(n=4):
    return pd.date_range("2026-01-01", periods=n, freq="D")


def frame(codes, values, n=4):
    """n daily rows of `values` per code."""
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({c: [values[c]] * n for c in codes}, index=idx)


def rates_for(codes, level=0.05, usd=0.03, n=4):
    r = {c: pd.Series(level, index=pd.date_range("2026-01-01", periods=n, freq="D")) for c in codes}
    r["USD"] = pd.Series(usd, index=pd.date_range("2026-01-01", periods=n, freq="D"))
    return r


# ---------------------------------------------------------------- Phase 2: the schedule

def test_every_tradeable_currency_has_a_schedule_entry():
    for code in TRADEABLE_CARRY + ["USD"]:
        assert code in CREDIT_SPREAD, f"{code} missing a credit spread"
        assert code in DEBIT_SPREAD, f"{code} missing a debit spread"


def test_debit_spreads_are_positive_costs():
    assert all(v > 0 for v in DEBIT_SPREAD.values())


def test_credit_spreads_are_non_negative():
    assert all(v >= 0 for v in CREDIT_SPREAD.values())


def test_the_schedule_records_its_source():
    assert "interactivebrokers" in SCHEDULE_SOURCE.lower()
    assert "2026" in SCHEDULE_SOURCE


# ---------------------------------------------------------------- spread computation

def test_long_spread_is_credit_shortfall_plus_usd_borrowing():
    rates = rates_for(["CAD"], level=0.05, usd=0.03)
    lon, sho = financing_spreads(rates['USD'].index, rates, ["CAD"])
    expected = CREDIT_SPREAD["CAD"] + DEBIT_SPREAD["USD"]
    assert lon["CAD"].iloc[0] == pytest.approx(expected)


def test_short_spread_is_currency_borrowing_plus_usd_credit_shortfall():
    rates = rates_for(["CAD"], level=0.05, usd=0.03)
    lon, sho = financing_spreads(rates['USD'].index, rates, ["CAD"])
    expected = DEBIT_SPREAD["CAD"] + CREDIT_SPREAD["USD"]
    assert sho["CAD"].iloc[0] == pytest.approx(expected)


def test_credit_is_floored_at_zero_when_the_rate_is_below_the_spread():
    """NZD publishes 0.000% credit: a 2.5% spread against a ~2.1% benchmark earns nothing."""
    rates = rates_for(["NZD"], level=0.02098, usd=0.03)
    lon, _ = financing_spreads(rates['USD'].index, rates, ["NZD"])
    # cost is the whole rate, not the nominal 2.5% spread
    assert lon["NZD"].iloc[0] == pytest.approx(0.02098 + DEBIT_SPREAD["USD"])
    assert lon["NZD"].iloc[0] < CREDIT_SPREAD["NZD"] + DEBIT_SPREAD["USD"]


def test_a_currency_paying_nothing_on_any_balance_costs_its_whole_rate():
    """ILS pays 0% on all balances — the limiting case of the same floor."""
    rates = rates_for(["ILS"], level=0.034, usd=0.03)
    lon, _ = financing_spreads(rates['USD'].index, rates, ["ILS"])
    assert lon["ILS"].iloc[0] == pytest.approx(0.034 + DEBIT_SPREAD["USD"])


def test_a_high_rate_currency_is_not_floored():
    rates = rates_for(["MXN"], level=0.0676, usd=0.03)
    lon, _ = financing_spreads(rates['USD'].index, rates, ["MXN"])
    assert lon["MXN"].iloc[0] == pytest.approx(CREDIT_SPREAD["MXN"] + DEBIT_SPREAD["USD"])


def test_a_negative_rate_currency_still_pays_to_borrow():
    """CHF borrows at BM + spread even though BM is negative."""
    rates = rates_for(["CHF"], level=-0.00254, usd=0.03)
    _, sho = financing_spreads(rates['USD'].index, rates, ["CHF"])
    assert sho["CHF"].iloc[0] > 0


def test_an_unknown_currency_raises_rather_than_charging_zero():
    rates = rates_for(["CAD"], level=0.05)
    rates["XYZ"] = rates["CAD"]
    with pytest.raises(KeyError, match="XYZ"):
        financing_spreads(rates['USD'].index, rates, ["CAD", "XYZ"])


# ---------------------------------------------------------------- Phase 3 (US1): the charge

def test_financing_is_charged_on_both_long_and_short():
    codes = ["CAD"]
    w_long = frame(codes, {"CAD": 0.5})
    w_short = frame(codes, {"CAD": -0.5})
    spot = frame(codes, {"CAD": 0.0})
    carry = frame(codes, {"CAD": 0.0})
    fin = financing_spreads(idx4(), rates_for(codes), codes)
    long_ret = simulate(w_long, spot, carry, cost_bps=0.0, financing=fin)
    short_ret = simulate(w_short, spot, carry, cost_bps=0.0, financing=fin)
    assert long_ret.iloc[-1] < 0
    assert short_ret.iloc[-1] < 0


def test_cost_is_absolute_weight_times_spread_over_252():
    codes = ["CAD"]
    w = frame(codes, {"CAD": 0.5})
    fin = financing_spreads(idx4(), rates_for(codes), codes)
    ret = simulate(w, frame(codes, {"CAD": 0.0}), frame(codes, {"CAD": 0.0}),
                   cost_bps=0.0, financing=fin)
    expected = -0.5 * fin[0]["CAD"].iloc[-1] / 252.0
    assert ret.iloc[-1] == pytest.approx(expected)


def test_a_bigger_position_costs_proportionally_more():
    codes = ["CAD"]
    fin = financing_spreads(idx4(), rates_for(codes), codes)
    spot, carry = frame(codes, {"CAD": 0.0}), frame(codes, {"CAD": 0.0})
    small = simulate(frame(codes, {"CAD": 0.25}), spot, carry, cost_bps=0.0, financing=fin)
    big = simulate(frame(codes, {"CAD": 0.5}), spot, carry, cost_bps=0.0, financing=fin)
    assert big.iloc[-1] == pytest.approx(2.0 * small.iloc[-1])


def test_a_zero_weight_costs_nothing():
    codes = ["CAD"]
    fin = financing_spreads(idx4(), rates_for(codes), codes)
    ret = simulate(frame(codes, {"CAD": 0.0}), frame(codes, {"CAD": 0.0}),
                   frame(codes, {"CAD": 0.0}), cost_bps=0.0, financing=fin)
    assert ret.iloc[-1] == pytest.approx(0.0)


def test_financing_off_reproduces_the_unfinanced_result_exactly():
    """FR-006: every prior result must remain reproducible."""
    codes = ["CAD", "MXN"]
    w = frame(codes, {"CAD": 0.5, "MXN": -0.5})
    spot = frame(codes, {"CAD": 0.001, "MXN": -0.002})
    carry = frame(codes, {"CAD": 0.02, "MXN": 0.07})
    before = simulate(w, spot, carry, cost_bps=1.0)
    after = simulate(w, spot, carry, cost_bps=1.0, financing=None)
    pd.testing.assert_series_equal(before, after)


def test_financing_never_improves_a_result():
    """SC-003, over a randomised book."""
    rng = np.random.default_rng(0)
    codes = ["CAD", "MXN", "NOK"]
    idx = pd.date_range("2026-01-01", periods=40, freq="D")
    w = pd.DataFrame(rng.normal(0, 0.3, (40, 3)), index=idx, columns=codes)
    spot = pd.DataFrame(rng.normal(0, 0.004, (40, 3)), index=idx, columns=codes)
    carry = pd.DataFrame(0.03, index=idx, columns=codes)
    rates = {c: pd.Series(0.05, index=idx) for c in codes}
    rates["USD"] = pd.Series(0.03, index=idx)
    fin = financing_spreads(idx4(), rates, codes)
    plain = simulate(w, spot, carry, cost_bps=1.0)
    financed = simulate(w, spot, carry, cost_bps=1.0, financing=fin)
    assert (financed <= plain + 1e-12).all()
    assert financed.sum() < plain.sum()


def test_financing_uses_the_lagged_weight_so_it_cannot_look_ahead():
    """The charge must follow the same shift(1) convention as the rest of the simulation."""
    codes = ["CAD"]
    idx = pd.date_range("2026-01-01", periods=3, freq="D")
    w = pd.DataFrame({"CAD": [0.0, 0.0, 1.0]}, index=idx)      # position only on the last day
    spot = pd.DataFrame({"CAD": [0.0, 0.0, 0.0]}, index=idx)
    carry = pd.DataFrame({"CAD": [0.0, 0.0, 0.0]}, index=idx)
    rates = {"CAD": pd.Series(0.05, index=idx), "USD": pd.Series(0.03, index=idx)}
    ret = simulate(w, spot, carry, cost_bps=0.0, financing=financing_spreads(idx4(), rates, codes))
    assert ret.iloc[-1] == pytest.approx(0.0)   # not yet held, so not yet charged


# ---------------------------------------------------------------- Phase 5 (US3): overridable

def test_an_overridden_schedule_changes_the_cost():
    codes = ["CAD"]
    rates = rates_for(codes)
    base_long, _ = financing_spreads(idx4(), rates, codes)
    wide_long, _ = financing_spreads(idx4(), rates, codes, credit_spread={**CREDIT_SPREAD, "CAD": 0.04})
    assert wide_long["CAD"].iloc[0] > base_long["CAD"].iloc[0]


def test_an_override_can_remove_the_cost_entirely():
    codes = ["CAD"]
    zero = {c: 0.0 for c in CREDIT_SPREAD}
    lon, sho = financing_spreads(idx4(), rates_for(codes), codes,
                                 credit_spread=zero, debit_spread=zero)
    assert lon["CAD"].iloc[0] == pytest.approx(0.0)
    assert sho["CAD"].iloc[0] == pytest.approx(0.0)
