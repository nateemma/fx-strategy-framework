import pandas as pd
from forex.data.store import asof_join

def test_asof_respects_publication_lag():
    # value for 2020-01-31 is only *released* 5 days later (2020-02-05)
    s = pd.Series([1.0, 2.0],
                  index=pd.to_datetime(["2020-01-31", "2020-02-29"]), name="rate")
    cal = pd.to_datetime(["2020-02-03", "2020-02-06", "2020-03-10"])
    out = asof_join(cal, s, pub_lag_days=5)
    # 2020-02-03: Jan value not released until 02-05 -> NaN (nothing available yet)
    # 2020-02-06: Jan value now visible -> 1.0
    # 2020-03-10: Feb value (released 03-05) visible -> 2.0
    assert pd.isna(out.loc["2020-02-03"])
    assert out.loc["2020-02-06"] == 1.0
    assert out.loc["2020-03-10"] == 2.0

def test_zero_lag_is_same_day():
    s = pd.Series([5.0], index=pd.to_datetime(["2020-01-02"]), name="fx")
    cal = pd.to_datetime(["2020-01-02", "2020-01-03"])
    out = asof_join(cal, s, pub_lag_days=0)
    assert out.loc["2020-01-02"] == 5.0
