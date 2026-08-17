from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from forex.run.futures import FuturesExecution

TODAY = date(2026, 8, 17)
NEAR, FRONT, BACK = date(2026, 8, 21), date(2026, 9, 18), date(2026, 12, 18)


class _Val:
    def __init__(self, tag, value):
        self.tag, self.value = tag, value


class _Pos:
    def __init__(self, conId, position):
        self.contract, self.position = SimpleNamespace(conId=conId), position


class _Bar:
    def __init__(self, close):
        self.close = close


class _FakeIB:
    """Deterministic broker for the futures executor. Records every order it is asked to place."""

    def __init__(self, nav=1_000_000.0, available=750_000.0, positions=None,
                 price=100.0, expiries=(NEAR, FRONT, BACK), acct="DU123456"):
        self._nav, self._available, self._price = nav, available, price
        self._positions = positions or []
        self._expiries, self._acct = list(expiries), acct
        self.placeOrder_calls, self.cancel_calls = 0, 0
        self.placed, self._fail_on, self._fill_frac = [], None, 1.0

    def connect(self, *a, **k):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def accountSummary(self):
        return [_Val("NetLiquidation", str(self._nav)), _Val("AvailableFunds", str(self._available))]

    def positions(self):
        return self._positions

    def reqPositions(self):
        pass

    def sleep(self, s):
        pass

    def managedAccounts(self):
        return [self._acct]

    def reqContractDetails(self, contract):
        out = []
        for e in self._expiries:
            c = SimpleNamespace(symbol=contract.symbol, conId=abs(hash((contract.symbol, e))) % 10**6,
                                lastTradeDateOrContractMonth=e.strftime("%Y%m%d"),
                                multiplier="5", exchange=contract.exchange)
            out.append(SimpleNamespace(contract=c))
        return out

    def reqHistoricalData(self, contract, *a, **k):
        return [_Bar(self._price)] * 400

    def cancelOrder(self, order):
        self.cancel_calls += 1

    def placeOrder(self, contract, order):
        self.placeOrder_calls += 1
        self.placed.append((contract.symbol, order.action, order.totalQuantity))
        if self._fail_on is not None and self.placeOrder_calls == self._fail_on:
            raise RuntimeError("induced placeOrder failure")
        filled = order.totalQuantity * self._fill_frac
        return SimpleNamespace(
            order=order,
            orderStatus=SimpleNamespace(status="Filled" if self._fill_frac >= 1.0 else "Submitted",
                                        filled=filled),
            fills=[SimpleNamespace(execution=SimpleNamespace(shares=filled))] if filled else [])


def make(fake, **kw):
    kw.setdefault("preview", True)
    return FuturesExecution(
        markets=[("MES", "CME", 5.0)], ib_factory=lambda: fake,
        contract_factory=lambda **k: SimpleNamespace(**k),
        order_factory=lambda action, qty: SimpleNamespace(action=action, totalQuantity=qty, tif=None),
        **kw)


# ---------------------------------------------------------------- US1: the guard set

def test_preview_places_nothing():
    fake = _FakeIB()
    rep = make(fake).rebalance({"MES": 3}, asof=TODAY)
    assert rep.applied is False
    assert fake.placeOrder_calls == 0


def test_preview_reports_the_orders_it_would_have_placed():
    rep = make(_FakeIB()).rebalance({"MES": 3}, asof=TODAY)
    assert rep.orders, "preview must still say what it intended"


def test_placement_requires_explicit_confirmation():
    fake = _FakeIB()
    with pytest.raises(RuntimeError, match="confirm"):
        make(fake, preview=False).rebalance({"MES": 3}, asof=TODAY)
    assert fake.placeOrder_calls == 0


def test_a_non_paper_account_is_refused_without_the_live_gate():
    fake = _FakeIB(acct="U1234567")
    with pytest.raises(RuntimeError, match="non-paper"):
        make(fake, preview=False, confirm=True).rebalance({"MES": 3}, asof=TODAY)
    assert fake.placeOrder_calls == 0


def test_the_live_gate_can_be_opened_deliberately():
    fake = _FakeIB(acct="U1234567")
    rep = make(fake, preview=False, confirm=True, allow_live=True).rebalance({"MES": 3}, asof=TODAY)
    assert rep.applied is True


def test_placement_on_a_paper_account_places_the_orders():
    fake = _FakeIB()
    rep = make(fake, preview=False, confirm=True).rebalance({"MES": 3}, asof=TODAY)
    assert rep.applied is True
    assert fake.placeOrder_calls == 1
    assert fake.placed[0][1] == "BUY" and fake.placed[0][2] == 3


def test_a_short_target_sells():
    fake = _FakeIB()
    make(fake, preview=False, confirm=True).rebalance({"MES": -2}, asof=TODAY)
    assert fake.placed[0][1] == "SELL" and fake.placed[0][2] == 2


# ---------------------------------------------------------------- reconciliation

