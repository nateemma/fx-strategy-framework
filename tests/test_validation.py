import pandas as pd
from forex.backtest.validation import walk_forward, distant_window

def test_walk_forward_pairs_are_disjoint_and_ordered():
    idx = pd.date_range("2015-01-01", periods=1000, freq="B")
    folds = walk_forward(idx, train_days=250, test_days=125)
    assert len(folds) >= 2
    tr, te = folds[0]
    assert idx[tr].max() < idx[te].min()          # train strictly before test
    assert idx[te].min() < idx[walk_forward(idx,250,125)[1][1]].min()  # test rolls forward

def test_distant_window_takes_earliest_years():
    idx = pd.date_range("2010-01-01", "2020-12-31", freq="B")
    recent, distant = distant_window(idx, holdout_years=3)
    assert idx[distant].min() == idx.min()
    assert idx[distant].max() < idx[recent].min()  # distant is strictly earlier
    assert (idx[distant].max() - idx[distant].min()).days <= 3 * 366
