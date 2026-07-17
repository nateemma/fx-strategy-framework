import math
import pandas as pd
import pytest
from forex.run.basket_weights import inverse_vol_weights, target_shares


class TestInverseVolWeights:
    """inverse_vol_weights: higher-vol symbol gets lower weight than lower-vol symbol."""

    def test_simple_two_symbols_vol_difference(self):
        """Higher-vol symbol gets lower weight."""
        # Create 65 days: sym1 constant (vol=0), sym2 oscillates (high vol)
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = pd.DataFrame({
            "sym1": [100.0] * 65,
            "sym2": [100.0 + 5.0 * math.sin(i / 5.0) for i in range(65)],
        }, index=dates)

        weights = inverse_vol_weights(prices, lookback=60)

        # sym1 should be dropped (zero vol), sym2 gets all weight (or equal weights if all drop)
        # Actually, if sym1 has zero vol it gets dropped, so only sym2 remains
        assert abs(weights["sym2"] - 1.0) < 1e-9
        assert "sym1" not in weights.index

    def test_two_symbols_comparable_vols(self):
        """Two symbols with different but nonzero volatilities."""
        # sym1: small swings, sym2: large swings
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = pd.DataFrame({
            "sym1": [100.0 + 0.5 * math.sin(i / 5.0) for i in range(65)],
            "sym2": [100.0 + 5.0 * math.sin(i / 5.0) for i in range(65)],
        }, index=dates)

        weights = inverse_vol_weights(prices, lookback=60)

        # Lower-vol sym1 should have higher weight than higher-vol sym2
        assert weights["sym1"] > weights["sym2"]
        assert abs(weights.sum() - 1.0) < 1e-9
        assert len(weights) == 2

    def test_weights_sum_to_one(self):
        """Weights must sum to 1.0."""
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = pd.DataFrame({
            "a": [100.0 + 2.0 * math.sin(i / 3.0) for i in range(65)],
            "b": [100.0 + 1.0 * math.sin(i / 4.0) for i in range(65)],
            "c": [100.0 + 0.5 * math.sin(i / 5.0) for i in range(65)],
        }, index=dates)

        weights = inverse_vol_weights(prices, lookback=60)
        assert abs(weights.sum() - 1.0) < 1e-9

    def test_zero_vol_symbol_dropped(self):
        """Zero-volatility (constant price) symbol is dropped."""
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = pd.DataFrame({
            "constant": [100.0] * 65,
            "volatile": [100.0 + 5.0 * math.sin(i / 3.0) for i in range(65)],
        }, index=dates)

        weights = inverse_vol_weights(prices, lookback=60)

        assert "constant" not in weights.index
        assert "volatile" in weights.index
        assert abs(weights["volatile"] - 1.0) < 1e-9

    def test_nan_column_dropped(self):
        """NaN column is dropped before normalization."""
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = pd.DataFrame({
            "nan_col": [float("nan")] * 65,
            "valid": [100.0 + 2.0 * math.sin(i / 3.0) for i in range(65)],
        }, index=dates)

        weights = inverse_vol_weights(prices, lookback=60)

        assert "nan_col" not in weights.index
        assert "valid" in weights.index
        assert abs(weights["valid"] - 1.0) < 1e-9

    def test_all_invalid_returns_equal_weights(self):
        """If all symbols are invalid (NaN, const, too short), return equal weights over ALL columns."""
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = pd.DataFrame({
            "const1": [100.0] * 65,
            "const2": [50.0] * 65,
            "nan_col": [float("nan")] * 65,
        }, index=dates)

        weights = inverse_vol_weights(prices, lookback=60)

        # All 3 columns should be in the result with equal weights
        assert len(weights) == 3
        expected = 1.0 / 3.0
        for col in prices.columns:
            assert abs(weights[col] - expected) < 1e-9

    def test_all_nan_history_dropped(self):
        """Symbol with all NaN prices (no valid returns) is dropped."""
        dates = pd.date_range("2024-01-01", periods=65, freq="D")
        prices = pd.DataFrame({
            "enough": [100.0 + 2.0 * math.sin(i / 3.0) for i in range(65)],
            "all_nan": [float("nan")] * 65,
        }, index=dates)

        weights = inverse_vol_weights(prices, lookback=60)

        # "all_nan" should be dropped (std is NaN)
        assert "enough" in weights.index
        assert abs(weights["enough"] - 1.0) < 1e-9
        assert "all_nan" not in weights.index

    def test_hand_computed_example(self):
        """Hand-computed numeric example: simple two-symbol case."""
        # Sym1: prices [100, 101, 102, 101, 100] -> returns [0.01, 0.0099, -0.0099, -0.0099]
        # Sym2: prices [100, 110, 100, 110, 100] -> returns [0.10, -0.0909, 0.10, -0.0909]
        # Over 4 returns: sym1 std ~0.0099, sym2 std ~0.0953
        # Inverse: w1 ∝ 1/0.0099 ≈ 101, w2 ∝ 1/0.0953 ≈ 10.5
        # Normalized: w1 ≈ 0.906, w2 ≈ 0.094

        prices = pd.DataFrame({
            "sym1": [100.0, 101.0, 102.0, 101.0, 100.0],
            "sym2": [100.0, 110.0, 100.0, 110.0, 100.0],
        })

        weights = inverse_vol_weights(prices, lookback=4)

        # Rough checks (exact values depend on pandas std implementation)
        assert weights["sym1"] > weights["sym2"]  # lower vol gets higher weight
        assert abs(weights.sum() - 1.0) < 1e-9
        assert weights["sym1"] > 0.8  # lower-vol should be majority
        assert weights["sym2"] < 0.2  # higher-vol should be minority


