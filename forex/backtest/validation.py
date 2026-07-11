import pandas as pd

def walk_forward(index: pd.DatetimeIndex, train_days: int,
                 test_days: int) -> list[tuple[slice, slice]]:
    idx = pd.DatetimeIndex(index).sort_values()
    folds, start = [], 0
    while start + train_days + test_days <= len(idx):
        tr = slice(start, start + train_days)
        te = slice(start + train_days, start + train_days + test_days)
        folds.append((tr, te))
        start += test_days
    return folds

def distant_window(index: pd.DatetimeIndex,
                   holdout_years: int = 3) -> tuple[slice, slice]:
    idx = pd.DatetimeIndex(index).sort_values()
    cutoff = idx.min() + pd.DateOffset(years=holdout_years)
    n_distant = int((idx < cutoff).sum())
    distant = slice(0, n_distant)
    recent = slice(n_distant, len(idx))
    return recent, distant
