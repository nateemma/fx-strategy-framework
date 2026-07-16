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
        self.cancel_calls = 0; self._fail_on = None; self._fill_frac = 1.0
    def connect(self, *a, **k): self.connected = True
    def disconnect(self): self.connected = False
    def reqMarketDataType(self, *a): pass
    def accountSummary(self): return [_Val("NetLiquidation", str(self._nav))]
    def positions(self): return self._positions
    def reqPositions(self): pass
    def qualifyContracts(self, c):
        self._conid += 1; c.conId = self._conid; c.exchange = "IDEALPRO"; return [c]
    def reqHistoricalData(self, *a, **k): return [_Bar(self._price)]
    def managedAccounts(self): return [getattr(self, "_acct", "DU123456")]
    def sleep(self, secs): pass
    def cancelOrder(self, order): self.cancel_calls += 1
    def placeOrder(self, contract, order):
        self.placeOrder_calls += 1
        self.placed.append((getattr(contract, "pair", None), order.action, order.totalQuantity, getattr(order, "tif", None)))
        if self._fail_on is not None and self.placeOrder_calls == self._fail_on:
            raise RuntimeError("induced placeOrder failure")
        filled = order.totalQuantity * self._fill_frac
        return SimpleNamespace(
            orderStatus=SimpleNamespace(status="Filled" if self._fill_frac >= 1.0 else "Submitted", filled=filled, avgFillPrice=self._price),
            order=order,
            fills=[SimpleNamespace(execution=SimpleNamespace(shares=filled, price=self._price))] if filled else [])

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

def test_odd_lot_flagged_below_idealpro_min():
    # 0.5 * 40k NAV = $20k USD notional < $25k IdealPro min -> flagged as odd-lot
    fake = _FakeIB(nav=40_000.0, price=18.0)
    rep = _live(fake).rebalance(_w({"MXN": 0.5}), pd.Series({"MXN": 1 / 18.0}))
    assert "USDMXN" in rep.odd_lot and round(rep.odd_lot["USDMXN"]) == 20000

def test_no_odd_lot_above_idealpro_min():
    fake = _FakeIB(nav=1_000_000.0, price=18.0)     # 0.5 * 1e6 = $500k, well above min
    rep = _live(fake).rebalance(_w({"MXN": 0.5}), pd.Series({"MXN": 1 / 18.0}))
    assert rep.odd_lot == {}

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

def test_gross_cap_rejects_isolated():
    # 9 legs of 0.3 -> gross 2.7 > 2.5, but each order is 30% < the 50% per-order cap: isolates the gross guard
    fake = _FakeIB(price=1.1)
    codes = ["EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK"]
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True, max_order_frac=0.5, max_gross=2.5).rebalance(
            _w({c: 0.3 for c in codes}), pd.Series({c: 1.1 for c in codes}))
    assert fake.placeOrder_calls == 0

def test_placement_happy_path_signs_and_tif():
    fake = _FakeIB(price=1.1)
    rep = _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
        _w({"EUR": 0.3, "MXN": -0.3}), pd.Series({"EUR": 1.1, "MXN": 1/18.0}))
    assert rep.applied is True and fake.placeOrder_calls == 2
    placed = {p[0]: p for p in fake.placed}
    assert placed["EURUSD"][1] == "BUY" and placed["EURUSD"][3] == "DAY"     # long C.USD -> BUY, TIF set
    assert placed["USDMXN"][1] == "BUY"    # short MXN: w=-0.3, USD.C target=-(w*N)=+, order>0 -> BUY USD.MXN
    # fill report captures BOTH legs (not under-counted) with BUY-sign, summed from executions
    assert set(rep.orders) == {"EURUSD", "USDMXN"}
    assert rep.orders["EURUSD"] > 0 and rep.orders["USDMXN"] > 0

def test_min_order_skipped():
    fake = _FakeIB(price=1.1)
    _place(fake, confirm=True, max_order_frac=0.5, min_order_units=10**9).rebalance(
        _w({"EUR": 0.3}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0      # order below the (absurd) min -> skipped

def test_nan_weight_rejected_before_placement():
    # NaN would fail the caps OPEN (NaN comparisons are False) -> must be caught up front
    fake = _FakeIB(price=1.1)
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True, max_order_frac=0.9).rebalance(
            _w({"EUR": float("nan")}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0

def test_atomic_reject_before_any_placement():
    # one leg within cap, one over -> WHOLE rebalance rejected, ZERO orders placed (not just the over one)
    fake = _FakeIB(price=1.1)
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True, max_order_frac=0.25).rebalance(
            _w({"EUR": 0.2, "MXN": 0.5}), pd.Series({"EUR": 1.1, "MXN": 1 / 18.0}))
    assert fake.placeOrder_calls == 0

# ---- Phase 3: auto-unwind + partial-fill tests ----

def test_midloop_failure_triggers_unwind_and_raises():
    fake = _FakeIB(price=1.1); fake._fail_on = 2          # 2nd placeOrder raises
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
            _w({"EUR": 0.3, "GBP": 0.3}), pd.Series({"EUR": 1.1, "GBP": 1.1}))
    # order 1 placed+filled (BUY), order 2 raises -> unwind flattens order 1 with an opposite SELL
    assert fake.placeOrder_calls >= 3            # order1, failed order2, flatten
    assert fake.placed[-1][1] == "SELL"          # the unwind flattened the filled BUY with a SELL

def test_unwind_is_best_effort_never_raises():
    # order 1 fills PARTIAL (status Submitted) so unwind tries to CANCEL it; make cancel raise.
    # The surfaced error must be the ORIGINAL placement failure, not the swallowed "cancel boom".
    fake = _FakeIB(price=1.1); fake._fail_on = 2; fake._fill_frac = 0.5
    def _boom(order): raise RuntimeError("cancel boom")
    fake.cancelOrder = _boom
    with pytest.raises(RuntimeError, match="placement failed"):
        _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
            _w({"EUR": 0.3, "GBP": 0.3}), pd.Series({"EUR": 1.1, "GBP": 1.1}))

def test_partial_fill_flags_incomplete():
    fake = _FakeIB(price=1.1); fake._fill_frac = 0.5      # each leg fills half
    rep = _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
        _w({"EUR": 0.3}), pd.Series({"EUR": 1.1}))
    assert rep.applied is True and rep.complete is False

def test_full_fill_is_complete():
    fake = _FakeIB(price=1.1)
    rep = _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
        _w({"EUR": 0.3}), pd.Series({"EUR": 1.1}))
    assert rep.complete is True
    assert fake.cancel_calls == 0 and fake.placeOrder_calls == 1   # NO unwind on the success path