class TestTargetShares:
    """target_shares: round shares and omit invalid cases."""

    def test_basic_allocation(self):
        """Basic case: allocate USD to symbols at given weights."""
        weights = pd.Series({"AAPL": 0.6, "GOOG": 0.4}, index=["AAPL", "GOOG"])
        prices = pd.Series({"AAPL": 100.0, "GOOG": 50.0})

        shares = target_shares(weights, allocation_usd=1000.0, prices=prices)

        # AAPL: 0.6 * 1000 / 100 = 6 shares
        # GOOG: 0.4 * 1000 / 50 = 8 shares
        assert shares == {"AAPL": 6, "GOOG": 8}

    def test_rounding_down(self):
        """Shares are rounded to int (truncated/rounded by Python's round())."""
        weights = pd.Series({"SYM": 1.0})
        prices = pd.Series({"SYM": 100.3})

        shares = target_shares(weights, allocation_usd=1000.0, prices=prices)

        # 1000 / 100.3 ≈ 9.97, rounds to 10
        assert shares["SYM"] == 10

    def test_zero_shares_omitted(self):
        """Symbol with zero resulting shares is omitted."""
        weights = pd.Series({"BIG": 0.95, "TINY": 0.05})
        prices = pd.Series({"BIG": 100.0, "TINY": 10000.0})

        shares = target_shares(weights, allocation_usd=100.0, prices=prices)

        # BIG: 0.95 * 100 / 100 = 0.95 -> 1 share
        # TINY: 0.05 * 100 / 10000 = 0.0005 -> 0 shares (omitted)
        assert "BIG" in shares
        assert shares["BIG"] == 1
        assert "TINY" not in shares

    def test_negative_price_omitted(self):
        """Symbol with negative or zero price is omitted."""
        weights = pd.Series({"GOOD": 0.5, "BAD": 0.5})
        prices = pd.Series({"GOOD": 100.0, "BAD": -50.0})

        shares = target_shares(weights, allocation_usd=1000.0, prices=prices)

        assert "GOOD" in shares
        assert "BAD" not in shares

    def test_nan_price_omitted(self):
        """Symbol with NaN price is omitted."""
        weights = pd.Series({"A": 0.5, "B": 0.5})
        prices = pd.Series({"A": 100.0, "B": float("nan")})

        shares = target_shares(weights, allocation_usd=1000.0, prices=prices)

        assert "A" in shares
        assert "B" not in shares

    def test_zero_weight_zero_shares(self):
        """Symbol with zero weight produces zero shares (omitted)."""
        weights = pd.Series({"A": 1.0, "B": 0.0})
        prices = pd.Series({"A": 100.0, "B": 50.0})

        shares = target_shares(weights, allocation_usd=1000.0, prices=prices)

        assert "A" in shares
        assert "B" not in shares

    def test_returns_dict_not_series(self):
        """Return type is dict, not pd.Series."""
        weights = pd.Series({"A": 1.0})
        prices = pd.Series({"A": 100.0})

        result = target_shares(weights, allocation_usd=100.0, prices=prices)

        assert isinstance(result, dict)
        assert not isinstance(result, pd.Series)

    def test_hand_computed_multi_symbol(self):
        """Hand-computed: three symbols with different prices."""
        # Allocation: $1000
        # A: weight 0.5, price $50 -> 0.5*1000/50 = 10 shares
        # B: weight 0.3, price $100 -> 0.3*1000/100 = 3 shares
        # C: weight 0.2, price $200 -> 0.2*1000/200 = 1 share

        weights = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
        prices = pd.Series({"A": 50.0, "B": 100.0, "C": 200.0})

        shares = target_shares(weights, allocation_usd=1000.0, prices=prices)

        assert shares == {"A": 10, "B": 3, "C": 1}

    def test_empty_weights(self):
        """Empty weights series returns empty dict."""
        weights = pd.Series(dtype=float)
        prices = pd.Series(dtype=float)

        result = target_shares(weights, allocation_usd=1000.0, prices=prices)

        assert result == {}
