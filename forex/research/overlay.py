from forex.data.fred import load_series
from forex.research.carry_baseline import run_baseline
from forex.features.volforecast import ewma_vol
from forex.backtest.voltarget import vol_target
from forex.backtest.portfolio import metrics

def run_overlay(cache_dir, loader=load_series, codes=None, n_long=3, n_short=3,
                cost_bps=1.0, target_vol=0.10, cap=1.5, cadence="MS", lam=0.94):
    bare, m_bare = run_baseline(cache_dir, loader=loader, codes=codes,
                                n_long=n_long, n_short=n_short, cost_bps=cost_bps)
    vf = ewma_vol(bare, lam=lam)
    overlay = vol_target(bare, vf, target_vol=target_vol, cap=cap,
                         cadence=cadence, cost_bps=cost_bps)
    return {"bare": bare, "overlay": overlay,
            "metrics_bare": m_bare, "metrics_overlay": metrics(overlay)}

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
