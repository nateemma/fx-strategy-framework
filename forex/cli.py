import argparse
from dataclasses import replace
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _coerce(s: str):
    for f in (int, float):
        try:
            return f(s)
        except ValueError:
            pass
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    return s

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="forex")
    sub = p.add_subparsers(dest="mode", required=True)
    for mode in ("backtest", "walkforward", "causal-check"):
        sp = sub.add_parser(mode)
        sp.add_argument("--config")
        sp.add_argument("--strategy")
        sp.add_argument("--universe")
        sp.add_argument("--timerange")
        sp.add_argument("--cost-bps", type=float, dest="cost_bps")
        sp.add_argument("--cadence")
        sp.add_argument("--param", action="append", default=[], dest="params")
        sp.add_argument("--cache-dir", dest="cache_dir")
    return p

def resolve(args):
    cfg = RunConfig.from_toml(args.config) if args.config else RunConfig()
    overrides = {}
    if args.strategy is not None:
        overrides["strategy"] = args.strategy
    if args.universe is not None:
        overrides["universe"] = args.universe.split(",")
    if args.timerange is not None:
        a, b = args.timerange.split(":")
        overrides["timerange"] = [a or None, b or None]
    if args.cost_bps is not None:
        overrides["cost_bps"] = args.cost_bps
    if args.cadence is not None:
        overrides["cadence"] = args.cadence
    if args.params:
        sp = {}
        for kv in args.params:
            k, v = kv.split("=", 1)
            sp[k] = _coerce(v)
        overrides["strategy_params"] = sp
    cfg = cfg.merge(overrides)
    env = EnvConfig.load()
    if args.cache_dir:
        env = replace(env, data_cache_dir=args.cache_dir)
    return cfg, env, args.mode

def _build_view(cfg, env):
    from forex.core.dataview import DataView
    view = DataView.from_fred(env.data_cache_dir, codes=cfg.universe)
    if cfg.timerange:
        s, e = cfg.timerange
        spot = view.spot.loc[s:e]
        rates = {k: v.loc[s:e] for k, v in view.rates.items()}
        view = DataView(spot=spot, rates=rates)
    return view

def run(cfg, env, mode) -> dict:
    from forex.strategies.registry import build_strategy
    from forex.run.backtest import backtest
    from forex.run.walkforward import walk_forward
    from forex.diagnostics.causal import assert_causal
    view = _build_view(cfg, env)
    if mode == "backtest":
        r = backtest(build_strategy(cfg.strategy, cfg.strategy_params), view, cfg.cost_bps)
        return {"metrics": r.metrics}
    if mode == "walkforward":
        r = walk_forward(lambda: build_strategy(cfg.strategy, cfg.strategy_params),
                         view, cfg.train_days, cfg.test_days, cfg.cost_bps)
        return {"metrics": r.metrics}
    if mode == "causal-check":
        strat = build_strategy(cfg.strategy, cfg.strategy_params)
        n = len(view.calendar)
        assert_causal(strat, view, view.calendar[[n // 4, n // 2, n - 1]])
        return {"causal": "PASS"}
    raise ValueError(f"unknown mode {mode}")

def _format(out: dict) -> str:
    if "metrics" in out:
        m = out["metrics"]
        keys = ["total_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar"]
        return "  ".join(f"{k}={m[k]:.4f}" for k in keys if k in m)
    return str(out)

def main(argv=None) -> int:
    cfg, env, mode = resolve(build_parser().parse_args(argv))
    print(_format(run(cfg, env, mode)))
    return 0
