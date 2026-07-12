# Hyperopt Progress Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `forex hyperopt` report its running best config as it searches (freqtrade-style), instead of printing nothing until the run completes.

**Architecture:** `optimize()` gains an optional `on_step` callback fired once per sample; the CLI passes a closure that prints "new best" lines to stderr. The library stays presentation-agnostic and unit-testable; stdout stays clean so the final winning-config TOML remains pipeable.

**Tech Stack:** Python 3.11+, stdlib only, pytest.

## Global Constraints

- No new dependencies; stdlib only.
- `optimize()` default behavior must be byte-identical when `on_step=None` (backward compatible, still deterministic, same returned dict).
- Callback signature is exactly `on_step(i, n, score, params, improved)` — `i` 1-based, `n` = `n_samples`, `improved` True iff this sample set a new best.
- CLI prints progress ONLY on `improved`, to **stderr** (never stdout).
- Progress line format: `[<i>/<n>] new best <objective>=<score:.4f> @ {k=v, k=v, ...}` (i right-justified width 3).
- Match the existing compact code style (see `forex/run/hyperopt.py`, `forex/cli.py`).
- Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `optimize()` `on_step` callback

**Files:**
- Modify: `forex/run/hyperopt.py`
- Test: `tests/test_hyperopt.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `optimize(..., on_step=None)` — when `on_step` is provided it is called once per sample as `on_step(i, n, score, params, improved)` (`i` 1-based, `n` = `n_samples`, `score` the candidate's objective value, `params` the candidate param dict, `improved` a bool True iff this sample set a new best). Return value and all existing behavior unchanged when `on_step is None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hyperopt.py` (the file already defines `_view()` and imports `optimize`):

```python
def test_on_step_fires_once_per_sample_with_correct_flags():
    calls = []
    r = optimize("carry", _view(), train_days=250, test_days=125,
                 n_samples=8, seed=1, tune=["n_long", "n_short"],
                 on_step=lambda i, n, score, params, improved: calls.append(
                     (i, n, score, dict(params), improved)))
    # one call per sample, i is 1..n in order, n constant
    assert len(calls) == 8
    assert [c[0] for c in calls] == list(range(1, 9))
    assert all(c[1] == 8 for c in calls)
    # first sample is always a new best
    assert calls[0][4] is True
    # `improved` marks exactly the running-maximum samples
    running = float("-inf")
    for _i, _n, score, _params, improved in calls:
        assert improved == (score > running)
        if improved:
            running = score
    # the reported best equals the max improved score
    assert r["score"] == running

def test_on_step_none_is_backward_compatible():
    v = _view()
    a = optimize("carry", v, train_days=250, test_days=125, n_samples=6, seed=7,
                 tune=["n_long", "n_short"])
    b = optimize("carry", v, train_days=250, test_days=125, n_samples=6, seed=7,
                 tune=["n_long", "n_short"], on_step=None)
    assert a["best_params"] == b["best_params"] and a["score"] == b["score"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hyperopt.py -v`
Expected: FAIL — `test_on_step_fires_once_per_sample_with_correct_flags` errors with `TypeError: optimize() got an unexpected keyword argument 'on_step'`.

- [ ] **Step 3: Write minimal implementation**

Edit `forex/run/hyperopt.py`. Add the `on_step=None` parameter and fire it inside the loop; change the loop to a 1-based counter and compute `improved` before updating `best`. The full updated function:

```python
import random
from forex.strategies.registry import build_strategy
from forex.run.walkforward import walk_forward
from forex.run.backtest import backtest

def optimize(strategy_name, view, *, train_days, test_days, n_samples=200, seed=0,
             cost_bps=1.0, base_params=None, tune=None, objective="sharpe", on_step=None) -> dict:
    base_params = dict(base_params or {})
    space = build_strategy(strategy_name, base_params).search_space()
    if tune is not None:
        space = {k: space[k] for k in tune}
    rng = random.Random(seed)
    best = None
    for i in range(1, n_samples + 1):
        cand = dict(base_params)
        for k, sp in space.items():
            cand[k] = sp.sample(rng)
        wf = walk_forward(lambda c=cand: build_strategy(strategy_name, c),
                          view, train_days, test_days, cost_bps)
        score = wf.metrics.get(objective, float("-inf"))
        improved = best is None or score > best["score"]
        if improved:
            best = {"score": score, "params": cand, "oos": wf.metrics}
        if on_step is not None:
            on_step(i, n_samples, score, cand, improved)
    is_metrics = backtest(build_strategy(strategy_name, best["params"]), view, cost_bps).metrics
    return {"best_params": best["params"], "score": best["score"], "objective": objective,
            "oos": best["oos"], "in_sample": is_metrics, "n_samples": n_samples}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hyperopt.py -v`
Expected: PASS (all tests, including the pre-existing `test_optimize_returns_best_and_gap` and `test_optimize_is_deterministic`).

- [ ] **Step 5: Commit**

```bash
git add forex/run/hyperopt.py tests/test_hyperopt.py
git commit -m "feat: optimize() on_step per-sample progress callback

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: CLI prints new-best progress to stderr

**Files:**
- Modify: `forex/cli.py` (the `if mode == "hyperopt":` branch of `run()`)
- Test: `tests/test_cli_hyperopt.py`

**Interfaces:**
- Consumes: `optimize(..., on_step=...)` from Task 1.
- Produces: no new public interface; `forex hyperopt` now emits `[<i>/<n>] new best <objective>=<score> @ {...}` lines to stderr while searching. stdout (the final winning-config TOML) is unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_hyperopt.py` (it already defines `_view()` and imports `forex.cli as cli`, `RunConfig`, `EnvConfig`):

```python
def test_main_hyperopt_prints_progress_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["hyperopt", "--strategy", "carry", "--n-samples", "6", "--seed", "1",
                   "--tune", "n_long,n_short", "--train-days", "250", "--test-days", "125"])
    assert rc == 0
    cap = capsys.readouterr()
    assert "new best" in cap.err                       # progress went to stderr
    assert "new best" not in cap.out                   # stdout stays clean
    assert "strategy = \"carry\"" in cap.out            # winning-config TOML still on stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_hyperopt.py::test_main_hyperopt_prints_progress_to_stderr -v`
