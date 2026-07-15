# IBKR LiveExecution Phase 2 (Paper Order Placement) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the order-PLACEMENT path in `LiveExecution` (non-preview), paper-only, behind five software guards. Factor the Phase-1 order math into a shared `_compute` used by both preview and placement.

**Architecture:** `rebalance` keeps the Phase-1 preview path (readonly, `applied=False`). The placement path: confirm-guard → connect `readonly=False` → **DU-prefix account guard** → `_compute` → size caps → place market orders (explicit TIF, skip sub-min) → await fills → `applied=True`. All broker interaction is behind injectable seams so tests place ZERO real orders without `ib_async`.

**Tech Stack:** pandas, `ib_async` (lazy).

## Global Constraints
- **Guards, all must pass before any `placeOrder`:** (1) `confirm=True` else `RuntimeError` before connect; (2) after connect, account `ib.managedAccounts()[0]` must start with `DU` (paper) else `allow_live=True`, else raise; (3) per-order `|notional|/NAV ≤ max_order_frac` (default 0.25) AND gross `sum|w| ≤ max_gross` (default 2.5), else raise (place nothing); (4) skip orders `< min_order_units` (default 20000); (5) every order gets explicit `order.tif` (default "DAY").
- **Preview path unchanged** — still `readonly=True`, `applied=False`, zero orders. The Phase-1 sign math (now in `_compute`) must stay byte-identical.
- **Hermetic tests** — fake IB (+ `order_factory`) via seams; suite runs and all guard/sign tests pass WITHOUT `ib_async` installed; the fake records `placeOrder` calls (must be zero when a guard blocks).
- Never hardcode account IDs. Run `python -m pytest -q` before each commit; trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; stage only touched files.

---

### Task 1: `_compute` refactor + placement path + guards + tests

**Files:**
- Modify: `forex/run/execution.py`
- Test: `tests/test_live_execution.py`

**Interfaces:**
- Produces: `LiveExecution(..., confirm=False, max_order_frac=0.25, max_gross=2.5, min_order_units=20000, allow_live=False, tif="DAY", order_factory=None)`; `_compute(ib, target_weights) -> dict`; placement path in `rebalance`.

- [ ] **Step 1: Write failing tests** — extend `tests/test_live_execution.py`. Add to `_FakeIB`:
```python
    def managedAccounts(self): return [getattr(self, "_acct", "DU123456")]
    def placeOrder(self, contract, order):
        self.placeOrder_calls += 1
        self.placed.append((getattr(contract, "pair", None), order.action, order.totalQuantity, getattr(order, "tif", None)))
        from types import SimpleNamespace
        return SimpleNamespace(orderStatus=SimpleNamespace(status="Filled", filled=order.totalQuantity,
                                                           avgFillPrice=self._price), order=order)
```
(Initialise `self.placed = []` and `self._acct = "DU123456"` in `_FakeIB.__init__`; keep `placeOrder_calls`.)
Add a fake order factory and a placement `_live` variant:
```python
def _fake_order(action, qty):
    from types import SimpleNamespace
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
```

- [ ] **Step 2: Run to verify they fail** — `python -m pytest tests/test_live_execution.py -k "confirm or account or cap or placement or min_order" -q` → FAIL.

- [ ] **Step 3: Implement.** In `forex/run/execution.py`:
  - Extend `__init__` with `confirm=False, max_order_frac=0.25, max_gross=2.5, min_order_units=20000, allow_live=False, tif="DAY", order_factory=None` (store all).
  - Add `_make_order` mirroring `_make_contract` (returns `self._order_factory` or lazily `ib_async.MarketOrder`).
  - Extract the current per-currency loop into `_compute(self, ib, target_weights) -> dict` returning
    `{"nav","orders","positions","base_usd","price","contract","turnover"}` (same math + `getattr(c,"conId")` guard; also store `contract[pair]=c`, `base_usd[pair]`, `price[pair]`).
  - Rewrite `rebalance`:
