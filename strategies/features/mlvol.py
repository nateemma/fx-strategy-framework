import numpy as np
import pandas as pd

class HARVolForecaster:
    """HAR-RV ridge forecaster of forward annualised realised volatility (log-vol space)."""
    WINDOWS = (5, 21, 63)

    def __init__(self):
        self.coef_ = None
        self.fitted = False

    def _features(self, returns: pd.Series) -> pd.DataFrame:
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        return pd.DataFrame(feats)

    def fit(self, returns: pd.Series, horizon: int = 21, alpha: float = 1.0) -> "HARVolForecaster":
        X = self._features(returns)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
        d = X.assign(_y=y).dropna()
        Xm = np.column_stack([np.ones(len(d)), d[X.columns].values])
        A = Xm.T @ Xm + alpha * np.eye(Xm.shape[1])
        self.coef_ = np.linalg.solve(A, Xm.T @ d["_y"].values)
        self.fitted = True
        return self

    def predict(self, returns: pd.Series) -> pd.Series:
        X = self._features(returns)
        Xm = np.column_stack([np.ones(len(X)), X.values])
        return pd.Series(np.exp(Xm @ self.coef_), index=X.index, name="vol_forecast")