def test_an_unchanged_target_places_nothing():
    held = _FakeIB().reqContractDetails(SimpleNamespace(symbol="MES", exchange="CME"))
    front = next(c.contract for c in held if c.contract.lastTradeDateOrContractMonth == FRONT.strftime("%Y%m%d"))
    fake = _FakeIB(positions=[_Pos(front.conId, 3)])
    rep = make(fake, preview=False, confirm=True).rebalance({"MES": 3}, asof=TODAY)
    assert fake.placeOrder_calls == 0
    assert rep.orders == {}


def test_a_roll_closes_the_old_contract_and_opens_the_new():
    details = _FakeIB().reqContractDetails(SimpleNamespace(symbol="MES", exchange="CME"))
    near = next(c.contract for c in details if c.contract.lastTradeDateOrContractMonth == NEAR.strftime("%Y%m%d"))
    fake = _FakeIB(positions=[_Pos(near.conId, 3)])
    make(fake, preview=False, confirm=True).rebalance({"MES": 3}, asof=TODAY)
    actions = sorted(p[1] for p in fake.placed)
    assert actions == ["BUY", "SELL"], "a roll is a matched pair"
    assert sum(q if a == "BUY" else -q for _, a, q in fake.placed) == 0, "net exposure unchanged"


# ---------------------------------------------------------------- caps and floors

def test_the_per_order_cap_raises_before_any_order_is_placed():
    """An atomic pre-pass, as basket.py was fixed to be — a breach on a later market must not leave
    earlier ones already placed."""
    fake = _FakeIB()
    ex = FuturesExecution(
        markets=[("A", "CME", 5.0), ("B", "CME", 5.0)], preview=False, confirm=True,
        max_order_frac=0.10, ib_factory=lambda: fake,
        contract_factory=lambda **k: SimpleNamespace(**k),
        order_factory=lambda action, qty: SimpleNamespace(action=action, totalQuantity=qty, tif=None))
    with pytest.raises(RuntimeError, match="max_order_frac"):
        ex.rebalance({"A": 1, "B": 500}, risk_base=100_000, asof=TODAY)
    assert fake.placeOrder_calls == 0


def test_placement_is_refused_when_it_would_breach_the_margin_floor():
    fake = _FakeIB(available=1_000.0)
    with pytest.raises(RuntimeError, match="available funds"):
        make(fake, preview=False, confirm=True, min_available_funds=50_000.0).rebalance(
            {"MES": 3}, asof=TODAY)
    assert fake.placeOrder_calls == 0


def test_ample_margin_permits_placement():
    fake = _FakeIB(available=750_000.0)
    rep = make(fake, preview=False, confirm=True, min_available_funds=50_000.0).rebalance(
        {"MES": 3}, asof=TODAY)
    assert rep.applied is True


# ---------------------------------------------------------------- failure handling

def test_a_midbatch_failure_unwinds_and_re_raises_without_masking():
    fake = _FakeIB()
    fake._fail_on = 2
    ex = FuturesExecution(
        markets=[("A", "CME", 5.0), ("B", "CME", 5.0)], preview=False, confirm=True,
        ib_factory=lambda: fake, contract_factory=lambda **k: SimpleNamespace(**k),
        order_factory=lambda action, qty: SimpleNamespace(action=action, totalQuantity=qty, tif=None))
    with pytest.raises(RuntimeError, match="VERIFY POSITIONS"):
        ex.rebalance({"A": 2, "B": 2}, asof=TODAY)
    assert fake.placeOrder_calls >= 2


def test_the_unwind_never_raises_even_when_it_fails():
    class _Hostile(_FakeIB):
        def cancelOrder(self, order):
            raise RuntimeError("cancel exploded")

    fake = _Hostile()
    fake._fail_on = 2
    fake._fill_frac = 0.5
    ex = FuturesExecution(
        markets=[("A", "CME", 5.0), ("B", "CME", 5.0)], preview=False, confirm=True,
        ib_factory=lambda: fake, contract_factory=lambda **k: SimpleNamespace(**k),
        order_factory=lambda action, qty: SimpleNamespace(action=action, totalQuantity=qty, tif=None))
    with pytest.raises(RuntimeError, match="VERIFY POSITIONS"):
        ex.rebalance({"A": 2, "B": 2}, asof=TODAY)   # must be the placement error, not the cancel one


def test_a_partial_fill_is_reported_as_incomplete():
    fake = _FakeIB()
    fake._fill_frac = 0.5
    rep = make(fake, preview=False, confirm=True).rebalance({"MES": 4}, asof=TODAY)
    assert rep.complete is False


def test_no_tradeable_contract_is_reported_rather_than_guessed():
    """Every listed expiry inside the roll window: close out, open nothing."""
    fake = _FakeIB(expiries=[TODAY + timedelta(days=2)])
    rep = make(fake).rebalance({"MES": 3}, asof=TODAY)
    assert rep.orders == {} or all(v < 0 for v in rep.orders.values())
