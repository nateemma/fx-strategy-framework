import json
import math
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
    complete: bool = True

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
    """ib_async IBKR adapter. Preview path: readonly=True, applied=False, places nothing.
    Placement path: confirm=True required; connects readonly=False; five guards before any placeOrder."""
    def __init__(self, host="127.0.0.1", port=4002, client_id=23, cost_bps: float = 1.0,
                 preview: bool = True, ib_factory=None, contract_factory=None,
                 confirm: bool = False, max_order_frac: float = 0.25, max_gross: float = 2.5,
                 min_order_units: int = 20000, allow_live: bool = False, tif: str = "DAY",
                 order_factory=None):
        self.host = host; self.port = port; self.client_id = client_id
        self.cost_bps = cost_bps; self.preview = preview
        self._ib_factory = ib_factory; self._contract_factory = contract_factory
        self.confirm = confirm; self.max_order_frac = min(float(max_order_frac), 1.0); self.max_gross = max_gross
        self.min_order_units = min_order_units; self.allow_live = allow_live; self.tif = tif
        self._order_factory = order_factory

    def _make_ib(self):
        if self._ib_factory is not None:
            return self._ib_factory()
        from ib_async import IB
        return IB()

    def _make_contract(self):
        # returns a callable pair_str -> contract; lazy ib_async import only when not injected,
        # so the sign-correctness tests run hermetically without ib_async.
        if self._contract_factory is not None:
            return self._contract_factory
        from ib_async import Forex
        return Forex

    def _make_order(self):
        if self._order_factory is not None:
            return self._order_factory
        from ib_async import MarketOrder
        return MarketOrder

    @staticmethod
    def _pair(code):
        from forex.config import CURRENCIES
        invert = CURRENCIES[code].spot_invert
        return (f"USD{code}", True) if invert else (f"{code}USD", False)

    @staticmethod
    def _cexp(units, base_usd, p):        # signed USD-notional exposure to the foreign ccy
        return -units if base_usd else units * p

    def _compute(self, ib, target_weights) -> dict:
        nav = next((float(v.value) for v in ib.accountSummary() if v.tag == "NetLiquidation"), None)
        if nav is None or not math.isfinite(nav) or nav <= 0:
            raise RuntimeError(f"invalid NAV from IBKR: {nav!r}")
        make_contract = self._make_contract()
        cur_by_conid = {p.contract.conId: float(p.position) for p in ib.positions()}
        orders, positions, turnover = {}, {}, 0.0
        base_usd_map, price_map, contract_map = {}, {}, {}
        for code in target_weights.index:
            w = float(target_weights[code])
            if not math.isfinite(w):                       # NaN/inf weight would fail the caps OPEN
                raise RuntimeError(f"non-finite target weight for {code}: {w!r}")
            if code == "USD" or abs(w) < 1e-12:
                continue
            pair, base_usd = self._pair(code)
            c = make_contract(pair); ib.qualifyContracts(c)
            if not getattr(c, "conId", None):
                raise RuntimeError(f"could not qualify {pair} on IBKR IDEALPRO")
            bars = ib.reqHistoricalData(c, "", "2 D", "1 day", "MIDPOINT", useRTH=False)
            if not bars:
                raise RuntimeError(f"no historical price for {pair}")
            p = float(bars[-1].close)
            if not math.isfinite(p) or p <= 0:             # bad price would size orders wrong / fail caps open
                raise RuntimeError(f"invalid price for {pair}: {p!r}")
            usd_notional = w * nav
            target_units = (-usd_notional) if base_usd else (usd_notional / p)
            current_units = cur_by_conid.get(getattr(c, "conId", None), 0.0)
            orders[pair] = target_units - current_units
            positions[pair] = target_units
            turnover += abs(usd_notional - self._cexp(current_units, base_usd, p)) / nav
            base_usd_map[pair] = base_usd
            price_map[pair] = p
            contract_map[pair] = c
        return {"nav": nav, "orders": orders, "positions": positions,
                "base_usd": base_usd_map, "price": price_map, "contract": contract_map,
                "turnover": turnover}

    def _unwind(self, ib, placed):
        # Best-effort: cancel unfilled + flatten filled from this batch. NEVER raises (a failure here must
        # not mask the original placement error). Flattens are fire-and-forget/UNVERIFIED — the operator
        # MUST verify positions in IBKR after any unwind. Failures are logged, not silent.
        try:
            ib.sleep(2)                                # let statuses settle
        except Exception:
            pass
        for pair, tr, contract, _intended in placed:
            try:
                if tr.orderStatus.status not in ("Filled",):
                    ib.cancelOrder(tr.order)           # unfilled remainder -> cancel
                filled = sum(float(f.execution.shares) for f in getattr(tr, "fills", [])) or float(tr.orderStatus.filled)
                if filled:                             # already filled -> flatten opposite
                    opp = "SELL" if tr.order.action == "BUY" else "BUY"
                    o = self._make_order()(opp, round(abs(filled))); o.tif = self.tif
                    ib.placeOrder(contract, o)         # contract carries exchange=IDEALPRO already
            except Exception as ue:
                print(f"WARNING: unwind of {pair} FAILED ({ue!r}) — POSITION MAY BE OPEN; verify in IBKR")
        try:
            ib.sleep(3)
        except Exception:
            pass

    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        competing = {"hit": False}
        def _on_err(rid, code, msg, c):
            if code == 10197: competing["hit"] = True
        if self.preview:
            ib = self._make_ib(); ib.errorEvent += _on_err
            try:
                ib.connect(self.host, self.port, clientId=self.client_id, timeout=15, readonly=True)
                c = self._compute(ib, target_weights)
                if competing["hit"]:
                    print("WARNING: competing live session (Error 10197) — another IBKR login holds the "
                          "market-data line; log out of TWS / mobile app / web portal for live streaming "
                          "(historical prices used here are unaffected).")
                cost = (self.cost_bps / 1e4) * c["turnover"] * c["nav"]
                return RebalanceReport(orders=c["orders"], positions=c["positions"], equity=c["nav"],
                                       turnover=c["turnover"], cost=cost, applied=False)
            finally:
                ib.disconnect()
        # ---- placement ----
        if not self.confirm:
            raise RuntimeError("placement requires confirm=True (pass --confirm)")
        ib = self._make_ib()
        try:
            ib.connect(self.host, self.port, clientId=self.client_id, timeout=15, readonly=False)
            acct = (ib.managedAccounts() or [""])[0]
            if not acct.startswith("DU") and not self.allow_live:
                raise RuntimeError(f"refusing to place on non-paper account {acct!r} without allow_live")
            c = self._compute(ib, target_weights)
            gross = sum(abs(float(target_weights[k])) for k in target_weights.index if k != "USD")
            if gross > self.max_gross:
                raise RuntimeError(f"gross {gross:.2f}x exceeds max_gross {self.max_gross}")
            for pair, units in c["orders"].items():
                notional = abs(units) * (1.0 if c["base_usd"][pair] else c["price"][pair])
                if notional / c["nav"] > self.max_order_frac:
                    raise RuntimeError(f"order {pair} {notional / c['nav']:.0%} exceeds max_order_frac {self.max_order_frac:.0%}")
            placed = []   # list of (pair, trade, contract, intended_units)
            try:
                make_order = self._make_order()
                for pair, units in c["orders"].items():
                    if abs(units) < self.min_order_units:
                        continue
                    order = make_order("BUY" if units > 0 else "SELL", round(abs(units))); order.tif = self.tif
                    tr = ib.placeOrder(c["contract"][pair], order)
                    placed.append((pair, tr, c["contract"][pair], units))
            except Exception as e:
                self._unwind(ib, placed)               # cancel unfilled + flatten filled (best-effort)
                raise RuntimeError(f"placement failed after {len(placed)} orders; attempted best-effort "
                                   f"unwind (VERIFY POSITIONS IN IBKR): {e}") from e
            TERMINAL = ("Filled", "Cancelled", "ApiCancelled", "Inactive")
            for _ in range(60):                       # wait for ALL orders to settle (not per-order)
                if all(tr.orderStatus.status in TERMINAL for _, tr, _, _ in placed): break
                ib.sleep(1)
            fills, complete = {}, True
            for pair, tr, _c, intended in placed:
                sgn = 1.0 if tr.order.action == "BUY" else -1.0
                qty = sum(float(f.execution.shares) for f in getattr(tr, "fills", [])) or float(tr.orderStatus.filled)
                fills[pair] = sgn * qty
                if abs(qty) < abs(intended) - 1.0:    # under-filled (1-unit tolerance)
                    complete = False
            cost = (self.cost_bps / 1e4) * c["turnover"] * c["nav"]
            return RebalanceReport(orders=fills, positions=c["positions"], equity=c["nav"],
                                   turnover=c["turnover"], cost=cost, applied=True, complete=complete)
        finally:
            ib.disconnect()
