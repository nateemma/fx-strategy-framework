# Parallel Hyperopt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate hyperopt candidates across a process pool for a ~cores× speedup, with a deterministic, job-count-invariant result.

**Architecture:** `optimize()` samples all candidates first (seeded), evaluates them sequentially (`jobs=1`) or via `ProcessPoolExecutor` (`jobs>1`), and picks the winner by stable argmax — identical for any `jobs`. The CLI injects a picklable `functools.partial` builder and defaults `--jobs` to `cores-1`.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, stdlib `concurrent.futures`. No new dependencies.

## Global Constraints

- **Deterministic + job-invariant:** `optimize(jobs=1)` and `optimize(jobs=k)` return the same `best_params`/`score`, and `jobs=1` reproduces today's sequential result byte-for-byte (pure speedup).
- Candidates are sampled sequentially from the seeded RNG (same draws as today); the winner is the **stable argmax** (max score, ties → lowest candidate index).
- Worker function `_eval` is module-level (picklable); the parallel path requires a **picklable `build`** (a `functools.partial`, not a lambda). The sequential path accepts any callable.
- `RunConfig.jobs` default = `1` (so `RunConfig()` construction stays sequential); the CLI `resolve` defaults `jobs` to `max(1, cpu_count-1)` when `--jobs` is absent.
- No new dependencies. Match the existing compact style. Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: Parallel `optimize`

**Files:**
- Modify: `forex/run/hyperopt.py`
- Test: `tests/test_hyperopt.py`

**Interfaces:**
- Produces: `optimize(build, view, *, …, jobs=1)` (new `jobs` kwarg); `_eval(build, cand, view, train_days, test_days, cost_bps, objective) -> (score, oos_metrics)` (module-level worker).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hyperopt.py` (it already defines `_view()` and imports `optimize`; add `import functools` and `from forex.core.discovery import build_strategy` if not present):
```python
def test_jobs_invariant_determinism():
    v = _view()
    build = functools.partial(build_strategy, "carry", package="strategies")   # picklable
    a = optimize(build, v, train_days=250, test_days=125, n_samples=6, seed=7,
                 tune=["n_long", "n_short"], jobs=1)
    b = optimize(build, v, train_days=250, test_days=125, n_samples=6, seed=7,
                 tune=["n_long", "n_short"], jobs=4)
    assert a["best_params"] == b["best_params"] and a["score"] == b["score"]

def test_parallel_path_completes():
    v = _view()
    build = functools.partial(build_strategy, "carry", package="strategies")
    r = optimize(build, v, train_days=250, test_days=125, n_samples=4, seed=1,
                 tune=["n_long", "n_short"], jobs=2)
    assert set(r) >= {"best_params", "score", "oos", "in_sample", "n_samples"}
    assert r["n_samples"] == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hyperopt.py -v`
Expected: FAIL — `optimize()` has no `jobs` kwarg.

- [ ] **Step 3: Write minimal implementation**

Replace `forex/run/hyperopt.py` with:
```python
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from forex.run.walkforward import walk_forward
from forex.run.backtest import backtest

def _eval(build, cand, view, train_days, test_days, cost_bps, objective):
    wf = walk_forward(lambda: build(cand), view, train_days, test_days, cost_bps)
    return wf.metrics.get(objective, float("-inf")), wf.metrics

def optimize(build, view, *, train_days, test_days, n_samples=200, seed=0, cost_bps=1.0,
             base_params=None, tune=None, objective="sharpe", on_step=None, jobs=1) -> dict:
    base_params = dict(base_params or {})
    space = build(base_params).search_space()
    if tune is not None:
        space = {k: space[k] for k in tune}
    rng = random.Random(seed)
    cands = []
    for _ in range(n_samples):
        cand = dict(base_params)
        for k, sp in space.items():
            cand[k] = sp.sample(rng)
        cands.append(cand)

    results = [None] * n_samples
    best_seen = float("-inf")
    def record(idx, score, oos, done):
        nonlocal best_seen
        results[idx] = (score, oos)
        improved = score > best_seen
        if improved:
            best_seen = score
        if on_step is not None:
            on_step(done, n_samples, score, cands[idx], improved)

    if jobs == 1:
        for done, cand in enumerate(cands, start=1):
            score, oos = _eval(build, cand, view, train_days, test_days, cost_bps, objective)
            record(done - 1, score, oos, done)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(_eval, build, c, view, train_days, test_days, cost_bps, objective): i
                    for i, c in enumerate(cands)}
            for done, fut in enumerate(as_completed(futs), start=1):
                idx = futs[fut]
                score, oos = fut.result()
                record(idx, score, oos, done)

    best_idx = max(range(n_samples), key=lambda i: (results[i][0], -i))
    best_params, (best_score, best_oos) = cands[best_idx], results[best_idx]
    is_metrics = backtest(build(best_params), view, cost_bps).metrics
    return {"best_params": best_params, "score": best_score, "objective": objective,
            "oos": best_oos, "in_sample": is_metrics, "n_samples": n_samples}