Expected: FAIL on `assert "new best" in cap.err` (nothing is printed to stderr yet).

- [ ] **Step 3: Write minimal implementation**

In `forex/cli.py`, replace the current `hyperopt` branch of `run()`:

```python
    if mode == "hyperopt":
        from forex.run.hyperopt import optimize
        res = optimize(cfg.strategy, view, train_days=cfg.train_days, test_days=cfg.test_days,
                       n_samples=cfg.n_samples, seed=cfg.seed, cost_bps=cfg.cost_bps,
                       base_params=cfg.strategy_params, tune=cfg.tune, objective=cfg.objective)
        return {"hyperopt": {**res, "strategy": cfg.strategy, "cost_bps": cfg.cost_bps}}
```

with this (adds a stderr progress closure passed as `on_step`):

```python
    if mode == "hyperopt":
        import sys
        from forex.run.hyperopt import optimize
        def _on_step(i, n, score, params, improved, _obj=cfg.objective):
            if improved:
                ps = ", ".join(f"{k}={v}" for k, v in params.items())
                print(f"[{i:>3}/{n}] new best {_obj}={score:.4f} @ {{{ps}}}", file=sys.stderr)
        res = optimize(cfg.strategy, view, train_days=cfg.train_days, test_days=cfg.test_days,
                       n_samples=cfg.n_samples, seed=cfg.seed, cost_bps=cfg.cost_bps,
                       base_params=cfg.strategy_params, tune=cfg.tune, objective=cfg.objective,
                       on_step=_on_step)
        return {"hyperopt": {**res, "strategy": cfg.strategy, "cost_bps": cfg.cost_bps}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_hyperopt.py -v`
Expected: PASS (the new test and the pre-existing `test_resolve_hyperopt_args`, `test_run_hyperopt`, `test_main_hyperopt_prints_winning_config`).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (whole suite green). If any pre-existing test fails, STOP and report BLOCKED with the failure — do not commit a red suite.

- [ ] **Step 6: Commit**

```bash
git add forex/cli.py tests/test_cli_hyperopt.py
git commit -m "feat: hyperopt prints new-best progress to stderr

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- `run()` returning the dict that `main()` formats and prints to stdout is unchanged — only the `hyperopt` branch gains the `on_step` closure. Do not alter `_format`, `main`, or any other mode.
- The progress closure binds `cfg.objective` via a default arg (`_obj=cfg.objective`) to avoid late-binding surprises; keep it that way.
- Do not touch `docs/` or the currently-running background hyperopt — this change only affects future runs.
