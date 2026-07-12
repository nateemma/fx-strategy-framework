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
    """ib_async broker adapter — NOT IMPLEMENTED (deferred until a TWS/IBKR paper account exists).
    Intended flow: query current positions + NAV from IB; target units = target_weight * NAV / price;
    place IDEALPRO orders to reach target; reconcile fills. Same Execution protocol as SimExecution."""
    def __init__(self, *args, **kwargs):
        pass
    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        raise NotImplementedError("LiveExecution (ib_async) is deferred; use SimExecution (paper).")
