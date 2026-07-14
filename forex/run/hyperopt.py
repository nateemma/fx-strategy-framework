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
