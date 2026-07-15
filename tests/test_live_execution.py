import pandas as pd, pytest
from types import SimpleNamespace
from forex.run.execution import LiveExecution

class _Val:
    def __init__(self, tag, value): self.tag, self.value = tag, value
class _Contract:
    def __init__(self, conId): self.conId = conId
class _Pos:
    def __init__(self, conId, position): self.contract, self.position = _Contract(conId), position
class _Bar:
    def __init__(self, close): self.close = close
class _Event:
    def __iadd__(self, fn): return self
class _FakeIB:
    """Records calls; provides deterministic account/positions/prices. Any order call would be logged."""
    def __init__(self, nav=1_000_000.0, positions=None, price=2.0):
        self._nav, self._positions, self._price = nav, positions or [], price
        self.errorEvent = _Event(); self.placeOrder_calls = 0; self._conid = 100
        self.placed = []; self._acct = "DU123456"
    def connect(self, *a, **k): self.connected = True
    def disconnect(self): self.connected = False
    def reqMarketDataType(self, *a): pass
    def accountSummary(self): return [_Val("NetLiquidation", str(self._nav))]
    def positions(self): return self._positions
    def qualifyContracts(self, c):
        self._conid += 1; c.conId = self._conid; c.exchange = "IDEALPRO"; return [c]
    def reqHistoricalData(self, *a, **k): return [_Bar(self._price)]
    def managedAccounts(self): return [getattr(self, "_acct", "DU123456")]
    def placeOrder(self, contract, order):
        self.placeOrder_calls += 1
        self.placed.append((getattr(contract, "pair", None), order.action, order.totalQuantity, getattr(order, "tif", None)))
        return SimpleNamespace(orderStatus=SimpleNamespace(status="Filled", filled=order.totalQuantity,
                                                           avgFillPrice=self._price), order=order)

def _w(d): return pd.Series(d)

def _live(fake, preview=True):
    # inject BOTH the fake IB and a fake contract factory so the sign tests run WITHOUT ib_async
    return LiveExecution(preview=preview, ib_factory=lambda: fake,
                         contract_factory=lambda pair: SimpleNamespace(pair=pair))

def test_long_c_usd_pair_units_and_sign():
    # EUR spot_invert=False -> EUR.USD, base EUR, price USD/EUR=1.1; long 0.5 of NAV 1e6 => buy 500000/1.1 EUR
    fake = _FakeIB(nav=1_000_000.0, price=1.1)
    ex = _live(fake)
    rep = ex.rebalance(_w({"EUR": 0.5}), pd.Series({"EUR": 1.1}))
    assert abs(rep.orders["EURUSD"] - (0.5 * 1_000_000 / 1.1)) < 1e-6   # positive => BUY
    assert rep.applied is False and fake.placeOrder_calls == 0

def test_long_usd_c_pair_units_and_sign():
    # MXN spot_invert=True -> USD.MXN, base USD; long 0.5 of NAV 1e6 => target USD units = -(0.5*1e6) => SELL USD.MXN
    fake = _FakeIB(nav=1_000_000.0, price=18.0)
    ex = _live(fake)
    rep = ex.rebalance(_w({"MXN": 0.5}), pd.Series({"MXN": 1/18.0}))
    assert abs(rep.orders["USDMXN"] - (-0.5 * 1_000_000)) < 1e-6        # negative => SELL (long MXN)
    assert rep.applied is False

def test_short_flips_sign():
    fake = _FakeIB(nav=1_000_000.0, price=1.1)
    ex = _live(fake)
    rep = ex.rebalance(_w({"EUR": -0.5}), pd.Series({"EUR": 1.1}))
    assert rep.orders["EURUSD"] < 0                                     # short C.USD => SELL

def test_preview_false_raises_and_never_places_order():
    fake = _FakeIB()
    ex = _live(fake, preview=False)
    with pytest.raises(RuntimeError):
        ex.rebalance(_w({"EUR": 0.5}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0

def test_current_position_nets_against_target():
    # already hold the exact target EUR units -> order ~0
    fake = _FakeIB(nav=1_000_000.0, price=1.1)
    target_units = 0.5 * 1_000_000 / 1.1
    # qualifyContracts assigns conId 101 to the first (only) pair
    fake._positions = [_Pos(101, target_units)]
    ex = _live(fake)
    rep = ex.rebalance(_w({"EUR": 0.5}), pd.Series({"EUR": 1.1}))
    assert abs(rep.orders["EURUSD"]) < 1e-6

# ---- Phase 2: placement tests ----

def _fake_order(action, qty):
    return SimpleNamespace(action=action, totalQuantity=qty)

def _place(fake, **kw):
    return LiveExecution(preview=False, ib_factory=lambda: fake,
                         contract_factory=lambda pair: SimpleNamespace(pair=pair),
                         order_factory=_fake_order, **kw)

def test_confirm_required_blocks_placement():
    fake = _FakeIB()
    with pytest.raises(RuntimeError):
        _place(fake, confirm=False).rebalance(_w({"EUR": 0.2}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0

def test_non_paper_account_blocked():
    fake = _FakeIB(); fake._acct = "U1234567"          # live-style account
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True).rebalance(_w({"EUR": 0.2}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0

def test_per_order_cap_rejects_whole_rebalance():
    fake = _FakeIB(price=1.1)                            # EUR 0.5 -> 50% > 0.25 cap
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True, max_order_frac=0.25).rebalance(_w({"EUR": 0.5}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0

def test_gross_cap_rejects():
    fake = _FakeIB(price=1.1)                            # gross sum|w| = 3.0 > 2.5
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True, max_order_frac=0.9, max_gross=2.5).rebalance(
            _w({"EUR": 1.0, "GBP": 1.0, "AUD": 1.0}), pd.Series({"EUR": 1.1, "GBP": 1.1, "AUD": 1.1}))
    assert fake.placeOrder_calls == 0

def test_placement_happy_path_signs_and_tif():
    fake = _FakeIB(price=1.1)
    rep = _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
        _w({"EUR": 0.3, "MXN": -0.3}), pd.Series({"EUR": 1.1, "MXN": 1/18.0}))
    assert rep.applied is True and fake.placeOrder_calls == 2
    placed = {p[0]: p for p in fake.placed}
    assert placed["EURUSD"][1] == "BUY" and placed["EURUSD"][3] == "DAY"     # long C.USD -> BUY, TIF set
    assert placed["USDMXN"][1] == "BUY"    # short MXN: w=-0.3, USD.C target=-(w*N)=+, order>0 -> BUY USD.MXN

def test_min_order_skipped():
    fake = _FakeIB(price=1.1)
    _place(fake, confirm=True, max_order_frac=0.5, min_order_units=10**9).rebalance(
        _w({"EUR": 0.3}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0      # order below the (absurd) min -> skipped
