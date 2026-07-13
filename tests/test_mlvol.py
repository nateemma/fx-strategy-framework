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
