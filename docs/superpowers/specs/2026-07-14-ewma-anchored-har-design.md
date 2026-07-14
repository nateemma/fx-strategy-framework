# EWMA-Anchored HAR Vol Forecaster (v3) — Design Spec

*Design spec. Status: approved 2026-07-14. Follow-up to the cross-asset ML vol result (v2), where
`carry_voltarget_xasset` (macro-HAR) lost to a plain EWMA on walk-forward. That negative result has one
open weakness: the HAR model never saw EWMA, so "HAR loses to EWMA" could just mean "HAR is a worse
repackaging of the same trailing-r² information." This v3 nests EWMA inside the model as a fixed offset
so the model only has to learn the **residual** EWMA misses — converting the finding into the
critique-proof "even given EWMA for free, the HAR/macro features add no OOS edge."*

## Goal & success criteria
- The `HARVolForecaster` gains an optional **anchor** (a log-vol offset): the target becomes
  `log(fwd_rv) − anchor`, the prediction becomes `exp(Xβ + anchor)`. When `anchor=None` the forecaster
  is **byte-identical** to today (the v2 `carry_voltarget_ml` / `carry_voltarget_xasset` paths must not
  move).
- `MLVolTargetOverlay` gains a structural `anchor_ewma: bool = False` flag that supplies
  `log(EWMA(base_ret, lam))` as the anchor.
- A registered `carry_voltarget_xasset_anchored` variant (macro exog + EWMA anchor) for the A/B.
- **Ship gate (unchanged):** the anchored macro overlay becomes the preferred ML variant only if it
  **beats** EWMA OOS on walk-forward. Otherwise record the (now airtight) negative result; EWMA stays
  the default.

## What "anchoring" does — and what it does NOT claim
With `log(EWMA)` as a fixed-coefficient offset, the ridge only fits the *gap* between EWMA and forward
RV. This is a strictly easier, lower-variance learning problem than fitting the whole vol level. In the
limit of strong shrinkage the corrections go to zero and the model **reproduces EWMA exactly**, so EWMA
is the structural fallback. It does **not** guarantee beating EWMA out-of-sample at finite `alpha`:
if the fitted corrections are noise, they can still degrade OOS — which is precisely the empirical
question this variant answers. `alpha` stays at the family default `1.0` (parity with the other
variants); the offset structure, not a retuned `alpha`, is the intervention.

## Components

### 1. Forecaster anchor (`strategies/features/mlvol.py`)
`fit` and `predict` gain an optional `anchor` (a pandas Series on the returns index, already in log-vol
space):
```python
def fit(self, returns, exog=None, anchor=None, horizon=21, alpha=1.0):
    X = self._features(returns, exog)
    fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
    y = np.log(fwd.clip(lower=1e-8))
    if anchor is not None:
        y = y - anchor                      # aligns on index; NaN anchor rows drop in dropna()
    d = X.assign(_y=y).dropna()
    ...                                     # standardization + ridge solve unchanged

def predict(self, returns, exog=None, anchor=None):
    X = self._features(returns, exog)
    ...                                     # standardize if mean_ is not None
    pred = Xm @ self.coef_                  # log-residual if fitted with anchor, else log-level
    if anchor is not None:
        pred = pred + anchor.reindex(X.index).values
    return pd.Series(np.exp(pred), index=X.index, name="vol_forecast")
```
- **`anchor=None` → byte-identical to today** (no subtraction, no addition).
- **Consistency contract:** the caller MUST pass `anchor` to `predict` iff it passed `anchor` to `fit`.
  This is internal; the overlay guarantees it. Document in the docstring.

### 2. Overlay flag (`strategies/mloverlay.py`)
```python
def __init__(self, base, *, horizon=21, ridge_alpha=1.0, use_macro=False, anchor_ewma=False, **kw):
    super().__init__(base, **kw); ...; self.anchor_ewma = anchor_ewma

def _anchor(self, base_ret):
    if not self.anchor_ewma:
        return None
    return np.log(ewma_vol(base_ret, lam=self.lam).clip(lower=1e-8))

def fit(self, train):
    ...
    anchor = self._anchor(base_ret)
    self.forecaster.fit(base_ret, exog=exog, anchor=anchor, horizon=self.horizon, alpha=self.ridge_alpha)

def _vol_forecast(self, base_ret, view):
    exog = self._build_exog(view, base_ret.index) if self.use_macro else None
    anchor = self._anchor(base_ret)
    if not self.forecaster.fitted:
        self.forecaster.fit(base_ret, exog=exog, anchor=anchor, horizon=self.horizon, alpha=self.ridge_alpha)
    har = self.forecaster.predict(base_ret, exog=exog, anchor=anchor)
    return har.fillna(ewma_vol(base_ret, lam=self.lam))
```
- `anchor_ewma` is **structural** (defines the variant) → NOT in `params()`/`search_space()`, exactly
  like `use_macro`.
- The existing `ewma_vol` NaN fallback still applies (an exog gap → NaN forecast → EWMA), so the anchor
  path degrades gracefully just like v2.

### 3. Variant registration (`strategies/carry.py`)
Co-located with `CarryVolTargetXAsset`:
```python
class CarryVolTargetXAssetAnchored(MLVolTargetOverlay):
    NAME = "carry_voltarget_xasset_anchored"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), use_macro=True, anchor_ewma=True, **overlay)
```

### Causality
The anchor is `log(EWMA(base_ret))` — a trailing, causal transform of the same base returns already
used, and the exog is as-of ≤ each date as in v2. `fit` freezes coefficients; `predict` adds the
trailing anchor. `carry_voltarget_xasset_anchored` must pass `causal-check`.

## Testing (all offline, no network)
- **Forecaster `anchor=None` byte-identical:** fit/predict with `anchor=None` yields the same `coef_`
  and same `predict` output as a baseline fit (no regression to the v2 variants).
- **Forecaster anchored behavior:** with an `anchor` and a forward RV that equals the anchor on average
  (near-zero residual), the fitted corrections are small and `predict ≈ exp(anchor)`; with a non-trivial
  residual the prediction responds. Predict with anchor differs from predict without.
- **Overlay:** `carry_voltarget_xasset_anchored` builds via discovery with `use_macro=True` and
  `anchor_ewma=True`; `anchor_ewma` is absent from `params()`; `assert_causal` passes on a synthetic
  view carrying `macro`; an integration backtest is finite; the `anchor_ewma=False` path (existing
  `carry_voltarget_xasset`) is unchanged.
- Full suite green.

## Validation (post-merge)
Walk-forward `carry_voltarget` (EWMA) vs `carry_voltarget_xasset` (macro-HAR) vs
`carry_voltarget_xasset_anchored` (macro-HAR anchored to EWMA), `--timerange 1997-01-01:
--train-days 2520 --test-days 504`. Record: does anchoring let the macro features add OOS edge over
EWMA? If yes → new preferred ML variant. If no → the ML-vol-overlay track is exhausted, airtight
(EWMA beats macro-HAR *even when the macro-HAR is handed EWMA as a free offset*); EWMA stays default.

## Out of scope (YAGNI)
- A price-only anchored variant (`carry_voltarget_ml_anchored`) — a trivial follow-on if the macro
  variant is inconclusive, not built pre-emptively.
- Retuning `alpha` / the EWMA `lam` — the offset structure is the sole intervention under test.
- Applying the anchor to the blend overlay — first read the result on carry.
