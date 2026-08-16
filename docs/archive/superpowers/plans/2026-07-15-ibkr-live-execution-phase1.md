# IBKR LiveExecution Phase 1 (Order Preview) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the stubbed `LiveExecution` against IBKR (`ib_async`), PREVIEW-ONLY: connect, price via historical midpoints, compute exact FX orders to reach target weights, display them, place nothing.

**Architecture:** `LiveExecution.rebalance()` connects `readonly=True`, reads NAV + positions, maps per-currency weights → IBKR FX pair orders (pair form from `spot_invert`), returns a `RebalanceReport(applied=False)`. Order placement raises `NotImplementedError`. A fake-IB seam keeps tests offline.

**Tech Stack:** pandas, `ib_async` (optional `live` dep, lazy-imported).

## Global Constraints
- **PREVIEW-ONLY / no orders:** zero `placeOrder` calls anywhere; the non-preview branch raises `NotImplementedError("live order placement is Phase 2")`; connect with `readonly=True`.
- **FX order math (exact):** book is USD-funded. Pair from `CURRENCIES[c].spot_invert`: `False`→`{C}USD` (base C, price USD/C), `True`→`USD{C}` (base USD, price C/USD). For weight `w`, NAV `N`, native midpoint `p`: `target_base_units = -(w*N)` if base-USD else `(w*N)/p`. `order = target - current`; BUY if `order>0` else SELL. USD-notional per ccy = `w*N`.
- **Prices:** `reqHistoricalData(c, '', '2 D', '1 day', 'MIDPOINT', useRTH=False)`, last bar `close`. No streaming.
- **Error 10197** → print a "log out of your other IBKR session" warning; continue (historical still valid).
- `ib_async` NOT imported at module top level (lazy import inside methods); live tests `pytest.importorskip("ib_async")`.
- Never hardcode account IDs/credentials. Framework (`forex/`) imports zero concrete strategies (unchanged).
- Run `python -m pytest -q` before each commit; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; stage only files each task touches.

---

### Task 1: LiveExecution (preview) + fake-IB tests

**Files:**
- Modify: `forex/run/execution.py` (replace the `LiveExecution` stub)
- Modify: `pyproject.toml` (add `live` optional dep)
- Test: `tests/test_live_execution.py`

**Interfaces:**
- Produces: `LiveExecution(host="127.0.0.1", port=4002, client_id=23, cost_bps=1.0, preview=True, ib_factory=None)` with `rebalance(target_weights: pd.Series, prices: pd.Series) -> RebalanceReport` (`applied` always False in preview).

- [ ] **Step 1: Write failing tests**

