import pytest

from forex.run.fxtrack import MIN_OBS_STATS, fx_observations, fx_performance


def history(days, nav=1_000_000.0, stock_positions=13):
    """Build snapshot rows. Each day is (date, net, gross, accrued) or a dict of overrides.

    A day whose net/gross/accrued are None produces a pre-2026-08-16 row with empty FX columns.
    """
    rows = []
    for d in days:
        if isinstance(d, dict):
            date, net, gross, accrued = d["date"], d.get("net"), d.get("gross"), d.get("accrued")
            sp, nv = d.get("stock_positions", stock_positions), d.get("nav", nav)
            stamp = d.get("stamp", f"{date}T04:00:00Z")
        else:
            date, net, gross, accrued = d
            sp, nv, stamp = stock_positions, nav, f"{date}T04:00:00Z"
        rows.append({
            "timestamp": stamp, "account": "DUQ218063", "nav": str(nv),
            "unrealized_pnl": "0.0", "realized_pnl": "0.0", "stock_positions": str(sp),
            "fx_legs": "" if net is None else "14",
            "fx_net_base": "" if net is None else str(net),
            "fx_gross_base": "" if gross is None else str(gross),
            "fx_accrued_base": "" if accrued is None else str(accrued),
        })
    return rows


def series(n, start_net=0.0, step=100.0, gross=1_000_000.0, accrued_step=0.0, first_day=1):
    """n consecutive August days, net trending by `step` per day with alternating overshoot.

    The overshoot lands on odd days only, so it cancels over any even number of steps: cumulative
    totals stay exactly `k * step` while daily returns still vary. A perfectly linear series would
    have zero variance and no defined Sharpe.
    """
    def net(i):
        return start_net + i * step + (step * 0.3 if i % 2 else 0.0)
    return [(f"2026-08-{first_day + i:02d}", net(i), gross, i * accrued_step) for i in range(n)]


# ---------------------------------------------------------------- Phase 2: loading + derivation

def test_rows_without_fx_columns_are_excluded():
    """Pre-2026-08-16 rows have empty FX columns and cannot be reconstructed."""
    rows = history([("2026-08-01", None, None, None),
                    ("2026-08-02", 100.0, 1_000_000.0, 0.0),
                    ("2026-08-03", 200.0, 1_000_000.0, 0.0)])
    perf = fx_performance(rows)
    assert perf.n_fx_days == 2
    assert perf.period_start == "2026-08-02"


def test_multiple_snapshots_in_a_day_collapse_to_the_last():
    rows = history([{"date": "2026-08-02", "net": 100.0, "gross": 1e6, "accrued": 0.0,
                     "stamp": "2026-08-02T04:00:00Z"},
                    {"date": "2026-08-02", "net": 175.0, "gross": 1e6, "accrued": 0.0,
                     "stamp": "2026-08-02T21:00:00Z"},
                    ("2026-08-03", 200.0, 1_000_000.0, 0.0)])
    perf = fx_performance(rows)
    assert perf.n_fx_days == 2
    assert perf.total_pnl == pytest.approx(25.0)   # 200 - 175, not 200 - 100


def test_rows_are_ordered_by_timestamp_not_file_order():
    rows = history([("2026-08-03", 200.0, 1e6, 0.0), ("2026-08-02", 100.0, 1e6, 0.0)])
    perf = fx_performance(rows)
    assert perf.period_start == "2026-08-02"
    assert perf.total_pnl == pytest.approx(100.0)


def test_observation_pnl_and_return_use_the_prior_gross():
    """Return divides by the gross at the START of the period, before this period's P&L moved it."""
    rows = history([("2026-08-02", 0.0, 1_000_000.0, 0.0),
                    ("2026-08-03", 500.0, 2_000_000.0, 0.0)])
    obs = fx_observations(rows)
    assert len(obs) == 1
    assert obs[0].pnl == pytest.approx(500.0)
    assert obs[0].ret == pytest.approx(500.0 / 1_000_000.0)


def test_spot_is_the_residual_so_components_always_sum():
    rows = history([("2026-08-02", 0.0, 1e6, 0.0), ("2026-08-03", 300.0, 1e6, -50.0)])
    o = fx_observations(rows)[0]
    assert o.carry_pnl == pytest.approx(-50.0)
    assert o.spot_pnl == pytest.approx(350.0)
    assert o.carry_pnl + o.spot_pnl == pytest.approx(o.pnl)


