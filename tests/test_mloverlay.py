import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.space import Int
from strategies.carry import CarryStrategy
from strategies.mloverlay import MLVolTargetOverlay
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2016-01-01", periods=700, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,700), "EUR": 1.1+np.zeros(700),
                         "SEK": 1.0+np.linspace(0,-0.1,700)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_fit_sets_forecaster_and_weights_preserve_shape_and_zeros():
    v = _view()
    base = CarryStrategy(1, 1)
    bw = base.target_weights(v)
    ov = MLVolTargetOverlay(base, target_vol=0.10, cap=1.5, cadence="D")
    ov.fit(v)
    assert ov.forecaster.fitted
    ow = ov.target_weights(v)
    assert ow.index.equals(bw.index) and list(ow.columns) == list(bw.columns)
    assert (ow.abs() <= 1.5 * bw.abs() + 1e-9).all().all()          # never exceeds cap
    assert (ow[bw == 0].fillna(0.0) == 0.0).all().all()             # zeros preserved

def test_target_weights_self_fits_without_prior_fit():
    v = _view()
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), target_vol=0.10, cap=1.5, cadence="D")
    ow = ov.target_weights(v)                                        # no fit() called
    assert ov.forecaster.fitted                                      # self-fit happened
    assert np.isfinite(ow.dropna(how="all").to_numpy()).all()

def test_params_and_search_space():
    ov = MLVolTargetOverlay(CarryStrategy(3, 3), horizon=21, ridge_alpha=1.0)
    p = ov.params()
    assert p["horizon"] == 21 and p["ridge_alpha"] == 1.0 and "target_vol" in p
    assert ov.search_space()["horizon"] == Int(10, 42)

def test_ml_overlay_is_causal():
    v = _view()
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), cadence="D")
    ov.fit(v)                                     # fix coefficients; predict must be truncation-invariant
    assert_causal(ov, v, v.calendar[[30, 200, 400, 699]])

def test_backtest_produces_finite_result():
    r = backtest(MLVolTargetOverlay(CarryStrategy(1, 1), cadence="D"), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])

def test_walk_forward_oos_is_finite():
    from forex.run.walkforward import walk_forward
    v = _view()
    r = walk_forward(lambda: MLVolTargetOverlay(CarryStrategy(1, 1), cadence="D"),
                     v, train_days=252, test_days=126, cost_bps=1.0)
    assert len(r.returns) > 0
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])
