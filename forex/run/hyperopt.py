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