def test_first_fx_day_yields_no_observation():
    rows = history([("2026-08-02", 100.0, 1e6, 0.0)])
    assert fx_observations(rows) == []


# ---------------------------------------------------------------- Phase 3 (US1): headline stats

def test_full_statistics_once_the_sample_is_large_enough():
    perf = fx_performance(history(series(MIN_OBS_STATS + 5)))
    assert perf.sharpe is not None
    assert perf.ann_vol is not None
    assert perf.ann_return is not None
    assert perf.max_drawdown is not None
    assert perf.n_obs >= MIN_OBS_STATS


def test_total_return_is_on_gross_exposure():
    perf = fx_performance(history(series(25, step=100.0, gross=1_000_000.0)))
    assert perf.total_pnl == pytest.approx(2400.0)              # 24 steps of 100
    assert perf.total_return == pytest.approx(2400.0 / 1_000_000.0)


def test_a_steadily_losing_book_reports_negative_return_and_drawdown():
    perf = fx_performance(history(series(25, step=-100.0)))
    assert perf.total_pnl < 0
    assert perf.total_return < 0
    assert perf.max_drawdown < 0


def test_fx_figures_are_invariant_to_whole_account_nav():
    """SC-002: the ETF sleeves must not be able to move the FX numbers."""
    days = series(25)
    flat = fx_performance(history(days, nav=1_000_000.0))
    surged = fx_performance(history(days, nav=1_200_000.0))
    assert flat == surged


# ---------------------------------------------------------------- Phase 4 (US2): carry vs spot

def test_carry_and_spot_reconcile_with_the_total():
    perf = fx_performance(history(series(25, step=100.0, accrued_step=-30.0)))
    assert perf.carry_pnl + perf.spot_pnl == pytest.approx(perf.total_pnl)


def test_negative_carry_is_reported_not_netted_away():
    """The live book accrues negative carry while spot gains — both must be visible."""
    perf = fx_performance(history(series(25, step=100.0, accrued_step=-30.0)))
    assert perf.carry_pnl < 0
    assert perf.spot_pnl > 0
    assert perf.total_pnl > 0


# ---------------------------------------------------------------- Phase 5 (US3): trust

def test_rebalance_days_are_detected_from_unsettled_trade_counts():
    """The real 2026-08-12 pattern: 7 orders placed, stock_positions 13 -> 20 -> 20 -> 13 at T+2."""
    days = [{"date": f"2026-08-{d:02d}", "net": float(d), "gross": 1e6, "accrued": 0.0,
             "stock_positions": 20 if d in (12, 13) else 13} for d in range(1, 26)]
    obs = fx_observations(history(days))
    flagged = {o.date for o in obs if o.contaminated}
    assert "2026-08-12" in flagged and "2026-08-13" in flagged
    assert "2026-08-14" in flagged            # the move spanning settlement
    assert "2026-08-20" not in flagged        # a quiet day is untouched


def test_a_rotation_that_leaves_leg_count_unchanged_is_still_detected():
    """The 2026-08-12 rebalance resized 7 existing legs; fx_legs would not have moved."""
    days = [{"date": f"2026-08-{d:02d}", "net": float(d), "gross": 1e6, "accrued": 0.0,
             "stock_positions": 18 if d == 10 else 13} for d in range(1, 26)]
    obs = fx_observations(history(days))
    assert any(o.contaminated for o in obs)


def test_contaminated_observations_are_excluded_and_counted():
    days = [{"date": f"2026-08-{d:02d}", "net": float(d), "gross": 1e6, "accrued": 0.0,
             "stock_positions": 20 if d in (12, 13) else 13} for d in range(1, 26)]
    perf = fx_performance(history(days))
    assert perf.n_excluded > 0
    assert perf.n_obs == len(fx_observations(history(days))) - perf.n_excluded


def test_cumulative_pnl_still_spans_the_whole_period_despite_exclusions():
    """Exclusions drop observations from ratios; endpoints are levels and must not be clipped."""
    days = [{"date": f"2026-08-{d:02d}", "net": float(d) * 10, "gross": 1e6, "accrued": 0.0,
             "stock_positions": 20 if d in (12, 13) else 13} for d in range(1, 26)]
    perf = fx_performance(history(days))
    assert perf.total_pnl == pytest.approx(240.0)   # (25*10) - (1*10)


