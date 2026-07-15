import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import pandas as pd

@dataclass
class RebalanceReport:
    orders: dict
    positions: dict
    equity: float
    turnover: float
    cost: float
    applied: bool

class Execution(Protocol):
    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        ...

class SimExecution:
    """Paper executor. Owns its portfolio in a JSON file; marks the book to market with the
    prices passed each rebalance (spot P&L only — the backtest is the precise P&L model)."""
    def __init__(self, portfolio_path, starting_equity: float = 10000.0, cost_bps: float = 1.0,
                 max_position_weight=None, preview: bool = False):
        self.portfolio_path = Path(portfolio_path)
        self.starting_equity = starting_equity
        self.cost_bps = cost_bps
        self.max_position_weight = max_position_weight
        self.preview = preview

    def _load(self) -> dict:
        if self.portfolio_path.exists():
            return json.loads(self.portfolio_path.read_text())
        return {"equity": self.starting_equity, "weights": {}, "last_prices": {}, "last_date": None}

    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        state = self._load()
        equity = float(state["equity"])
        weights = {k: float(v) for k, v in state["weights"].items()}
        last_prices = state["last_prices"]

        pnl = 0.0                                        # mark-to-market: spot P&L since last run
        for c, w in weights.items():
            if c in last_prices and last_prices[c] and c in prices.index:
                pnl += w * (float(prices[c]) / float(last_prices[c]) - 1.0)
        equity *= (1.0 + pnl)

        target = {c: float(target_weights[c]) for c in target_weights.index}
        if self.max_position_weight is not None:
            cap = self.max_position_weight
            target = {c: max(-cap, min(cap, w)) for c, w in target.items()}

        keys = set(target) | set(weights)
        turnover = sum(abs(target.get(c, 0.0) - weights.get(c, 0.0)) for c in keys)
        cost = (self.cost_bps / 1e4) * turnover * equity
        equity_after = equity - cost
        orders = {c: (target.get(c, 0.0) - weights.get(c, 0.0)) * equity for c in keys}

        applied = not self.preview
        if applied:
            new_state = {
                "equity": equity_after,
                "weights": target,
                "last_prices": {c: float(prices[c]) for c in prices.index},
                "last_date": str(prices.name) if prices.name is not None else None,
            }
            self.portfolio_path.parent.mkdir(parents=True, exist_ok=True)
            self.portfolio_path.write_text(json.dumps(new_state))

        return RebalanceReport(orders=orders, positions=target, equity=equity_after,
                               turnover=turnover, cost=cost, applied=applied)

class LiveExecution:
    """ib_async IBKR adapter. Phase 1: PREVIEW-ONLY — computes the FX orders to reach the target
    weights and returns them with applied=False; places NOTHING. Non-preview raises NotImplementedError.
    Connects readonly=True; prices from historical MIDPOINT bars (competing-session-proof)."""
    def __init__(self, host="127.0.0.1", port=4002, client_id=23, cost_bps: float = 1.0,
                 preview: bool = True, ib_factory=None):
        self.host = host; self.port = port; self.client_id = client_id
        self.cost_bps = cost_bps; self.preview = preview; self._ib_factory = ib_factory

    def _make_ib(self):
        if self._ib_factory is not None:
            return self._ib_factory()
        from ib_async import IB
        return IB()

    @staticmethod
    def _pair(code):
        from forex.config import CURRENCIES
        invert = CURRENCIES[code].spot_invert
        return (f"USD{code}", True) if invert else (f"{code}USD", False)

    @staticmethod
    def _cexp(units, base_usd, p):        # signed USD-notional exposure to the foreign ccy
        return -units if base_usd else units * p

    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        if not self.preview:
            raise NotImplementedError("live order placement is Phase 2; LiveExecution is preview-only")
        from ib_async import Forex
        ib = self._make_ib()
        competing = {"hit": False}
        def _on_err(reqId, code, msg, contract):
            if code == 10197:
                competing["hit"] = True
        ib.errorEvent += _on_err
        try:
            ib.connect(self.host, self.port, clientId=self.client_id, timeout=15, readonly=True)
            nav = next((float(v.value) for v in ib.accountSummary() if v.tag == "NetLiquidation"), None)
            if nav is None:
                raise RuntimeError("could not read NetLiquidation (NAV) from IBKR")
            cur_by_conid = {p.contract.conId: float(p.position) for p in ib.positions()}
            orders, positions, turnover = {}, {}, 0.0
            for code in target_weights.index:
                w = float(target_weights[code])
                if code == "USD" or abs(w) < 1e-12:
                    continue
                pair, base_usd = self._pair(code)
                c = Forex(pair); ib.qualifyContracts(c)
                bars = ib.reqHistoricalData(c, "", "2 D", "1 day", "MIDPOINT", useRTH=False)
                if not bars:
                    raise RuntimeError(f"no historical price for {pair}")
                p = float(bars[-1].close)
                usd_notional = w * nav
                target_units = (-usd_notional) if base_usd else (usd_notional / p)
                current_units = cur_by_conid.get(getattr(c, "conId", None), 0.0)
                orders[pair] = target_units - current_units
                positions[pair] = target_units
                turnover += abs(usd_notional - self._cexp(current_units, base_usd, p)) / nav
            if competing["hit"]:
                print("WARNING: competing live session (Error 10197) — another IBKR login holds the "
                      "market-data line; log out of TWS / mobile app / web portal for live streaming "
                      "(historical prices used here are unaffected).")
            cost = (self.cost_bps / 1e4) * turnover * nav
            return RebalanceReport(orders=orders, positions=positions, equity=nav,
                                   turnover=turnover, cost=cost, applied=False)
        finally:
            ib.disconnect()