```

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_hyperopt.py -v && python -m pytest -q`
Expected: PASS — the two new tests, the pre-existing `optimize` tests (which use `jobs=1` default with a lambda builder — unchanged behaviour), and the whole suite.

- [ ] **Step 5: Commit**

```bash
git add forex/run/hyperopt.py tests/test_hyperopt.py
git commit -m "feat: parallel hyperopt (process-pool candidate evaluation, jobs param)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: CLI `--jobs` + picklable builder

**Files:**
- Modify: `forex/core/config.py`, `forex/cli.py`
- Test: `tests/test_cli_hyperopt.py`

**Interfaces:**
- Produces: `RunConfig.jobs: int = 1`; `forex hyperopt --jobs N` (default `cores-1`); the CLI injects a picklable `functools.partial` builder and passes `jobs=cfg.jobs` to `optimize`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_hyperopt.py`:
```python
def test_resolve_jobs_flag_and_default():
    import os
    from forex.cli import build_parser, resolve
    cfg, _, _ = resolve(build_parser().parse_args(
        ["hyperopt", "--strategy", "carry", "--jobs", "4"]))
    assert cfg.jobs == 4
    cfg2, _, _ = resolve(build_parser().parse_args(["hyperopt", "--strategy", "carry"]))
    assert cfg2.jobs == max(1, (os.cpu_count() or 1) - 1)   # parallel by default
```

Then update the two existing `cli.main([...])` hyperopt tests to pass `--jobs 1` (keep them sequential — they test output formatting, not parallelism). In `test_main_hyperopt_prints_winning_config` and `test_main_hyperopt_prints_progress_to_stderr`, add `"--jobs", "1"` to the argv list passed to `cli.main([...])`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli_hyperopt.py -v`
Expected: FAIL — `test_resolve_jobs_flag_and_default` errors (`--jobs` unknown / `cfg.jobs` missing).

- [ ] **Step 3: Write minimal implementation**

In `forex/core/config.py`, add a field to `RunConfig` (after `preview`):
```python
    preview: bool = False
    jobs: int = 1
```
(`from_dict`/`merge`/`to_toml_str` need no change — `from_dict` filters by declared fields, `merge` uses `asdict`, and `to_toml_str` deliberately emits only strategy/cost_bps/universe/strategy_params.)

In `forex/cli.py`:
- Add `import os` and `import functools` at the top.
- In `build_parser`, inside `if mode == "hyperopt":`, add: `sp.add_argument("--jobs", type=int)`.
- In `resolve`, after the existing `for attr in (...)` loop (and before/after the `tune` block), set the jobs default:
```python
    overrides["jobs"] = args.jobs if getattr(args, "jobs", None) is not None \
        else max(1, (os.cpu_count() or 1) - 1)
```
- In `run`'s `if mode == "hyperopt":` branch, replace the lambda builder and pass `jobs`:
```python
        build = functools.partial(build_strategy, cfg.strategy, package="strategies")
        res = optimize(build, view, train_days=cfg.train_days, test_days=cfg.test_days,
                       n_samples=cfg.n_samples, seed=cfg.seed, cost_bps=cfg.cost_bps,
                       base_params=cfg.strategy_params, tune=cfg.tune, objective=cfg.objective,
                       on_step=_on_step, jobs=cfg.jobs)
```
(keep the existing `_on_step` closure and the `return {"hyperopt": …}` line).

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_cli_hyperopt.py -v && python -m pytest -q`
Expected: PASS. Note the two updated `main` tests now run with `--jobs 1` (sequential); `test_run_hyperopt` calls `cli.run(RunConfig(...))` which has `jobs=1` by default, so it stays sequential too.

- [ ] **Step 5: Commit**

```bash
git add forex/core/config.py forex/cli.py tests/test_cli_hyperopt.py
git commit -m "feat: forex hyperopt --jobs (default cores-1); picklable partial builder

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- The determinism guarantee is the point: `jobs` must never change the winner. If `test_jobs_invariant_determinism` fails, STOP — the stable-argmax or the candidate sampling is wrong; do not "fix" it by loosening the assertion.
- `_eval` MUST be module-level (picklable); its inner `lambda: build(cand)` runs inside the worker (fine — `walk_forward` takes a factory).
- For `jobs > 1` the injected `build` must be picklable — that's why the CLI uses `functools.partial(build_strategy, …)`, not a lambda. Library callers that stay sequential (`jobs=1`) may still pass a lambda.
- Do not emit `jobs` in the winning-config TOML (`to_toml_str` already only emits the experiment fields).
