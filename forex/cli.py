import argparse
import os
import functools
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
    for mode in ("backtest", "walkforward", "causal-check", "hyperopt", "download", "dryrun"):
        sp = sub.add_parser(mode)
        sp.add_argument("--config")
        sp.add_argument("--strategy")
        sp.add_argument("--universe")
        sp.add_argument("--timerange")
        sp.add_argument("--cost-bps", type=float, dest="cost_bps")
        sp.add_argument("--param", action="append", default=[], dest="params")
        sp.add_argument("--cache-dir", dest="cache_dir")
        if mode in ("walkforward", "hyperopt"):
            sp.add_argument("--train-days", type=int, dest="train_days")
            sp.add_argument("--test-days", type=int, dest="test_days")
        if mode == "hyperopt":
            sp.add_argument("--n-samples", type=int, dest="n_samples")
            sp.add_argument("--seed", type=int)
            sp.add_argument("--objective")
            sp.add_argument("--tune")
            sp.add_argument("--jobs", type=int)
        if mode == "dryrun":
            sp.add_argument("--preview", action="store_true")
            sp.add_argument("--equity", type=float)
            sp.add_argument("--broker", choices=["sim", "ib"], default="sim")
            sp.add_argument("--ib-port", type=int, default=4002, dest="ib_port")
            sp.add_argument("--confirm", action="store_true")
            sp.add_argument("--max-order-frac", type=float, dest="max_order_frac")
            sp.add_argument("--allow-live", action="store_true", dest="allow_live")
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
    if args.params:
        sp = {}
        for kv in args.params:
            k, v = kv.split("=", 1)
            sp[k] = _coerce(v)
        overrides["strategy_params"] = sp
    for attr in ("train_days", "test_days", "n_samples", "seed", "objective"):
        v = getattr(args, attr, None)
        if v is not None:
            overrides[attr] = v
    tune = getattr(args, "tune", None)
    if tune is not None:
        overrides["tune"] = tune.split(",")
    if getattr(args, "preview", False):
        overrides["preview"] = True
    if getattr(args, "confirm", False):
        overrides["confirm"] = True
    if getattr(args, "allow_live", False):
        overrides["allow_live"] = True
    max_order_frac = getattr(args, "max_order_frac", None)
    if max_order_frac is not None:
        overrides["max_order_frac"] = max_order_frac
    broker = getattr(args, "broker", None)
    if broker is not None:
        overrides["broker"] = broker
    ib_port = getattr(args, "ib_port", None)
    if ib_port is not None:
        overrides["ib_port"] = ib_port
    overrides["jobs"] = args.jobs if getattr(args, "jobs", None) is not None \
        else max(1, (os.cpu_count() or 1) - 1)
    cfg = cfg.merge(overrides)
    env = EnvConfig.load()
    if args.cache_dir is not None:
        env = replace(env, data_cache_dir=args.cache_dir)
    equity = getattr(args, "equity", None)
    if equity is not None:
        env = replace(env, starting_equity=equity)
    return cfg, env, args.mode

def _build_view(cfg, env):
    from forex.core.dataview import DataView
    view = DataView.from_fred(env.data_cache_dir, codes=cfg.universe)
    if cfg.timerange:
        s, e = cfg.timerange
        spot = view.spot.loc[s:e]
        rates = {k: v.loc[s:e] for k, v in view.rates.items()}
        reer = {k: v.loc[s:e] for k, v in view.reer.items()}
        macro = {k: v.loc[s:e] for k, v in view.macro.items()}
        view = DataView(spot=spot, rates=rates, reer=reer, macro=macro)
    return view

