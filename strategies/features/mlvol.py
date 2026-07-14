import numpy as np
import pandas as pd

class HARVolForecaster:
    """HAR-RV ridge forecaster of forward annualised realised volatility (log-vol space).
    Optionally accepts exogenous features; standardizes the feature matrix when exog is present.
    Consistency contract: predict must receive `anchor` iff fit did (enforced), and the anchor must
    cover the full prediction index (an uncovered date yields a NaN forecast, which the overlay's EWMA
    fallback then fills)."""
    WINDOWS = (5, 21, 63)

    def __init__(self):
        self.coef_ = None
        self.fitted = False
        self.mean_ = None
        self.std_ = None
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
        X = self._features(returns, exog)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
        if anchor is not None:
            y = y - anchor
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
        self._anchored = anchor is not None
        return self

    def predict(self, returns, exog=None, anchor=None):
        if (anchor is not None) != self._anchored:
            raise ValueError("predict must receive `anchor` iff fit did")
        X = self._features(returns, exog)
        Xv = X.values
        if self.mean_ is not None:
            Xv = (Xv - self.mean_) / self.std_
        Xm = np.column_stack([np.ones(len(X)), Xv])
        pred = Xm @ self.coef_
        if anchor is not None:
            pred = pred + anchor.reindex(X.index).values
        return pd.Series(np.exp(pred), index=X.index, name="vol_forecast")
