from forex.data.fred import load_series

def run_overlay(cache_dir, loader=load_series, codes=None, n_long=3, n_short=3,
                cost_bps=1.0, target_vol=0.10, cap=1.5, cadence="MS", lam=0.94):
    from forex.core.dataview import DataView
    from strategies.carry import CarryStrategy
    from strategies.overlay import VolTargetOverlay
    from forex.run.backtest import backtest
    view = DataView.from_fred(cache_dir, loader=loader, codes=codes)
    base = CarryStrategy(n_long=n_long, n_short=n_short)
    ov = VolTargetOverlay(base, target_vol=target_vol, cap=cap, cadence=cadence,
                          lam=lam, cost_bps=cost_bps)
    r_bare = backtest(base, view, cost_bps=cost_bps)
    r_ov = backtest(ov, view, cost_bps=cost_bps)
    return {"bare": r_bare.returns, "overlay": r_ov.returns,
            "metrics_bare": r_bare.metrics, "metrics_overlay": r_ov.metrics}

if __name__ == "__main__":
    from forex.backtest.validation import distant_window
    out = run_overlay(cache_dir="data_cache")
    bare, overlay = out["bare"], out["overlay"]
    print("=" * 64)
    print("CARRY + EWMA VOL-TARGET OVERLAY  (target 10% ann, cap 1.5x, monthly)")
    print("=" * 64)
    active = overlay.loc[overlay != 0]
    first = active.index[0] if len(active) else overlay.index[0]
    for label, m in [("bare carry     ", out["metrics_bare"]),
                     ("vol-target     ", out["metrics_overlay"])]:
        print(f"{label}  total {m['total_return']*100:+.0f}%  ann {m['ann_return']*100:+.1f}%  "
              f"vol {m['ann_vol']*100:.1f}%  Sharpe {m['sharpe']:.2f}  "
              f"maxDD {m['max_drawdown']*100:.0f}%  Calmar {m['calmar']:.2f}")
    recent, dist = distant_window(overlay.loc[first:].index, holdout_years=3)
    ov = overlay.loc[first:]
    print(f"\nDISTANT-ERA (earliest 3y) vol-target: "
          f"{((1+ov.iloc[dist]).prod()-1)*100:+.1f}%   "
          f"recent: {((1+ov.iloc[recent]).prod()-1)*100:+.1f}%")
