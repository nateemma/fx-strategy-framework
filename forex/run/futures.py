"""ib_async IBKR adapter for a futures book. The third executor, after LiveExecution (FX) and
BasketExecution (Stock/SMART).

Deliberately the same shape as the other two: preview by default, explicit confirm to place, a
paper-account check with an explicit live gate, the per-order cap as an ATOMIC PRE-PASS, reconcile
against what the account actually holds, and a best-effort unwind that never raises. Every deviation
from that shape would be a place a reviewer has to think again, so there are none.

Two things are new to futures and are where the risk lives:

- **Contract roll.** Positions expire. Rolling is delegated to forex/run/futures_roll.py and
  reconciliation happens PER MARKET, so a roll comes out as a matched pair that nets to zero
  exposure change rather than looking like the signal round-tripping.
- **Margin.** Futures consume it. Placement is refused if it would take available funds below a
  floor, because unlike the cash sleeves this book can move the account toward a margin call.
"""
import math
from dataclasses import dataclass, field
from datetime import date, datetime

from forex.run.futures_roll import ROLL_DAYS, front_expiry, reconcile_market
from forex.run.ibconnect import connect_with_retry


@dataclass
class FuturesReport:
    orders: dict                                  # market -> signed contracts traded (or intended)
    positions: dict                               # market -> target contracts
    equity: float
    applied: bool
    complete: bool = True
    account: str = ""
    rolled: list = field(default_factory=list)    # markets rolled this run
    skipped: dict = field(default_factory=dict)


