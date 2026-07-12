import pandas as pd
from forex.core.result import Result
from forex.run.backtest import backtest
from forex.backtest.portfolio import metrics
from forex.backtest.validation import walk_forward as wf_splits

def walk_forward(strategy_factory, view, train_days, test_days, cost_bps: float = 1.0) -> Result:
    cal = view.calendar
    rets_parts, wt_parts = [], []
    for train_sl, test_sl in wf_splits(cal, train_days, test_days):
        strat = strategy_factory()
        strat.fit(view.truncate(cal[train_sl][-1]))
        r = backtest(strat, view, cost_bps=cost_bps)
        test_idx = cal[test_sl]
        rets_parts.append(r.returns.reindex(test_idx).dropna())
        wt_parts.append(r.weights.reindex(test_idx).dropna(how="all"))
    oos_rets = pd.concat(rets_parts) if rets_parts else pd.Series(dtype=float)
    oos_wts = pd.concat(wt_parts) if wt_parts else pd.DataFrame()
    return Result(returns=oos_rets, weights=oos_wts, metrics=metrics(oos_rets))
