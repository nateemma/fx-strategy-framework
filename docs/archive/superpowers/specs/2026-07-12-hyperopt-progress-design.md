# Hyperopt Progress Output — Design Spec

*Design spec. Status: approved 2026-07-12. Small enhancement to the FX strategy framework
(`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`). Makes `forex hyperopt`
report its running best as it searches, freqtrade-style, instead of printing nothing until the end.*

## Goal & success criteria
Long hyperopt runs (random search does a full walk-forward per sample) currently produce no output
until completion, so the user cannot tell the run is progressing or what the best config so far is.
Add incremental "new best" progress reporting. Success: `forex hyperopt …` prints a line each time a
new best config is found — sample `i/N`, the objective score, and the params — and the final winning
config still prints exactly as it does today.

## Decisions (settled during brainstorming)
- **Quiet cadence:** print a line ONLY when a new best is found (not per-sample, no heartbeat).
- **Mechanism:** `optimize()` gains an optional `on_step` callback fired once per sample; the CLI owns
  presentation. The library never touches stdout/stderr — it stays pure and unit-testable.
- **Stream:** the CLI prints progress to **stderr**, so stdout stays clean and holds only the final
  winning-config TOML (`forex hyperopt … > winning.toml` must not capture progress lines).

## Component 1 — `optimize()` callback (`forex/run/hyperopt.py`)
Add a keyword parameter `on_step=None`. Inside the existing sample loop, after the `best` update,
determine whether this sample became the new best and invoke the callback:

```python
def optimize(strategy_name, view, *, train_days, test_days, n_samples=200, seed=0,
             cost_bps=1.0, base_params=None, tune=None, objective="sharpe", on_step=None) -> dict:
    ...
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
    ...
```

- **Signature:** `on_step(i, n, score, params, improved)` — `i` is 1-based, `n` is `n_samples`,
  `score` is the sampled candidate's objective value, `params` is that candidate's full param dict,
  `improved` is `True` iff this sample set a new best.
- **Loop counter:** the loop variable becomes `i` (1-based) purely to feed the callback; sampling
  order and results are unchanged (same `rng` draw sequence).
- **Backward compatibility:** with `on_step=None` (the default), behavior is identical to today —
  including determinism and the returned dict. No other call site changes.
- The returned dict (`best_params`, `score`, `objective`, `oos`, `in_sample`, `n_samples`) is
  unchanged.

## Component 2 — CLI printer (`forex/cli.py`, `hyperopt` branch of `run()`)
In the `if mode == "hyperopt":` branch, build a small closure and pass it as `on_step`:

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

- Prints ONLY on `improved`, to **stderr**.
- Format: `[<i>/<n>] new best <objective>=<score:.4f> @ {k=v, k=v, ...}`.
- `run()` already returns the dict that `main()` formats and prints to stdout — that path is unchanged,
  so the final winning-config TOML is untouched.

## Testing (all offline, no network)
Extend the existing `tests/test_hyperopt.py` and `tests/test_cli_hyperopt.py`.

- **`optimize` fires the callback once per sample** — pass an `on_step` that appends
  `(i, n, score, params, improved)` to a list; assert `len == n_samples`, the `i` values are
  `1..n_samples` in order, `n` is constant, and the first sample has `improved=True`.
- **`improved` flags are correct** — assert every `improved=True` entry has a `score` strictly greater
  than all earlier entries' scores, and every `improved=False` entry does not (i.e. `improved` marks
  exactly the running-maximum samples).
- **`on_step=None` is a no-op / backward compatible** — `optimize(..., on_step=None)` returns the same
  `best_params` and `score` as the same call without the argument (reuse the existing deterministic
  `_view`).
- **CLI prints progress to stderr** — via `capsys`, assert `readouterr().err` contains `"new best"`
  and the stdout still contains the winning-config TOML (`strategy = "carry"`). Use the existing
  monkeypatched `_build_view`.

## Out of scope (YAGNI)
- No per-sample heartbeat line and no cadence parameter (quiet mode chosen).
- No persisted hyperopt log file (the framework may add per-run logging later; not here).
- No change to the search algorithm, the objective, the returned dict, or any other CLI mode.
