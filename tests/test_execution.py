import pandas as pd, pytest
from forex.run.execution import SimExecution, LiveExecution, RebalanceReport

def test_first_rebalance_inits_and_applies(tmp_path):
    pf = tmp_path / "pf.json"
    ex = SimExecution(pf, starting_equity=10000.0, cost_bps=0.0)
    r = ex.rebalance(pd.Series({"AUD": 1.0, "EUR": -1.0}), pd.Series({"AUD": 1.0, "EUR": 1.1}))
    assert r.applied and pf.exists()
    assert r.positions == {"AUD": 1.0, "EUR": -1.0}
    assert round(r.turnover, 6) == 2.0                # 0->1 and 0->-1
    assert round(r.orders["AUD"], 2) == 10000.0       # weight delta * equity
    assert round(r.equity, 2) == 10000.0              # cost 0, no prior book to mark

def test_second_rebalance_marks_to_market(tmp_path):
    pf = tmp_path / "pf.json"
    ex = SimExecution(pf, starting_equity=10000.0, cost_bps=0.0)
    ex.rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.0}))       # long AUD @ 1.0
    r = ex.rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.10}))  # AUD +10%, same weight
    assert round(r.equity, 2) == 11000.0              # 10000 * 1.10, no turnover -> no cost

def test_preview_writes_nothing(tmp_path):
    pf = tmp_path / "pf.json"
    r = SimExecution(pf, preview=True).rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.0}))
    assert r.applied is False and not pf.exists()

def test_max_position_weight_clips(tmp_path):
    r = SimExecution(tmp_path / "pf.json", max_position_weight=0.5, cost_bps=0.0
                     ).rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.0}))
    assert r.positions["AUD"] == 0.5

def test_live_execution_is_not_implemented():
    with pytest.raises(NotImplementedError):
        LiveExecution().rebalance(pd.Series(dtype=float), pd.Series(dtype=float))