```python
    def rebalance(self, target_weights, prices) -> RebalanceReport:
        competing = {"hit": False}
        def _on_err(rid, code, msg, c):
            if code == 10197: competing["hit"] = True
        if self.preview:
            ib = self._make_ib(); ib.errorEvent += _on_err
            try:
                ib.connect(self.host, self.port, clientId=self.client_id, timeout=15, readonly=True)
                c = self._compute(ib, target_weights)
                if competing["hit"]:
                    print("WARNING: competing live session (Error 10197) ...")
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
            make_order = self._make_order()
            trades = []
            for pair, units in c["orders"].items():
                if abs(units) < self.min_order_units:
                    continue
                order = make_order("BUY" if units > 0 else "SELL", round(abs(units)))
                order.tif = self.tif
                trades.append((pair, ib.placeOrder(c["contract"][pair], order)))
            fills = {}
            for pair, tr in trades:
                for _ in range(30):
                    if tr.orderStatus.status in ("Filled", "Cancelled", "ApiCancelled", "Inactive"):
                        break
                    ib.sleep(1)
                sgn = 1.0 if tr.order.action == "BUY" else -1.0
                fills[pair] = sgn * float(tr.orderStatus.filled)
            cost = (self.cost_bps / 1e4) * c["turnover"] * c["nav"]
            return RebalanceReport(orders=fills, positions=c["positions"], equity=c["nav"],
                                   turnover=c["turnover"], cost=cost, applied=True)
        finally:
            ib.disconnect()
```

- [ ] **Step 4: Run** `python -m pytest tests/test_live_execution.py -q` → all pass (Phase-1 tests + new placement tests).

- [ ] **Step 5: Commit** — stage `forex/run/execution.py`, `tests/test_live_execution.py`.

---

### Task 2: CLI placement flags + fills table

**Files:** Modify `forex/cli.py`, `forex/core/config.py`; Test `tests/test_cli_dryrun.py`.

**Interfaces:** `forex dryrun ... --broker ib --confirm [--max-order-frac F] [--allow-live]`.

- [ ] **Step 1: Failing test** — add to `tests/test_cli_dryrun.py`:
```python
def test_dryrun_ib_confirm_threads_placement_params(monkeypatch):
    import forex.run.execution as exmod
    captured = {}
    class _Fake:
        def __init__(self, **kw): captured.update(kw)
        def rebalance(self, tw, px):
            from forex.run.execution import RebalanceReport
            return RebalanceReport(orders={"USDMXN": -20000.0}, positions={}, equity=1e6,
                                   turnover=0.6, cost=60.0, applied=True)
    monkeypatch.setattr(exmod, "LiveExecution", _Fake)
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long": 1, "n_short": 1},
                            broker="ib", ib_port=4002, confirm=True, max_order_frac=0.4), EnvConfig(), "dryrun")
    assert captured["confirm"] is True and captured["max_order_frac"] == 0.4
    assert out["dryrun"].applied is True

def test_format_ib_fills_table():
    from forex.run.execution import RebalanceReport
    s = cli._format({"broker": "ib", "dryrun": RebalanceReport(
        orders={"USDMXN": -20000.0}, positions={}, equity=1e6, turnover=0.6, cost=60.0, applied=True)})
    assert "PLACED" in s and "USDMXN" in s and "SELL" in s
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement.** `build_parser` dryrun: add `--confirm` (store_true), `--max-order-frac` (type float, dest `max_order_frac`), `--allow-live` (store_true, dest `allow_live`). `resolve`: thread `confirm`/`max_order_frac`/`allow_live` into overrides (mirror `preview`, only when truthy/not-None). `RunConfig`: add fields `confirm: bool = False`, `max_order_frac: float | None = None`, `allow_live: bool = False`. In `run` dryrun ib branch, pass them:
```python
            ex = LiveExecution(port=cfg.ib_port, cost_bps=cfg.cost_bps, preview=cfg.preview,
                               confirm=getattr(cfg, "confirm", False), allow_live=getattr(cfg, "allow_live", False),
                               **({"max_order_frac": cfg.max_order_frac} if getattr(cfg, "max_order_frac", None) is not None else {}))
```
In `_format` dryrun ib branch, when `rep.applied`, header `"ORDERS PLACED -> NAV ..."` and rows show filled units BUY/SELL (same table shape as preview but "PLACED"). Keep preview (`applied=False`) header as `"PREVIEW IBKR ..."`.

- [ ] **Step 4: Full suite** `python -m pytest -q` → pass.

- [ ] **Step 5: Commit** — stage `forex/cli.py`, `forex/core/config.py`, `tests/test_cli_dryrun.py`.

---

## Self-Review
- Spec coverage: shared `_compute` ✓; 5 guards (confirm/DU-account/size-caps/min-order/TIF) each with a test ✓; preview unchanged ✓; hermetic seams (ib_factory/contract_factory/order_factory) ✓; CLI flags + fills table ✓.
- Placeholder scan: none.
- Risk note for reviewers: the guards and the "zero placeOrder when a guard blocks" property are load-bearing; verify each guard raises BEFORE any `placeOrder`, and that `_compute`'s sign math is byte-identical to Phase 1.
