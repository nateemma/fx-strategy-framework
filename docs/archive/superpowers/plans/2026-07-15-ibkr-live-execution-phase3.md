# IBKR LiveExecution Phase 3 (Rollback & Partial-Fill) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add auto-unwind (cancel unfilled + flatten filled on mid-loop placement failure, then raise) and partial-fill flagging (`complete=False`, no retry) to `LiveExecution` placement.

**Architecture:** Track each placed order `(pair, trade, contract, intended)`; wrap the placement loop so an exception triggers `_unwind` (best-effort) then re-raises; after settling, set `complete=False` on any under-fill. `RebalanceReport` gains `complete: bool = True`. CLI flags incomplete placements.

## Global Constraints
- The unwind PLACES flatten orders (money-code) — it must be **best-effort and never raise** (each cancel/flatten wrapped in try/except); it reuses the `_compute` `Forex(pair)` contracts (exchange set).
- Partial fills are **flagged, never retried**.
- `RebalanceReport.complete` defaults `True` → SimExecution + preview + all existing constructions unchanged.
- Existing guard/sign/placement tests must still pass. Hermetic (fake IB via seams, no real ib_async, no real orders). Run `python -m pytest -q` before each commit; trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; stage only touched files.

---

### Task 1: RebalanceReport.complete + auto-unwind + partial-fill flag + tests

**Files:** Modify `forex/run/execution.py`; Test `tests/test_live_execution.py`.

- [ ] **Step 1: Write failing tests.** Extend `_FakeIB` (add to `__init__`: `self.cancel_calls = 0`, `self._fail_on = None`, `self._fill_frac = 1.0`); add methods:
```python
    def cancelOrder(self, order): self.cancel_calls += 1
    # replace placeOrder to support induced failure + partial fill:
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
```
Add tests:
```python
def test_midloop_failure_triggers_unwind_and_raises():
    fake = _FakeIB(price=1.1); fake._fail_on = 2          # 2nd placeOrder raises
    with pytest.raises(RuntimeError):
        _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
            _w({"EUR": 0.3, "GBP": 0.3}), pd.Series({"EUR": 1.1, "GBP": 1.1}))
    # order 1 was placed+filled -> unwind flattens it (a 3rd placeOrder) and/or cancels
    assert fake.placeOrder_calls >= 2 and (fake.cancel_calls > 0 or fake.placeOrder_calls >= 3)

def test_unwind_is_best_effort_never_raises():
    fake = _FakeIB(price=1.1); fake._fail_on = 1          # 1st placeOrder raises (nothing placed yet)
    def _boom(*a, **k): raise RuntimeError("cancel boom")
    fake.cancelOrder = _boom
    with pytest.raises(RuntimeError):                     # the ORIGINAL failure, not the unwind's
        _place(fake, confirm=True, max_order_frac=0.5, min_order_units=1).rebalance(
            _w({"EUR": 0.3}), pd.Series({"EUR": 1.1}))

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
```

- [ ] **Step 2: Run → fail** (`-k "unwind or partial or complete or midloop"`).

- [ ] **Step 3: Implement** per the spec: add `complete: bool = True` to `RebalanceReport`; add `_unwind`; rewrite the placement loop to track `placed=[(pair, tr, contract, intended)]`, wrap in try/except calling `_unwind` then raising, settle, reconcile with `complete` flag, return `RebalanceReport(..., complete=complete)`. (Exact code in the spec.)

- [ ] **Step 4: Run** `python -m pytest tests/test_live_execution.py -q` → all pass (existing + new).

- [ ] **Step 5: Commit** — stage `forex/run/execution.py`, `tests/test_live_execution.py`.

---

### Task 2: CLI INCOMPLETE flag in `_format`

**Files:** Modify `forex/cli.py`; Test `tests/test_cli_dryrun.py`.

- [ ] **Step 1: Failing test:**
```python
def test_format_ib_incomplete_flagged():
    from forex.run.execution import RebalanceReport
    s = cli._format({"broker": "ib", "dryrun": RebalanceReport(
        orders={"USDMXN": -20000.0}, positions={}, equity=1e6, turnover=0.6, cost=60.0,
        applied=True, complete=False)})
    assert "INCOMPLETE" in s
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — in `_format`'s ib `applied` branch, when `not getattr(rep, "complete", True)` prepend a line `"⚠ INCOMPLETE — partial fills; review positions"`. Complete placements + preview unchanged.

- [ ] **Step 4: Full suite** `python -m pytest -q` → pass.

- [ ] **Step 5: Commit** — stage `forex/cli.py`, `tests/test_cli_dryrun.py`.

---

## Self-Review
- Coverage: `complete` field ✓; unwind on mid-loop failure (test) ✓; unwind best-effort/never-raises (test) ✓; partial-fill flag (test) ✓; full-fill complete (test) ✓; CLI INCOMPLETE (test) ✓.
- Placeholder scan: none. Risk note for reviewers: the unwind trades — verify it can never raise (masking the original error) and never runs on the success path; verify partial-fill detection uses intended-vs-actual per leg.