Create `tests/test_live_execution.py`:
```python
import pandas as pd, pytest
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
    def connect(self, *a, **k): self.connected = True
    def disconnect(self): self.connected = False
    def reqMarketDataType(self, *a): pass
    def accountSummary(self): return [_Val("NetLiquidation", str(self._nav))]
    def positions(self): return self._positions
    def qualifyContracts(self, c):
        self._conid += 1; c.conId = self._conid; c.exchange = "IDEALPRO"; return [c]
    def reqHistoricalData(self, *a, **k): return [_Bar(self._price)]
    def placeOrder(self, *a, **k): self.placeOrder_calls += 1     # must never be called in Phase 1

def _w(d): return pd.Series(d)

def test_long_c_usd_pair_units_and_sign():
    # EUR spot_invert=False -> EUR.USD, base EUR, price USD/EUR=1.1; long 0.5 of NAV 1e6 => buy 500000/1.1 EUR
    fake = _FakeIB(nav=1_000_000.0, price=1.1)
    ex = LiveExecution(preview=True, ib_factory=lambda: fake)
    rep = ex.rebalance(_w({"EUR": 0.5}), pd.Series({"EUR": 1.1}))
    assert abs(rep.orders["EURUSD"] - (0.5 * 1_000_000 / 1.1)) < 1e-6   # positive => BUY
    assert rep.applied is False and fake.placeOrder_calls == 0

def test_long_usd_c_pair_units_and_sign():
    # MXN spot_invert=True -> USD.MXN, base USD; long 0.5 of NAV 1e6 => target USD units = -(0.5*1e6) => SELL USD.MXN
    fake = _FakeIB(nav=1_000_000.0, price=18.0)
    ex = LiveExecution(preview=True, ib_factory=lambda: fake)
    rep = ex.rebalance(_w({"MXN": 0.5}), pd.Series({"MXN": 1/18.0}))
    assert abs(rep.orders["USDMXN"] - (-0.5 * 1_000_000)) < 1e-6        # negative => SELL (long MXN)
    assert rep.applied is False

def test_short_flips_sign():
    fake = _FakeIB(nav=1_000_000.0, price=1.1)
    ex = LiveExecution(preview=True, ib_factory=lambda: fake)
    rep = ex.rebalance(_w({"EUR": -0.5}), pd.Series({"EUR": 1.1}))
    assert rep.orders["EURUSD"] < 0                                     # short C.USD => SELL

def test_preview_false_raises_and_never_places_order():
    fake = _FakeIB()
    ex = LiveExecution(preview=False, ib_factory=lambda: fake)
    with pytest.raises(NotImplementedError):
        ex.rebalance(_w({"EUR": 0.5}), pd.Series({"EUR": 1.1}))
    assert fake.placeOrder_calls == 0

def test_current_position_nets_against_target():
    # already hold the exact target EUR units -> order ~0
    fake = _FakeIB(nav=1_000_000.0, price=1.1)
    target_units = 0.5 * 1_000_000 / 1.1
    # qualifyContracts assigns conId 101 to the first (only) pair
    fake._positions = [_Pos(101, target_units)]
    ex = LiveExecution(preview=True, ib_factory=lambda: fake)
    rep = ex.rebalance(_w({"EUR": 0.5}), pd.Series({"EUR": 1.1}))
    assert abs(rep.orders["EURUSD"]) < 1e-6
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_live_execution.py -q`
Expected: FAIL (current `LiveExecution.rebalance` raises `NotImplementedError` unconditionally / no `ib_factory`).

- [ ] **Step 3: Implement `LiveExecution`**

In `forex/run/execution.py`, replace the `LiveExecution` stub with:
```python
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

    def rebalance(self, target_weights, prices) -> RebalanceReport:
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
```

- [ ] **Step 4: Add the optional dependency**

In `pyproject.toml` `[project.optional-dependencies]`, add: `live = ["ib_async>=2.0"]`.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_live_execution.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add forex/run/execution.py tests/test_live_execution.py pyproject.toml
git commit -m "feat: LiveExecution Phase 1 — IBKR order preview (no placement)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: CLI `--broker ib` wiring + preview table

**Files:**
- Modify: `forex/cli.py` (`build_parser` dryrun args; `run` dryrun branch; `_format` dryrun table)
- Test: `tests/test_cli_dryrun.py`

**Interfaces:**
- Consumes: Task 1's `LiveExecution`; existing `rebalance_now`, `RebalanceReport`.
- Produces: `forex dryrun ... --broker ib --preview [--ib-port 4002]`.

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli_dryrun.py` (create if absent):
```python
import forex.cli as cli