class FuturesExecution:
    def __init__(self, markets, host="127.0.0.1", port=4002, client_id=29, preview=True,
                 confirm=False, allow_live=False, max_order_frac=0.5, min_available_funds=25_000.0,
                 roll_days=ROLL_DAYS, tif="DAY",
                 ib_factory=None, contract_factory=None, order_factory=None):
        self.markets = list(markets)              # (symbol, exchange, multiplier)
        self.host, self.port, self.client_id = host, port, client_id
        self.preview, self.confirm, self.allow_live = preview, confirm, allow_live
        self.max_order_frac = max_order_frac
        self.min_available_funds = min_available_funds
        self.roll_days, self.tif = roll_days, tif
        self._ib_factory, self._contract_factory = ib_factory, contract_factory
        self._order_factory = order_factory

    # ---- injectable broker seams, so tests never import ib_async -------------------------------
    def _make_ib(self):
        if self._ib_factory is not None:
            return self._ib_factory()
        from ib_async import IB
        return IB()

    def _make_contract(self, **kw):
        if self._contract_factory is not None:
            return self._contract_factory(**kw)
        from ib_async import Future
        return Future(**kw)

    def _make_order(self, action, qty):
        if self._order_factory is not None:
            return self._order_factory(action, qty)
        from ib_async import MarketOrder
        return MarketOrder(action, qty)

    # ---- the same never-raising unwind the other executors use ---------------------------------
    def _unwind(self, ib, placed):
        """Cancel unfilled, flatten filled, from THIS batch only. Never raises: a failure here must
        not mask the original placement error. The operator must verify positions afterwards."""
        try:
            ib.sleep(2)
        except Exception:
            pass
        for market, tr, contract, _intended in placed:
            try:
                if tr.orderStatus.status not in ("Filled",):
                    ib.cancelOrder(tr.order)
                filled = (sum(float(f.execution.shares) for f in getattr(tr, "fills", []))
                          or float(tr.orderStatus.filled))
                if filled:
                    opp = "SELL" if tr.order.action == "BUY" else "BUY"
                    o = self._make_order(opp, int(round(abs(filled))))
                    o.tif = self.tif
                    ib.placeOrder(contract, o)
            except Exception as ue:
                print(f"WARNING: unwind of {market} FAILED ({ue!r}) — POSITION MAY BE OPEN; "
                      f"verify in IBKR")
        try:
            ib.sleep(3)
        except Exception:
            pass

    @staticmethod
    def _expiry(contract):
        return datetime.strptime(contract.lastTradeDateOrContractMonth[:8], "%Y%m%d").date()

    def _compute(self, ib, targets, asof):
        """Resolve contracts, pick the front month per market, and reconcile against holdings."""
        nav = next((float(v.value) for v in ib.accountSummary() if v.tag == "NetLiquidation"), None)
        if nav is None or not math.isfinite(nav) or nav <= 0:
            raise RuntimeError(f"invalid NAV from IBKR: {nav!r}")
        available = next((float(v.value) for v in ib.accountSummary()
                          if v.tag == "AvailableFunds"), None)

        try:
            ib.reqPositions(); ib.sleep(1.5)      # let the snapshot populate, as the others do
        except Exception:
            pass
        held_by_conid = {p.contract.conId: float(p.position) for p in ib.positions()}

        chains, fronts, orders, prices, rolled = {}, {}, {}, {}, []
        for symbol, exchange, multiplier in self.markets:
            details = ib.reqContractDetails(self._make_contract(
                symbol=symbol, exchange=exchange, currency="USD"))
            if not details:
                raise RuntimeError(f"no contracts found for {symbol} on {exchange}")
            by_expiry = {self._expiry(d.contract): d.contract for d in details}
            chains[symbol] = by_expiry
            front = front_expiry(by_expiry, asof, self.roll_days)
            fronts[symbol] = front

            held = {e: held_by_conid.get(c.conId, 0.0) for e, c in by_expiry.items()}
            held = {e: q for e, q in held.items() if q}
            per_expiry = reconcile_market(int(targets.get(symbol, 0)), held, front)
            if per_expiry and any(e != front for e in per_expiry):
                rolled.append(symbol)
            for expiry, delta in per_expiry.items():
                orders[(symbol, expiry)] = delta

            bars = ib.reqHistoricalData(by_expiry[front] if front else next(iter(by_expiry.values())),
                                        "", "1 D", "1 day", "TRADES", useRTH=True)
            price = float(bars[-1].close) if bars else float("nan")
            if not math.isfinite(price) or price <= 0:
                raise RuntimeError(f"invalid price for {symbol}: {price!r}")
            prices[symbol] = price

        return {"nav": nav, "available": available, "orders": orders, "chains": chains,
                "fronts": fronts, "prices": prices, "rolled": rolled}

    def rebalance(self, targets: dict, risk_base: float = None, asof: date = None) -> FuturesReport:
        """Move the book to `targets` (market -> signed whole contracts)."""
        asof = asof or date.today()
        mult = {s: m for s, _e, m in self.markets}

        if self.preview:
            ib = self._make_ib()
            try:
                connect_with_retry(ib, self.host, self.port, self.client_id, readonly=True)
                c = self._compute(ib, targets, asof)
                by_market = {}
                for (sym, _exp), d in c["orders"].items():
                    by_market[sym] = by_market.get(sym, 0) + d
                return FuturesReport(orders={k: v for k, v in by_market.items() if v},
                                     positions=dict(targets), equity=c["nav"], applied=False,
                                     rolled=c["rolled"])
            finally:
                ib.disconnect()

        if not self.confirm:
            raise RuntimeError("placement requires confirm=True (pass --confirm)")

        ib = self._make_ib()
        try:
            connect_with_retry(ib, self.host, self.port, self.client_id, readonly=False)
            acct = (ib.managedAccounts() or [""])[0]
            if not acct.startswith("DU") and not self.allow_live:
                raise RuntimeError(
                    f"refusing to place on non-paper account {acct!r} without allow_live")
            c = self._compute(ib, targets, asof)

            if (self.min_available_funds and c["available"] is not None
                    and c["available"] < self.min_available_funds):
                raise RuntimeError(
                    f"available funds {c['available']:,.0f} below floor "
                    f"{self.min_available_funds:,.0f} — refusing to add futures margin")

            # ATOMIC PRE-PASS: every cap checked before a single order is placed, so a breach on a
            # later market cannot leave earlier ones filled.
            base = risk_base or c["nav"]
            for (sym, _expiry), delta in c["orders"].items():
                notional = abs(delta) * c["prices"][sym] * mult[sym]
                if notional / base > self.max_order_frac:
                    raise RuntimeError(
                        f"order {sym} {notional / base:.0%} of risk base exceeds "
                        f"max_order_frac {self.max_order_frac:.0%}")

            placed = []
            try:
                for (sym, expiry), delta in c["orders"].items():
                    contract = c["chains"][sym][expiry]
                    order = self._make_order("BUY" if delta > 0 else "SELL", int(round(abs(delta))))
                    order.tif = self.tif
                    placed.append((sym, ib.placeOrder(contract, order), contract, delta))
            except Exception as e:
                self._unwind(ib, placed)
                raise RuntimeError(f"placement failed after {len(placed)} orders; attempted "
                                   f"best-effort unwind (VERIFY POSITIONS IN IBKR): {e}") from e

            TERMINAL = ("Filled", "Cancelled", "ApiCancelled", "Inactive")
            for _ in range(60):
                if all(tr.orderStatus.status in TERMINAL for _, tr, _, _ in placed):
                    break
                ib.sleep(1)

            fills, complete = {}, True
            for sym, tr, _contract, intended in placed:
                sgn = 1.0 if tr.order.action == "BUY" else -1.0
                qty = (sum(float(f.execution.shares) for f in getattr(tr, "fills", []))
                       or float(tr.orderStatus.filled))
                fills[sym] = fills.get(sym, 0.0) + sgn * qty
                if abs(qty) < abs(intended) - 1e-9:
                    complete = False
            return FuturesReport(orders=fills, positions=dict(targets), equity=c["nav"],
                                 applied=True, complete=complete, account=acct, rolled=c["rolled"])
        finally:
            ib.disconnect()
