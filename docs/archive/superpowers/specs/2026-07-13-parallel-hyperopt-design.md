# Parallel Hyperopt — Design Spec

*Design spec. Status: approved 2026-07-13. Hyperopt is the framework's heaviest operation and runs
single-threaded (≈1 of 14 cores). This parallelizes the independent candidate evaluations across a
process pool for a ~cores× speedup, while keeping the result deterministic and identical regardless of
worker count.*

## Goal & success criteria
- `optimize()` evaluates its N candidates across `jobs` worker processes; wall-clock drops ~linearly
  with cores on the heavy searches.
- **Determinism is preserved and job-count-invariant:** `optimize(jobs=1)` and `optimize(jobs=k)`
  return the *same* `best_params`/`score`, and the result matches today's sequential optimize (a pure
  speedup, not a behaviour change).
- CLI gains `--jobs N`, defaulting to `cores-1` (parallel by default); `--jobs 1` forces sequential.
- Success: a test asserts `jobs=1 == jobs=4`; the full suite stays green; `forex hyperopt` runs
  multi-core.

## Why a process pool (not threads / GPU)
The work is pandas time-series (rolling/shift/as-of-join/resample/cumprod over a ~13k×9 panel) — CPU
sequential scans, GIL-bound, and not matrix math. **Threads** don't help (GIL); **GPU/MLX** is the
wrong tool (tiny branchy data; kernel-launch overhead would dominate — a rewrite that runs *slower*).
Independent-sample **process** parallelism is the right and simple lever. Stdlib
`concurrent.futures.ProcessPoolExecutor` — no new dependency.

## Design: separate sampling from evaluation

`optimize` today interleaves sampling and evaluation in one loop. Split them:

1. **Sample all N candidates first**, sequentially, from the seeded RNG — the *same* draws in the same
   order as today, so the candidate set is byte-identical to the current sequential optimize.
2. **Evaluate the candidates** — sequentially if `jobs == 1`, else via a `ProcessPoolExecutor(jobs)`.
   Each evaluation is `walk_forward(build(cand), view, …)` → `(score, oos_metrics)`.
3. **Pick the winner by stable argmax** — max score, ties broken by lowest candidate index. This is
   exactly what the current loop picks (first candidate to reach the running max), and it is
   **independent of completion order**, so the result is identical for any `jobs`.

### `forex/run/hyperopt.py`
```python
import os, random
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

    results: list = [None] * n_samples          # results[idx] = (score, oos)
    best_seen = float("-inf")
    def record(idx, score, oos, done):
        nonlocal best_seen
        results[idx] = (score, oos)
        improved = score > best_seen
        if improved:
            best_seen = score
        if on_step is not None:
            on_step(done, n_samples, score, cands[idx], improved)   # `done` = completion count

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

    best_idx = max(range(n_samples), key=lambda i: (results[i][0], -i))   # stable argmax
    best_params, (best_score, best_oos) = cands[best_idx], results[best_idx]
    is_metrics = backtest(build(best_params), view, cost_bps).metrics
    return {"best_params": best_params, "score": best_score, "objective": objective,
            "oos": best_oos, "in_sample": is_metrics, "n_samples": n_samples}
```
- **Backward compatible:** `jobs=1` (the default) reproduces today's result exactly (same candidates,
  same winner). Existing `optimize(build, …)` call sites (which pass a lambda builder) keep working.
- `_eval` is **module-level** (picklable); its inner `lambda: build(cand)` runs *inside* the worker
  (created there, never pickled), matching `walk_forward`'s `strategy_factory` contract.
- **`on_step`:** under parallelism `done` is the completion count (not candidate index) and `improved`
  is arrival-order — purely cosmetic (the live "new best" print). The returned winner is the
  deterministic stable-argmax, unaffected.

## The picklable-builder requirement
`ProcessPoolExecutor` pickles the work sent to workers, so for `jobs > 1` the injected `build` must be
**picklable**. The CLI currently injects a **lambda** (`build = lambda p: build_strategy(cfg.strategy,
p, "strategies")`), which is not picklable. Replace it with a `functools.partial` of the module-level
`build_strategy`:
```python
    build = functools.partial(build_strategy, cfg.strategy, package="strategies")
```
`build_strategy(name, params=None, package="strategies")` → `partial(build_strategy, name,
package="strategies")(params)` calls `build_strategy(name, params, package="strategies")`. Picklable
(partial of a top-level function with str args). The sequential path (`jobs=1`) accepts any callable,
so library callers passing a lambda are unaffected.

## CLI wiring (`forex/cli.py`, `forex/core/config.py`)
- **`RunConfig`** gains `jobs: int = 1` (default 1 → constructing `RunConfig()` directly, as tests do,
  stays sequential and fast; it's a perf knob, and it is NOT emitted in the printed winning-config
  TOML, which is built from `strategy`/`cost_bps`/`strategy_params` only).
- **`build_parser`** adds `--jobs` (`type=int`) under the `hyperopt` subparser.
- **`resolve`** sets the CLI default: `overrides["jobs"] = args.jobs if args.jobs is not None else
  max(1, (os.cpu_count() or 1) - 1)` (so `--jobs` absent → parallel; explicit → honoured). Add `jobs`
  to `RunConfig` handling so `merge` accepts it.
- **`run`'s hyperopt branch** builds the `functools.partial` builder and passes `jobs=cfg.jobs` to
  `optimize` (keeping the existing `_on_step` stderr closure).

## Testing (all offline, no network)
- **Determinism / job-invariance** (`tests/test_hyperopt.py`) — with a **picklable** builder
  `functools.partial(build_strategy, "carry", package="strategies")` and a synthetic in-memory view,
  `optimize(build, view, …, jobs=1)` and `optimize(build, view, …, jobs=4)` return equal
  `best_params` and `score`. (This is the core guarantee.)
- **Parallel path completes** — a small `jobs=2` run returns a well-formed result dict (`best_params`,
  `score`, `oos`, `in_sample`, `n_samples`) — smoke that the pool actually runs.
- **Existing `optimize` tests unchanged** — they call `optimize(build, …)` with the default `jobs=1`
  and must still pass (byte-identical behaviour).
- **CLI** (`tests/test_cli_hyperopt.py`) — `resolve` maps `--jobs 4` → `cfg.jobs == 4`, and with
  `--jobs` absent → `cfg.jobs == max(1, cpu-1)`. Update the existing `cli.main([...])` hyperopt tests
  (`test_main_hyperopt_*`) to pass **`--jobs 1`** so they stay sequential (they test output
  formatting, not parallelism — no reason to spawn a pool in them).

## Out of scope (deferred)
- **Redundant sub-strategy re-evaluation inside blends** (the blend computes each sub's weights, then
  `backtest` recomputes them, then the overlay re-backtests the blend) — a further ~2–4× per-sample
  win via caching. A separate optimization; parallelism is the headline.
- Fold-level parallelism (coarser sample-level parallelism suffices).
- A persistent worker pool / shared-memory view (per-submit pickling of the ~few-MB view is fine at
  these sample counts).
