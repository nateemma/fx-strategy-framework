import math
from dataclasses import dataclass, field
import pandas as pd
from forex.run.ibconnect import connect_with_retry
from forex.run.basket_weights import inverse_vol_weights, target_shares

@dataclass
class BasketReport:
    orders: dict
    positions: dict
    weights: dict
    equity: float
    allocation: float
    applied: bool
    complete: bool = True
    skipped: dict = field(default_factory=dict)   # symbol -> USD notional, for legs below min_order_usd
    account: str = ""                             # real traded account (placement only; "" on preview)

class BasketExecution:
    """ib_async IBKR adapter for a long-only Stock/SMART risk-parity basket. Mirrors LiveExecution
    (FX) but simpler: no FX inversion, no odd-lot."""
    def __init__(self, symbols=("SPY", "TLT", "IEF", "GLD", "DBC"), host="127.0.0.1", port=4002,
                 client_id=24, preview=True, confirm=False, allow_live=False, lookback=60,
                 min_order_usd=500.0, max_order_frac=0.6, tif="DAY",
                 ib_factory=None, contract_factory=None, order_factory=None):
        self.symbols = symbols; self.host = host; self.port = port; self.client_id = client_id
        self.preview = preview; self.confirm = confirm; self.allow_live = allow_live
        self.lookback = lookback; self.min_order_usd = min_order_usd; self.max_order_frac = max_order_frac
        self.tif = tif
        self._ib_factory = ib_factory; self._contract_factory = contract_factory; self._order_factory = order_factory

    def _make_ib(self):
        if self._ib_factory is not None:
            return self._ib_factory()
        from ib_async import IB
        return IB()

    def _make_contract(self):
        if self._contract_factory is not None:
            return self._contract_factory
        from ib_async import Stock
        return Stock

    def _make_order(self):
        if self._order_factory is not None:
            return self._order_factory
        from ib_async import MarketOrder
        return MarketOrder

    def _unwind(self, ib, placed):
        # Best-effort: cancel unfilled + flatten filled from this batch. NEVER raises (a failure here
        # must not mask the original placement error). The operator MUST verify positions in IBKR after.
        try:
            ib.sleep(2)
        except Exception:
            pass
        for sym, tr, contract, _intended in placed:
            try:
                if tr.orderStatus.status not in ("Filled",):
                    ib.cancelOrder(tr.order)
                filled = sum(float(f.execution.shares) for f in getattr(tr, "fills", [])) or float(tr.orderStatus.filled)
                if filled:
                    opp = "SELL" if tr.order.action == "BUY" else "BUY"
                    o = self._make_order()(opp, round(abs(filled))); o.tif = self.tif
                    ib.placeOrder(contract, o)
            except Exception as ue:
                print(f"WARNING: unwind of {sym} FAILED ({ue!r}) — POSITION MAY BE OPEN; verify in IBKR")
        try:
            ib.sleep(3)
        except Exception:
            pass

    def _compute(self, ib, allocation_usd):
        nav = next((float(v.value) for v in ib.accountSummary() if v.tag == "NetLiquidation"), None)
        if nav is None or not math.isfinite(nav) or nav <= 0:
            raise RuntimeError(f"invalid NAV from IBKR: {nav!r}")
        make_contract = self._make_contract()
        history, last_price, contracts = {}, {}, {}
        for sym in self.symbols:
            c = make_contract(sym, "SMART", "USD"); ib.qualifyContracts(c)
            if not getattr(c, "conId", None):
                raise RuntimeError(f"could not qualify {sym} on SMART")
            bars = ib.reqHistoricalData(c, "", "120 D", "1 day", "MIDPOINT", useRTH=True)
            if not bars:
                raise RuntimeError(f"no historical data for {sym}")
            p = float(bars[-1].close)
            if not math.isfinite(p) or p <= 0:
                raise RuntimeError(f"invalid last price for {sym}: {p!r}")
            history[sym] = pd.Series({b.date: float(b.close) for b in bars})
            last_price[sym] = p
            contracts[sym] = c
        weights = inverse_vol_weights(pd.concat(history, axis=1), self.lookback)
        target = target_shares(weights, allocation_usd, pd.Series(last_price))
        try:                                  # ensure the position snapshot has populated after connect
            ib.reqPositions(); ib.sleep(1.5)
        except Exception:
            pass
        cur_by_conid = {p.contract.conId: float(p.position) for p in ib.positions()}
        orders = {}
        for sym in self.symbols:
            tgt = target.get(sym, 0)
            cur = cur_by_conid.get(getattr(contracts[sym], "conId", None), 0.0)
            d = tgt - cur
            if abs(d) > 1e-9:
                orders[sym] = d
        return {"nav": nav, "weights": weights.to_dict(), "positions": target, "orders": orders,
                "price": last_price, "contract": contracts}

    def rebalance(self, allocation_usd: float) -> BasketReport:
        if self.preview:
            ib = self._make_ib()
            try:
                connect_with_retry(ib, self.host, self.port, self.client_id, readonly=True)
                c = self._compute(ib, allocation_usd)
                return BasketReport(orders=c["orders"], positions=c["positions"], weights=c["weights"],
                                    equity=c["nav"], allocation=allocation_usd, applied=False)
            finally:
                ib.disconnect()
        # ---- placement ----
        if not self.confirm:
            raise RuntimeError("placement requires confirm=True (pass --confirm)")
        ib = self._make_ib()
        try:
            connect_with_retry(ib, self.host, self.port, self.client_id, readonly=False)
            acct = (ib.managedAccounts() or [""])[0]
            if not acct.startswith("DU") and not self.allow_live:
                raise RuntimeError(f"refusing to place on non-paper account {acct!r} without allow_live")
            c = self._compute(ib, allocation_usd)
            for sym, d in c["orders"].items():
                notional = abs(d) * c["price"][sym]
                if notional / allocation_usd > self.max_order_frac:
                    raise RuntimeError(f"order {sym} {notional / allocation_usd:.0%} exceeds max_order_frac {self.max_order_frac:.0%}")
            placed, skipped = [], {}
            try:
                make_order = self._make_order()
                for sym, d in c["orders"].items():
                    notional = abs(d) * c["price"][sym]
                    if notional < self.min_order_usd:
                        skipped[sym] = notional
                        continue
                    order = make_order("BUY" if d > 0 else "SELL", round(abs(d))); order.tif = self.tif
                    tr = ib.placeOrder(c["contract"][sym], order)
                    placed.append((sym, tr, c["contract"][sym], d))
            except Exception as e:
                self._unwind(ib, placed)           # cancel unfilled + flatten filled (best-effort)
                raise RuntimeError(f"placement failed after {len(placed)} orders; attempted best-effort "
                                   f"unwind (VERIFY POSITIONS IN IBKR): {e}") from e
            TERMINAL = ("Filled", "Cancelled", "ApiCancelled", "Inactive")
            for _ in range(60):                    # wait for ALL orders to settle (not per-order)
                if all(tr.orderStatus.status in TERMINAL for _, tr, _, _ in placed): break
                ib.sleep(1)
            fills, complete = {}, True
            for sym, tr, _c, intended in placed:
                sgn = 1.0 if tr.order.action == "BUY" else -1.0
                qty = sum(float(f.execution.shares) for f in getattr(tr, "fills", [])) or float(tr.orderStatus.filled)
                fills[sym] = sgn * qty
                if abs(qty) < abs(intended) - 1.0:  # under-filled (1-unit tolerance)
                    complete = False
            return BasketReport(orders=fills, positions=c["positions"], weights=c["weights"], equity=c["nav"],
                                allocation=allocation_usd, applied=True, complete=complete, skipped=skipped,
                                account=acct)
        finally:
            ib.disconnect()