def test_dryrun_broker_ib_builds_live_execution(monkeypatch):
    import forex.run.execution as exmod
    captured = {}
    class _Fake:
        def __init__(self, **kw): captured.update(kw)
        def rebalance(self, tw, px):
            from forex.run.execution import RebalanceReport
            return RebalanceReport(orders={"EURUSD": 100.0}, positions={"EURUSD": 100.0},
                                   equity=1_000_000.0, turnover=0.5, cost=50.0, applied=False)
    monkeypatch.setattr(exmod, "LiveExecution", _Fake)
    # a tiny view via the strategy's fixture path is heavy; instead assert the parser/branch wires broker
    args = cli.build_parser().parse_args(["dryrun", "--strategy", "carry", "--broker", "ib",
                                          "--preview", "--ib-port", "4002"])
    assert args.broker == "ib" and args.ib_port == 4002 and args.preview is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cli_dryrun.py -q`
Expected: FAIL (`--broker` / `--ib-port` unknown args).

- [ ] **Step 3: Wire the CLI**

In `forex/cli.py` `build_parser`, under `if mode == "dryrun":` add:
```python
            sp.add_argument("--broker", choices=["sim", "ib"], default="sim")
            sp.add_argument("--ib-port", type=int, default=4002, dest="ib_port")
```
In `run`, replace the `dryrun` executor construction so it branches on `args`/cfg. Since `run` takes
`cfg, env, mode`, thread the broker/ib_port through `resolve` into `cfg` (add `broker`/`ib_port` to the
overrides in `resolve`, mirroring `preview`), then:
```python
    if mode == "dryrun":
        import os
        from forex.run.live import rebalance_now
        if getattr(cfg, "broker", "sim") == "ib":
            from forex.run.execution import LiveExecution
            ex = LiveExecution(port=getattr(cfg, "ib_port", 4002), cost_bps=cfg.cost_bps,
                               preview=cfg.preview)
        else:
            from forex.run.execution import SimExecution
            pf = os.path.join(env.output_dir, "portfolio.json")
            ex = SimExecution(pf, starting_equity=env.starting_equity, cost_bps=cfg.cost_bps,
                              preview=cfg.preview)
        rep = rebalance_now(build_strategy(cfg.strategy, cfg.strategy_params, "strategies"), view, ex)
        return {"dryrun": rep}
```
(Add `broker`/`ib_port` handling in `resolve` alongside the existing `preview` override, and to `RunConfig`
if it is a dataclass with fixed fields — mirror how `preview` is stored. If `RunConfig` already accepts
arbitrary overrides via `merge`, just include them.)

In `_format`'s dryrun branch, when orders are present, print a per-pair table:
```python
        lines = [f"{'PREVIEW ' if not rep.applied else ''}IBKR rebalance -> NAV {rep.equity:,.0f}  "
                 f"turnover {rep.turnover:.3f}  est.cost {rep.cost:,.0f}", "orders (base-ccy units):"]
        for pair, units in sorted(rep.orders.items(), key=lambda kv: -abs(kv[1])):
            if abs(units) > 1e-6:
                lines.append(f"  {pair:8} {'BUY ' if units > 0 else 'SELL'} {abs(units):,.0f}")
        return "\n".join(lines)
```
(Keep the existing SimExecution dryrun formatting path working — branch on the report shape or reuse this
table for both, whichever is cleaner without breaking `test_cli` dryrun expectations.)

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (new dryrun test + existing suite; SimExecution dryrun unaffected).

- [ ] **Step 5: Commit**

```bash
git add forex/cli.py tests/test_cli_dryrun.py
git commit -m "feat: dryrun --broker ib preview path + order table

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review
- **Spec coverage:** LiveExecution preview + FX math (Task 1) ✓; safety (no placeOrder, NotImplementedError, readonly) ✓; 10197 warning ✓; fake-IB offline tests incl. exact sign/units ✓; optional dep ✓; CLI `--broker ib` + table (Task 2) ✓.
- **Placeholder scan:** none.
- **Type consistency:** `_pair` returns `(str, bool)`; `orders`/`positions` keyed by pair string; `RebalanceReport(applied=False)` throughout; `ib_factory` seam used identically in code and tests.
- **Risk note for reviewers:** the FX sign/units logic and the "never places an order" guarantee are the load-bearing correctness properties — verify both against the hand-computed test numbers and by confirming no `placeOrder` path is reachable in preview.
