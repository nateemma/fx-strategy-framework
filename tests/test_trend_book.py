import numpy as np
import pandas as pd
import pytest

from strategies.trend_book import (
    LOOKBACKS,
    MIN_HISTORY,
    UNIVERSE,
    ensemble_signal,
    risk_parity_weights,
    target_contracts,
    trend_targets,
)


def ramp(n=600, slope=0.0005, vol=0.01, seed=0, start=100.0):
    """A price path with a controllable drift, so the trend sign is known."""
    rng = np.random.default_rng(seed)
    steps = slope + rng.normal(0, vol, n)
    return pd.Series(start * np.exp(np.cumsum(steps)),
                     index=pd.bdate_range("2023-01-02", periods=n))


def frame(**series):
    return pd.DataFrame(series)


# ---------------------------------------------------------------- the universe

def test_universe_is_the_eight_granularity_feasible_markets():
    assert len(UNIVERSE) == 8


def test_every_market_declares_what_it_needs_to_be_traded_and_validated():
    for m in UNIVERSE:
        assert m.symbol and m.exchange and m.multiplier > 0
        assert m.proxy, f"{m.symbol} has no ETF proxy — the gate evidence would be untraceable"
        assert m.note, f"{m.symbol} has no proxy-fidelity note"


def test_the_universe_spans_all_four_asset_classes():
    """The gate's edge came from diversification across sleeves, not from any one market."""
    assert {m.sleeve for m in UNIVERSE} == {"equity", "bond", "fx", "commodity"}


def test_no_duplicate_symbols():
    syms = [m.symbol for m in UNIVERSE]
    assert len(syms) == len(set(syms))


# ---------------------------------------------------------------- signal

def test_signal_is_positive_for_a_rising_market_and_negative_for_a_falling_one():
    px = frame(UP=ramp(slope=0.001), DOWN=ramp(slope=-0.001, seed=1))
    sig = ensemble_signal(px)
    assert sig["UP"].iloc[-1] > 0
    assert sig["DOWN"].iloc[-1] < 0


def test_signal_is_bounded_by_one():
    px = frame(A=ramp(slope=0.002), B=ramp(slope=-0.002, seed=2), C=ramp(slope=0.0, seed=3))
    assert ensemble_signal(px).abs().max().max() <= 1.0 + 1e-12


def test_signal_averages_the_lookbacks_so_disagreement_gives_a_partial_position():
    """A market up over 63d but down over 252d must not read as full conviction."""
    n = 400
    idx = pd.bdate_range("2023-01-02", periods=n)
    path = np.concatenate([np.linspace(100, 60, n - 100), np.linspace(60, 75, 100)])
    px = frame(MIXED=pd.Series(path, index=idx))
    s = ensemble_signal(px)["MIXED"].iloc[-1]
    assert -1.0 < s < 1.0, f"expected disagreement, got full conviction {s}"


def test_signal_uses_the_configured_lookbacks():
    assert LOOKBACKS == (63, 126, 252)


# ---------------------------------------------------------------- weights

def test_weights_are_signed_and_sum_to_one_in_absolute_value():
    px = frame(A=ramp(slope=0.001), B=ramp(slope=-0.001, seed=4), C=ramp(slope=0.001, seed=5))
    w = risk_parity_weights(ensemble_signal(px), px).iloc[-1]
    assert w.abs().sum() == pytest.approx(1.0)
    assert (w != 0).any()


def test_a_calmer_market_gets_a_larger_weight():
    """Inverse-vol: the same signal in a quieter market earns more of the risk budget."""
    px = frame(CALM=ramp(slope=0.001, vol=0.004, seed=6),
               WILD=ramp(slope=0.001, vol=0.02, seed=7))
    w = risk_parity_weights(ensemble_signal(px), px).iloc[-1]
    assert abs(w["CALM"]) > abs(w["WILD"])


def test_a_flat_market_earns_no_weight():
    px = frame(TREND=ramp(slope=0.002), FLAT=pd.Series(100.0, index=ramp().index))
    w = risk_parity_weights(ensemble_signal(px), px).iloc[-1]
    assert w["FLAT"] == pytest.approx(0.0)