def test_one_observation_gives_levels_but_no_pnl():
    perf = fx_performance(history([("2026-08-16", 129.0, 996_532.0, -841.0)]))
    assert perf.n_fx_days == 1
    assert perf.net_base == pytest.approx(129.0)
    assert perf.gross_base == pytest.approx(996_532.0)
    assert perf.accrued_base == pytest.approx(-841.0)
    assert perf.total_pnl is None
    assert perf.sharpe is None


def test_small_sample_gives_pnl_but_withholds_ratios():
    perf = fx_performance(history(series(4)))
    assert perf.total_pnl is not None
    assert perf.carry_pnl is not None
    assert perf.sharpe is None
    assert perf.ann_vol is None
    assert perf.ann_return is None
    assert perf.max_drawdown is None


def test_withheld_statistics_are_none_never_nan_or_zero():
    """C-07: a suppressed statistic must be absent, not a misleading stand-in."""
    perf = fx_performance(history(series(4)))
    for value in (perf.sharpe, perf.ann_vol, perf.ann_return, perf.max_drawdown):
        assert value is None


def test_history_with_no_fx_columns_at_all_is_reported_as_unavailable():
    """C-08: legacy histories must not error."""
    perf = fx_performance(history([("2026-08-01", None, None, None),
                                   ("2026-08-02", None, None, None)]))
    assert perf.n_fx_days == 0
    assert perf.period_start is None
    assert perf.total_pnl is None
    assert perf.sharpe is None


def test_empty_history_is_reported_as_unavailable():
    perf = fx_performance([])
    assert perf.n_fx_days == 0
    assert perf.sharpe is None


# ---------------------------------------------------------------- Phase 6: guards

def test_zero_gross_exposure_does_not_divide():
    """A fully-closed book must not produce an infinite return."""
    rows = history([("2026-08-02", 100.0, 0.0, 0.0), ("2026-08-03", 100.0, 1e6, 0.0)])
    obs = fx_observations(rows)
    assert obs[0].ret is None


def test_a_closed_book_day_is_not_treated_as_missing_data():
    rows = history([("2026-08-02", 100.0, 1e6, 0.0), ("2026-08-03", 100.0, 0.0, 0.0)])
    perf = fx_performance(rows)
    assert perf.n_fx_days == 2
    assert perf.gross_base == pytest.approx(0.0)


def test_a_multi_day_gap_is_excluded_from_ratio_statistics():
    """A week of missed snapshots must not be annualised as if it were one day."""
    days = [("2026-08-01", 0.0, 1e6, 0.0),
            ("2026-08-02", 100.0, 1e6, 0.0),
            ("2026-08-12", 900.0, 1e6, 0.0),   # 10-day hole in the curve
            ("2026-08-13", 950.0, 1e6, 0.0)]
    obs = fx_observations(history(days))
    gapped = [o for o in obs if o.date == "2026-08-12"]
    assert len(gapped) == 1, "the gapped move must still produce an observation"
    assert gapped[0].gap_days == 10
    assert gapped[0].excluded_gap is True
    assert [o.excluded_gap for o in obs] == [False, True, False]


def test_gapped_observations_do_not_reach_the_statistics():
    """The gapped move is counted as excluded, not silently absorbed."""
    days = [(f"2026-08-{d:02d}", float(d) * 50 + (10 if d % 2 else 0), 1e6, 0.0)
            for d in range(1, 26) if d != 10]           # a 2-day step, still fine
    long_gap = [("2026-09-15", 5000.0, 1e6, 0.0)]       # 20-day hole at the end
    perf = fx_performance(history(days + long_gap))
    assert perf.n_excluded >= 1
    assert perf.total_pnl is not None                    # endpoints are levels, never clipped


def test_weekend_gap_is_not_excluded():
    """Fri -> Mon is a 3-day gap and is perfectly normal."""
    rows = history([("2026-08-07", 0.0, 1e6, 0.0), ("2026-08-10", 100.0, 1e6, 0.0)])
    obs = fx_observations(rows)
    assert obs[0].gap_days == 3
    assert not obs[0].excluded_gap
