import numpy as np
import pandas as pd

class HARVolForecaster:
    """HAR-RV ridge forecaster of forward annualised realised volatility (log-vol space).
    Optionally accepts exogenous features; standardizes the feature matrix when exog is present."""
    WINDOWS = (5, 21, 63)

    def __init__(self):
        self.coef_ = None
        self.fitted = False
        self.mean_ = None
        self.std_ = None

    def _features(self, returns, exog=None):
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        X = pd.DataFrame(feats)
        if exog is not None:
            X = X.join(exog)
        return X

    def fit(self, returns, exog=None, horizon: int = 21, alpha: float = 1.0):
        X = self._features(returns, exog)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
        d = X.assign(_y=y).dropna()
        Xv = d[X.columns].values
        if exog is not None:
            self.mean_ = Xv.mean(axis=0)
            self.std_ = Xv.std(axis=0)
            self.std_[self.std_ == 0] = 1.0
            Xv = (Xv - self.mean_) / self.std_
        else:
            self.mean_ = self.std_ = None
        Xm = np.column_stack([np.ones(len(d)), Xv])
        A = Xm.T @ Xm + alpha * np.eye(Xm.shape[1])
        self.coef_ = np.linalg.solve(A, Xm.T @ d["_y"].values)
        self.fitted = True
        return self

    def predict(self, returns, exog=None):
        X = self._features(returns, exog)
        Xv = X.values
        if self.mean_ is not None:
            Xv = (Xv - self.mean_) / self.std_
        Xm = np.column_stack([np.ones(len(X)), Xv])
        return pd.Series(np.exp(Xm @ self.coef_), index=X.index, name="vol_forecast")