# ---------------------------------------------------------------- causality (Constitution II)

def test_weights_on_a_date_do_not_change_when_later_data_is_removed():
    """Truncation invariance: the same discipline the framework enforces on every strategy."""
    px = frame(A=ramp(slope=0.001), B=ramp(slope=-0.001, seed=8), C=ramp(slope=0.0005, seed=9))
    asof = px.index[-60]
    full = risk_parity_weights(ensemble_signal(px), px).loc[asof]
    trunc = risk_parity_weights(ensemble_signal(px.loc[:asof]), px.loc[:asof]).loc[asof]
    pd.testing.assert_series_equal(full, trunc)


# ---------------------------------------------------------------- contracts + rounding

def test_targets_are_whole_contracts():
    targets, _ = target_contracts({"A": 0.5, "B": -0.5}, leverage=2.0, risk_base=200_000,
                                  prices={"A": 100.0, "B": 50.0},
                                  multipliers={"A": 5.0, "B": 1000.0})
    assert all(isinstance(v, int) for v in targets.values())


def test_target_sign_follows_the_weight():
    targets, _ = target_contracts({"LONG": 0.5, "SHORT": -0.5}, 2.0, 200_000,
                                  {"LONG": 100.0, "SHORT": 100.0},
                                  {"LONG": 5.0, "SHORT": 5.0})
    assert targets["LONG"] > 0 and targets["SHORT"] < 0


def test_rounding_error_is_reported_for_every_market():
    targets, rounding = target_contracts({"A": 0.5, "B": -0.5}, 2.0, 200_000,
                                         {"A": 100.0, "B": 50.0}, {"A": 5.0, "B": 1000.0})
    assert set(rounding) == set(targets)
    for m, err in rounding.items():
        assert 0.0 <= err <= 0.5 + 1e-9, f"{m} rounding error {err} out of range"


def test_a_market_too_small_to_round_to_one_contract_is_reported_not_hidden():
    """At this sleeve size some markets genuinely round to zero. That must be visible."""
    targets, rounding = target_contracts({"TINY": 1.0}, leverage=1.0, risk_base=1_000,
                                         prices={"TINY": 5_000.0}, multipliers={"TINY": 1_000.0})
    assert targets["TINY"] == 0
    assert "TINY" in rounding


def test_bigger_risk_base_gives_proportionally_more_contracts():
    small, _ = target_contracts({"A": 1.0}, 1.0, 200_000, {"A": 100.0}, {"A": 5.0})
    big, _ = target_contracts({"A": 1.0}, 1.0, 800_000, {"A": 100.0}, {"A": 5.0})
    assert big["A"] == pytest.approx(4 * small["A"], rel=0.02)


# ---------------------------------------------------------------- refuse rather than degrade

def test_insufficient_history_raises_rather_than_producing_a_degraded_signal():
    """Without a market-data subscription IBKR returns a handful of bars. Trading on that is worse
    than not trading, so it must fail loudly."""
    px = frame(A=ramp(n=30), B=ramp(n=30, seed=10))
    with pytest.raises(ValueError, match="history"):
        trend_targets(px, {"A": 5.0, "B": 5.0}, risk_base=200_000)


def test_the_minimum_history_covers_the_longest_lookback_plus_the_vol_window():
    assert MIN_HISTORY >= max(LOOKBACKS)


def test_a_full_pipeline_run_produces_targets_and_diagnostics():
    px = frame(**{m.symbol: ramp(slope=0.0008, seed=i) for i, m in enumerate(UNIVERSE)})
    mults = {m.symbol: m.multiplier for m in UNIVERSE}
    targets, diag = trend_targets(px, mults, risk_base=200_000)
    assert set(targets) == set(mults)
    for key in ("leverage", "weights", "rounding", "gross_notional"):
        assert key in diag, f"diagnostic {key!r} missing"
    assert diag["leverage"] > 0
