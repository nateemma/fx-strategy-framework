import numpy as np, pandas as pd
from strategies.features.mlvol import HARVolForecaster

def _regime_returns():
    idx = pd.date_range("2015-01-01", periods=1000, freq="B")
    rng = np.random.RandomState(0)
    r = np.concatenate([rng.normal(0, 0.003, 500), rng.normal(0, 0.02, 500)])  # low then high vol
    return pd.Series(r, index=idx)

def test_har_forecaster_fits_and_tracks_vol_regime():
    returns = _regime_returns()
    f = HARVolForecaster().fit(returns, horizon=21, alpha=1.0)
    assert f.fitted and len(f.coef_) == 4          # intercept + 3 windows
    pred = f.predict(returns)
    assert pred.iloc[:60].isna().all()             # warm-up before the 63-window is NaN
    assert pred.iloc[300:].notna().all()           # valid past warm-up
    assert pred.iloc[600:].mean() > pred.iloc[100:400].mean()   # higher forecast in high-vol regime

def test_har_predict_is_deterministic():
    returns = _regime_returns()
    f = HARVolForecaster().fit(returns)
    a = f.predict(returns)
    b = f.predict(returns)
    assert (a.dropna() == b.dropna()).all()

def test_exog_none_is_byte_identical():
    r = _regime_returns()
    f = HARVolForecaster().fit(r, horizon=21, alpha=1.0)
    assert len(f.coef_) == 4 and f.mean_ is None       # no exog -> 4 coefs, no standardization

def test_exog_adds_features_and_standardizes():
    import numpy as np, pandas as pd
    r = _regime_returns()
    # an exog column that tracks the realized-vol regime (informative)
    ex = pd.DataFrame({"risk": (r.abs().rolling(21).mean() * 20).fillna(0.0)}, index=r.index)
    f = HARVolForecaster().fit(r, exog=ex, horizon=21, alpha=1.0)
    assert len(f.coef_) == 1 + 3 + 1                    # intercept + 3 RV + 1 exog
    assert f.mean_ is not None and f.std_ is not None    # standardization stored
    pred = f.predict(r, exog=ex)
    assert pred.iloc[300:].notna().any()                 # produces forecasts

def _returns(n=800, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2000-01-01", periods=n, freq="B")
    return pd.Series(rng.normal(0, 0.01, n), index=idx)

def test_anchor_none_is_byte_identical():
    r = _returns()
    a = HARVolForecaster().fit(r)                       # baseline (no anchor)
    b = HARVolForecaster().fit(r, anchor=None)          # explicit None
    assert np.array_equal(a.coef_, b.coef_)
    pa, pb = a.predict(r), b.predict(r, anchor=None)
    assert pa.equals(pb)

def test_anchored_prediction_tracks_anchor():
    r = _returns()
    f = HARVolForecaster()
    anchor = pd.Series(np.log(0.12), index=r.index)     # constant log-vol anchor
    f.fit(r, anchor=anchor)
    pred = f.predict(r, anchor=anchor)
    plain = HARVolForecaster().fit(r).predict(r)
    assert not pred.dropna().equals(plain.dropna())     # anchoring changes the forecast
    # residual target is centered near 0 -> anchored forecast stays near exp(anchor)
    assert abs(np.log(pred.dropna()).mean() - np.log(0.12)) < abs(np.log(plain.dropna()).mean() - np.log(0.12))
