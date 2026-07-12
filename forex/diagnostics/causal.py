import pandas as pd

def assert_causal(strategy, view, sample_dates) -> None:
    """Truncation-invariance: weights at t on the full view must equal weights at t
    on the view truncated at t. Any difference is lookahead."""
    full = strategy.target_weights(view)
    bad = []
    for t in pd.DatetimeIndex(sample_dates):
        trunc = strategy.target_weights(view.truncate(t))
        if t not in trunc.index or t not in full.index:
            bad.append((t, "missing"))
            continue
        a = full.loc[t].reindex(sorted(full.columns)).fillna(0.0)
        b = trunc.loc[t].reindex(sorted(full.columns)).fillna(0.0)
        if not (a.round(10) == b.round(10)).all():
            bad.append((t, "differs"))
    if bad:
        raise AssertionError(f"lookahead detected at {bad}")
