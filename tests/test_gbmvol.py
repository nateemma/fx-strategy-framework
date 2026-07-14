import numpy as np, pandas as pd, pytest
from strategies.features.gbmvol import GBMVolForecaster

def _regime_returns():
    idx = pd.date_range("2010-01-01", periods=1200, freq="B")
    rng = np.random.RandomState(0)
    r = np.concatenate([rng.normal(0, 0.003, 600), rng.normal(0, 0.02, 600)])  # low then high vol
    return pd.Series(r, index=idx)

def test_gbm_fits_and_tracks_vol_regime():
    r = _regime_returns()
    f = GBMVolForecaster().fit(r, horizon=21)
    assert f.fitted
    pred = f.predict(r)
    assert pred.iloc[700:].notna().all()
    assert pred.iloc[750:].mean() > pred.iloc[100:400].mean()   # higher forecast in high-vol regime

def test_gbm_predict_is_deterministic():
    r = _regime_returns()
    f = GBMVolForecaster().fit(r)
    assert (f.predict(r).dropna() == f.predict(r).dropna()).all()

def test_gbm_anchor_changes_forecast_and_enforces_contract():
    r = _regime_returns()
    anchor = pd.Series(np.log(0.12), index=r.index)
    fa = GBMVolForecaster().fit(r, anchor=anchor)
    with pytest.raises(ValueError):
        fa.predict(r)                                           # fit anchored, predict not
    fp = GBMVolForecaster().fit(r)
    with pytest.raises(ValueError):
        fp.predict(r, anchor=anchor)                           # fit plain, predict anchored
    assert not fa.predict(r, anchor=anchor).dropna().equals(fp.predict(r).dropna())
