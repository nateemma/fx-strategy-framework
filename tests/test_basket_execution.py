import math
import pandas as pd, pytest
from types import SimpleNamespace
from forex.run.basket import BasketExecution

class _Val:
    def __init__(self, tag, value): self.tag, self.value = tag, value
class _Contract:
    def __init__(self, conId): self.conId = conId
class _Pos:
    def __init__(self, conId, position): self.contract, self.position = _Contract(conId), position
class _Bar:
    def __init__(self, close, date): self.close, self.date = close, date
class _Event:
    def __iadd__(self, fn): return self

class _FakeIB:
    """Records calls; provides deterministic account/positions/prices per symbol (keyed off
    contract.sym, set by the injected contract_factory). Any order call is logged in .placed."""
    def __init__(self, nav=1_000_000.0, positions=None, prices=None):
        self._nav = nav
        self._positions = positions or []
        self._prices = prices or {"SPY": 400.0, "TLT": 90.0, "IEF": 95.0, "GLD": 180.0, "DBC": 22.0}
        self.errorEvent = _Event(); self.placeOrder_calls = 0; self._conid = 100
        self.placed = []; self._acct = "DU123456"
        self.cancel_calls = 0; self._fail_on = None; self._fill_frac = 1.0
    def connect(self, *a, **k): self.connected = True
    def disconnect(self): self.connected = False
    def accountSummary(self): return [_Val("NetLiquidation", str(self._nav))]
    def positions(self): return self._positions
    def reqPositions(self): pass
    def qualifyContracts(self, c):
        self._conid += 1; c.conId = self._conid; return [c]
    def reqHistoricalData(self, c, *a, **k):
        base = self._prices[c.sym]
        return [_Bar(base + 0.5 * math.sin(i / 5.0), i) for i in range(65)]
    def managedAccounts(self): return [self._acct]
    def sleep(self, secs): pass
    def cancelOrder(self, order): self.cancel_calls += 1
    def placeOrder(self, contract, order):
        self.placeOrder_calls += 1
        self.placed.append((contract.sym, order.action, order.totalQuantity, getattr(order, "tif", None)))
        if self._fail_on is not None and self.placeOrder_calls == self._fail_on:
            raise RuntimeError("induced placeOrder failure")
        filled = order.totalQuantity * self._fill_frac
        return SimpleNamespace(
            orderStatus=SimpleNamespace(status="Filled" if self._fill_frac >= 1.0 else "Submitted", filled=filled),
            order=order,
            fills=[SimpleNamespace(execution=SimpleNamespace(shares=filled))] if filled else [])

def _cf(sym, exch, ccy): return SimpleNamespace(sym=sym)

def _fake_order(action, qty): return SimpleNamespace(action=action, totalQuantity=qty)

def _ex(fake, **kw):
    return BasketExecution(ib_factory=lambda: fake, contract_factory=_cf, order_factory=_fake_order, **kw)

def test_preview_places_nothing():
    fake = _FakeIB()
    rep = _ex(fake, symbols=("SPY", "TLT"), preview=True).rebalance(100_000.0)
    assert rep.applied is False
    assert fake.placeOrder_calls == 0

def test_placement_happy_path_buys_and_tif():
    fake = _FakeIB()
    rep = _ex(fake, symbols=("SPY", "TLT"), preview=False, confirm=True,
              min_order_usd=1.0, max_order_frac=0.9).rebalance(100_000.0)
    assert rep.applied is True
    assert fake.placeOrder_calls == 2
    for sym, action, qty, tif in fake.placed:
        assert action == "BUY" and tif == "DAY" and qty > 0
    assert rep.orders["SPY"] > 0 and rep.orders["TLT"] > 0

def test_reconcile_no_overtrade_when_positions_match_target():
    # learn the target shares from a preview run, then seed a fresh fake with a matching position
    fake1 = _FakeIB(prices={"SPY": 400.0})
    preview = _ex(fake1, symbols=("SPY",), preview=True).rebalance(100_000.0)
    target = preview.positions["SPY"]

    fake2 = _FakeIB(prices={"SPY": 400.0})
    fake2._positions = [_Pos(101, target)]   # qualifyContracts assigns conId 101 to the sole symbol
    rep = _ex(fake2, symbols=("SPY",), preview=False, confirm=True, min_order_usd=1.0).rebalance(100_000.0)
    assert fake2.placeOrder_calls == 0
    assert rep.orders == {}

def test_non_paper_account_blocked_without_allow_live():
    fake = _FakeIB(); fake._acct = "U1234567"
    with pytest.raises(RuntimeError):
        _ex(fake, symbols=("SPY",), preview=False, confirm=True).rebalance(100_000.0)
    assert fake.placeOrder_calls == 0

def test_per_order_cap_raises_as_a_prepass_before_any_placement():
    # TLT (low price -> high relative vol -> small weight, within cap) then SPY (high price -> low
    # relative vol -> large weight, breaches cap): the LATER symbol breaches, proving the cap check
    # is a pre-pass over ALL orders (mirrors execution.py) rather than checked inside the placement
    # loop -- if it weren't, TLT would already be placed before SPY's breach is discovered.
    fake = _FakeIB(prices={"TLT": 50.0, "SPY": 400.0})
    with pytest.raises(RuntimeError):
        _ex(fake, symbols=("TLT", "SPY"), preview=False, confirm=True,
            min_order_usd=1.0, max_order_frac=0.5).rebalance(100_000.0)
    assert fake.placeOrder_calls == 0

def test_sub_min_order_skipped_and_recorded():
    fake = _FakeIB(prices={"SPY": 400.0})
    rep = _ex(fake, symbols=("SPY",), preview=False, confirm=True,
              min_order_usd=10**9, max_order_frac=1.5).rebalance(100_000.0)
    assert fake.placeOrder_calls == 0
    assert "SPY" in rep.skipped

def test_partial_fill_marks_incomplete():
    fake = _FakeIB(prices={"SPY": 400.0, "TLT": 90.0})
    fake._fill_frac = 0.5
    rep = _ex(fake, symbols=("SPY", "TLT"), preview=False, confirm=True,
              min_order_usd=1.0, max_order_frac=0.9).rebalance(100_000.0)
    assert rep.applied is True
    assert rep.complete is False
    for sym, intended in rep.positions.items():
        if sym in rep.orders:
            assert abs(rep.orders[sym]) < intended

def test_midbatch_failure_triggers_unwind_and_raises():
    fake = _FakeIB(prices={"SPY": 400.0, "TLT": 400.0})  # equal prices/vol shape -> both legs sizable
    fake._fail_on = 2
    with pytest.raises(RuntimeError, match="VERIFY POSITIONS"):
        _ex(fake, symbols=("SPY", "TLT"), preview=False, confirm=True,
            min_order_usd=1.0, max_order_frac=0.9).rebalance(100_000.0)
    assert fake.placeOrder_calls >= 3           # order1 placed, order2 fails, unwind flattens order1
    assert fake.placed[-1][1] == "SELL"         # unwind flattened the filled BUY with a SELL
