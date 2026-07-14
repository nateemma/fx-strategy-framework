import numpy as np
import pandas as pd

class GBMVolForecaster:
    """Gradient-boosted-tree forecaster of forward annualised realised volatility (log-vol space),
    a nonlinear counterpart to HARVolForecaster with the same fit/predict interface. Optionally learns
    the residual over an anchor (log-vol offset). Consistency contract: predict must receive `anchor`
    iff fit did (enforced); the anchor must cover the prediction index."""
    WINDOWS = (5, 10, 21, 42, 63)

    def __init__(self):
        self.model = None
        self.fitted = False
        self._anchored = False

    def _features(self, returns, exog=None):
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        X = pd.DataFrame(feats)
        if exog is not None:
            X = X.join(exog)
        return X

    def fit(self, returns, exog=None, anchor=None, horizon: int = 21, alpha: float = 1.0):
        from sklearn.ensemble import HistGradientBoostingRegressor
        X = self._features(returns, exog)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
        if anchor is not None:
            y = y - anchor
        d = X.assign(_y=y).dropna()
        self.model = HistGradientBoostingRegressor(
            random_state=0, max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
            min_samples_leaf=50, l2_regularization=1.0, early_stopping=True)
        self.model.fit(d[X.columns].values, d["_y"].values)
        self.fitted = True
        self._anchored = anchor is not None
        return self

    def predict(self, returns, exog=None, anchor=None):
        if (anchor is not None) != self._anchored:
            raise ValueError("predict must receive `anchor` iff fit did")
        X = self._features(returns, exog)
        valid = X.notna().all(axis=1)
        pred = pd.Series(np.nan, index=X.index, name="vol_forecast")
        if valid.any():
            p = self.model.predict(X[valid].values)
            if anchor is not None:
                p = p + anchor.reindex(X.index)[valid].values
            pred.loc[valid] = np.exp(p)
        return pred