def run(cfg, env, mode) -> dict:
    if mode == "download":
        import sys
        from forex.data.refresh import refresh_cache
        def _on_step(i, n, sid):
            print(f"[{i:>2}/{n}] fetching {sid}", file=sys.stderr)
        series = refresh_cache(env.data_cache_dir, codes=cfg.universe, on_step=_on_step)
        return {"download": {"series": series, "cache_dir": env.data_cache_dir}}
    from forex.core.discovery import build_strategy
    from forex.run.backtest import backtest
    from forex.run.walkforward import walk_forward
    from forex.diagnostics.causal import assert_causal
    view = _build_view(cfg, env)
    if mode == "backtest":
        r = backtest(build_strategy(cfg.strategy, cfg.strategy_params, "strategies"), view, cfg.cost_bps)
        return {"metrics": r.metrics}
    if mode == "walkforward":
        r = walk_forward(lambda: build_strategy(cfg.strategy, cfg.strategy_params, "strategies"),
                         view, cfg.train_days, cfg.test_days, cfg.cost_bps)
        return {"metrics": r.metrics}
    if mode == "causal-check":
        strat = build_strategy(cfg.strategy, cfg.strategy_params, "strategies")
        n = len(view.calendar)
        assert_causal(strat, view, view.calendar[[n // 4, n // 2, n - 1]])
        return {"causal": "PASS"}
    if mode == "hyperopt":
        import sys
        from forex.run.hyperopt import optimize
        def _on_step(i, n, score, params, improved, _obj=cfg.objective):
            if improved:
                ps = ", ".join(f"{k}={v}" for k, v in params.items())
                print(f"[{i:>3}/{n}] new best {_obj}={score:.4f} @ {{{ps}}}", file=sys.stderr)
        build = functools.partial(build_strategy, cfg.strategy, package="strategies")
        res = optimize(build, view, train_days=cfg.train_days, test_days=cfg.test_days,
                       n_samples=cfg.n_samples, seed=cfg.seed, cost_bps=cfg.cost_bps,
                       base_params=cfg.strategy_params, tune=cfg.tune, objective=cfg.objective,
                       on_step=_on_step, jobs=cfg.jobs)
        return {"hyperopt": {**res, "strategy": cfg.strategy, "cost_bps": cfg.cost_bps}}
    if mode == "dryrun":
        import os
        from forex.run.live import rebalance_now
        if cfg.broker == "ib":
            from forex.run.execution import LiveExecution
            ex = LiveExecution(port=cfg.ib_port, cost_bps=cfg.cost_bps, preview=cfg.preview,
                               confirm=cfg.confirm, allow_live=cfg.allow_live,
                               **({"max_order_frac": cfg.max_order_frac} if cfg.max_order_frac is not None else {}))
        else:
            from forex.run.execution import SimExecution
            pf = os.path.join(env.output_dir, "portfolio.json")
            ex = SimExecution(pf, starting_equity=env.starting_equity, cost_bps=cfg.cost_bps,
                              preview=cfg.preview)
        rep = rebalance_now(build_strategy(cfg.strategy, cfg.strategy_params, "strategies"), view, ex)
        return {"dryrun": rep, "broker": cfg.broker}
    raise ValueError(f"unknown mode {mode}")

def _format(out: dict) -> str:
    if "metrics" in out:
        m = out["metrics"]
        keys = ["total_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar"]
        return "  ".join(f"{k}={m[k]:.4f}" for k in keys if k in m)
    if "causal" in out:
        return f"causal-check: {out['causal']}"
    if "hyperopt" in out:
        from forex.core.config import RunConfig
        r = out["hyperopt"]
        best = RunConfig(strategy=r["strategy"], cost_bps=r["cost_bps"],
                         strategy_params=r["best_params"])
        gap = r["in_sample"]["sharpe"] - r["oos"]["sharpe"]
        return ("\n".join([
            f"best {r['objective']} (OOS) = {r['score']:.4f}   [n_samples={r['n_samples']}]",
            f"OOS       sharpe={r['oos']['sharpe']:.3f} calmar={r['oos']['calmar']:.3f} "
            f"maxDD={r['oos']['max_drawdown']:.3f}",
            f"in-sample sharpe={r['in_sample']['sharpe']:.3f}  (IS-OOS gap {gap:+.3f})",
            "--- winning config ---",
            best.to_toml_str().rstrip(),
        ]))
    if "download" in out:
        d = out["download"]
        return f"downloaded {len(d['series'])} series to {d['cache_dir']}"
    if "dryrun" in out:
        rep = out["dryrun"]
        if out.get("broker") == "ib":
            if rep.applied:
                header = f"ORDERS PLACED -> NAV {rep.equity:,.0f}  turnover {rep.turnover:.3f}  est.cost {rep.cost:,.0f}"
            else:
                header = f"PREVIEW IBKR rebalance -> NAV {rep.equity:,.0f}  turnover {rep.turnover:.3f}  est.cost {rep.cost:,.0f}"
            lines = []
            if rep.applied and not getattr(rep, "complete", True):
                lines.append("⚠ INCOMPLETE — partial fills; review positions")
            lines += [header, "orders (base-ccy units):"]
            for pair, units in sorted(rep.orders.items(), key=lambda kv: -abs(kv[1])):
                if abs(units) > 1e-6:
                    lines.append(f"  {pair:8} {'BUY ' if units > 0 else 'SELL'} {abs(units):,.0f}")
            return "\n".join(lines)
        head = f"{'PREVIEW ' if not rep.applied else ''}rebalance -> equity {rep.equity:.2f}  " \
               f"turnover {rep.turnover:.3f}  cost {rep.cost:.2f}"
        lines = [head, "orders (notional):"]
        for c, v in sorted(rep.orders.items(), key=lambda kv: -abs(kv[1])):
            if abs(v) > 1e-6:
                lines.append(f"  {c:5} {v:+.2f}")
        return "\n".join(lines)
    return str(out)

def main(argv=None) -> int:
    cfg, env, mode = resolve(build_parser().parse_args(argv))
    print(_format(run(cfg, env, mode)))
    return 0
