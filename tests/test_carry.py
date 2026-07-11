import numpy as np, pandas as pd
from forex.features.carry import carry_signal, basket_weights

def test_carry_is_differential_vs_usd():
    cal = pd.to_datetime(["2020-06-01"])
    rates = {
        "USD": pd.Series([0.01], index=pd.to_datetime(["2020-06-01"]), name="USD"),
        "AUD": pd.Series([0.05], index=pd.to_datetime(["2020-06-01"]), name="AUD"),
    }
    sig = carry_signal(cal, rates)
    assert round(sig.loc["2020-06-01", "AUD"], 4) == 0.04  # 5% - 1%

def test_basket_weights_are_dollar_neutral():
    sig = pd.DataFrame(
        {"A": [0.05], "B": [0.04], "C": [0.03], "D": [-0.01], "E": [-0.02]},
        index=pd.to_datetime(["2020-06-01"]),
    )
    w = basket_weights(sig, n_long=2, n_short=2)
    row = w.loc["2020-06-01"]
    assert row["A"] == 0.5 and row["B"] == 0.5      # top-2 long
    assert row["D"] == -0.5 and row["E"] == -0.5    # bottom-2 short
    assert row["C"] == 0.0                          # middle excluded
    assert abs(row.sum()) < 1e-9                    # dollar-neutral
