"""Cross-asset trend book: signal, risk-parity weights, and target contracts.

Transcribes the construction validated by the A2 gate (docs/cross-asset-trend-findings.md) so that
what runs is what was tested: a 3-lookback ensemble, inverse-vol weights across markets, and a
book-level vol target.

WHY THESE EIGHT MARKETS. The gate tested 16 ETF proxies, but at a ~$200k risk base 8 of the 16
corresponding futures round to 0 or 1 contract — a >=50% sizing error that would destroy the very
risk-parity construction that carries the edge. Restricting to markets whose contracts are small
enough to size sensibly left these eight, and the narrower book then *beat* the full sixteen:
Sharpe 0.83 vs 0.78, drawdown -16.8% vs -21.1%, correlation to the existing ETF basket +0.06 vs
+0.17. That is a fortunate result rather than a designed one, so changing this universe means
re-running the gate, not editing the table.

PROXY FIDELITY IS UNEVEN, and deliberately recorded per market. The gate's evidence is ETF-based;
some futures map onto their proxy exactly (M2K/IWM) and some only approximately (ZC/DBA, where the
proxy is a broad agriculture basket rather than corn). The looser the mapping, the more the live
result may differ from the gate.
"""
import math
from typing import NamedTuple

import numpy as np
import pandas as pd

LOOKBACKS = (63, 126, 252)
VOL_WINDOW = 63
TARGET_VOL = 0.10
LEVERAGE_CAP = 3.0
MIN_HISTORY = max(LOOKBACKS) + VOL_WINDOW      # enough for the longest signal AND the vol estimate


class Market(NamedTuple):
    symbol: str
    exchange: str
    multiplier: float
    sleeve: str
    proxy: str        # the ETF the gate used to validate this market
    note: str         # how faithful that proxy is


UNIVERSE = [
    Market("M2K", "CME", 5.0, "equity", "IWM", "exact — micro Russell 2000 vs the Russell 2000 ETF"),
    Market("MES", "CME", 5.0, "equity", "SPY", "exact — micro S&P 500 vs the S&P 500 ETF"),
    Market("ZT", "CBOT", 2000.0, "bond", "SHY", "close — 2y note future vs the 1-3y Treasury ETF"),
    Market("ZF", "CBOT", 1000.0, "bond", "IEF", "approximate — 5y note future vs a 7-10y ETF; "
                                                "shorter duration than the proxy"),
    Market("M6E", "CME", 12500.0, "fx", "FXE", "exact — micro EUR/USD vs the euro ETF"),
    Market("M6A", "CME", 10000.0, "fx", "UUP", "loose — micro AUD/USD stood in for a broad dollar "
                                               "ETF in the gate; a single currency, not the index"),
    Market("MCL", "NYMEX", 100.0, "commodity", "USO", "close — micro WTI vs a WTI ETF that carries "
                                                     "its own roll drag"),
    Market("ZC", "CBOT", 5000.0, "commodity", "DBA", "loose — corn vs a broad agriculture basket"),
]


def ensemble_signal(prices: pd.DataFrame, lookbacks=LOOKBACKS) -> pd.DataFrame:
    """Mean of the sign of the return over each lookback, so disagreement gives a partial position."""
    return sum(np.sign(prices / prices.shift(lb) - 1.0) for lb in lookbacks) / len(lookbacks)


def risk_parity_weights(signal: pd.DataFrame, prices: pd.DataFrame,
                        vol_window: int = VOL_WINDOW) -> pd.DataFrame:
    """Signed weights whose absolute values sum to 1 — equal risk per market, direction from signal."""
    inv_vol = 1.0 / prices.pct_change().rolling(vol_window).std()
    raw = (signal * inv_vol).replace([np.inf, -np.inf], np.nan)
    return raw.div(raw.abs().sum(axis=1), axis=0).fillna(0.0)


def book_leverage(weights: pd.DataFrame, prices: pd.DataFrame, target_vol: float = TARGET_VOL,
                  cap: float = LEVERAGE_CAP, vol_window: int = VOL_WINDOW) -> float:
    """Leverage that puts the weighted book at its vol target, from trailing data only."""
    book = (weights.shift(1) * prices.pct_change()).sum(axis=1)
    realised = book.rolling(vol_window).std().iloc[-1] * math.sqrt(252)
    if not np.isfinite(realised) or realised <= 0:
        return 0.0
    return float(min(cap, target_vol / realised))


def target_contracts(weights, leverage: float, risk_base: float, prices, multipliers):
    """Whole contracts per market, plus the rounding error each one incurred.

    Rounding is reported rather than smoothed away: at a ~$200k risk base the smallest market is
    roughly 1.5 contracts, so the error is a material part of how faithfully the tested construction
    is actually being run.
    """
    targets, rounding = {}, {}
    for market, w in dict(weights).items():
        notional = float(w) * leverage * risk_base
        per_contract = float(prices[market]) * float(multipliers[market])
        exact = notional / per_contract if per_contract else 0.0
        targets[market] = int(round(exact))
        rounding[market] = abs(exact - targets[market])
    return targets, rounding


def trend_targets(prices: pd.DataFrame, multipliers: dict, risk_base: float,
                  target_vol: float = TARGET_VOL, cap: float = LEVERAGE_CAP):
    """Full pipeline: price history -> target contracts, with the diagnostics a run should report.

    Raises when history is too short. Without a market-data subscription IBKR returns a handful of
    bars rather than an error, and a signal computed from those would be confident and meaningless —
    refusing is the safer failure (spec FR-007).
    """
    if len(prices) < MIN_HISTORY:
        raise ValueError(
            f"insufficient history: {len(prices)} bars, need {MIN_HISTORY} "
            f"(longest lookback {max(LOOKBACKS)} + {VOL_WINDOW}-day vol window). "
            f"A market-data subscription is required for full futures history."
        )
    signal = ensemble_signal(prices)
    weights = risk_parity_weights(signal, prices)
    lev = book_leverage(weights, prices, target_vol, cap)
    last_w, last_px = weights.iloc[-1], prices.iloc[-1]
    targets, rounding = target_contracts(last_w, lev, risk_base, last_px, multipliers)
    gross = sum(abs(t) * float(last_px[m]) * float(multipliers[m]) for m, t in targets.items())
    return targets, {"leverage": lev, "weights": last_w.to_dict(), "rounding": rounding,
                     "gross_notional": gross, "signal": signal.iloc[-1].to_dict(),
                     "asof": prices.index[-1]}
