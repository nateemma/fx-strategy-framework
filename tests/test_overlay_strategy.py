import numpy as np, pandas as pd
from forex.core.dataview import DataView
from strategies.carry import CarryStrategy
from strategies.overlay import VolTargetOverlay

def _view():
    idx = pd.date_range("2019-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_overlay_scales_base_weights_within_cap_and_preserves_zeros():
    v = _view()
    base = CarryStrategy(1, 1)
    bw = base.target_weights(v)
    ow = VolTargetOverlay(base, target_vol=0.10, cap=1.5, cadence="D").target_weights(v)
    assert ow.index.equals(bw.index) and list(ow.columns) == list(bw.columns)
    # leverage never exceeds cap: |overlay| <= cap*|base| everywhere
    assert (ow.abs() <= 1.5 * bw.abs() + 1e-9).all().all()
    # zero base weight -> zero overlay weight
    assert (ow[bw == 0].fillna(0.0) == 0.0).all().all()

def test_vol_forecast_defaults_to_ewma():
    from strategies.overlay import VolTargetOverlay
    from strategies.carry import CarryStrategy
    from forex.features.volforecast import ewma_vol
    idx = pd.date_range("2019-01-01", periods=300, freq="B")
    base_ret = pd.Series(np.random.RandomState(1).normal(0, 0.01, 300), index=idx)
    ov = VolTargetOverlay(CarryStrategy(1, 1), lam=0.94)
    assert (ov._vol_forecast(base_ret) == ewma_vol(base_ret, lam=0.94)).all()
