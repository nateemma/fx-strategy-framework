"""Spec 009 must never touch a broker. This makes that structural instead of promised.

FR-012 and SC-005 say nothing in this feature may connect to a broker, require the IB Gateway, or
place an order — and Principle IV is NON-NEGOTIABLE. The `/speckit-analyze` pass on 2026-10-15
found those requirements had ZERO verifying tasks: the plan asserted compliance and nothing checked
it.

The realistic way it erodes is not malice. It is somebody needing a price mid-implementation and
reaching for `forex.data.ibkr`, which already exists and already works. This test is what turns
"we don't think it does" into "it cannot".

The paper track and all seven launchd agents were stopped on 2026-10-14 and stay stopped.
"""
import ast
from pathlib import Path

import pytest

FEATURE_MODULES = [
    "forex/data/yahoo.py",
    "forex/backtest/gate.py",
    "strategies/longshort_candidates.py",
    "strategies/curve_spread.py",
    "strategies/macro_spread.py",
    "scripts/gate_data_feasibility.py",
    "scripts/gate_candidate.py",
]

FORBIDDEN = (
    "ib_async",                  # the broker library itself
    "forex.run.execution",       # FX executor
    "forex.run.basket",          # ETF executor
    "forex.run.futures",         # futures executor
    "forex.run.ibconnect",       # the connect-with-retry helper
    "forex.data.ibkr",           # broker-sourced prices — the realistic slip
)

ROOT = Path(__file__).resolve().parents[1]


def _imports(path: Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("rel", FEATURE_MODULES)
def test_no_feature_module_imports_a_broker_path(rel):
    path = ROOT / rel
    if not path.exists():
        pytest.skip(f"{rel} not implemented yet")
    found = _imports(path)
    for bad in FORBIDDEN:
        offenders = {n for n in found if n == bad or n.startswith(bad + ".")}
        assert not offenders, (
            f"{rel} imports {sorted(offenders)} — spec 009 must not reach a broker (FR-012). "
            f"If a price is needed, use forex.data.yahoo or forex.data.fred.")


def test_the_guard_covers_every_module_the_feature_adds():
    """A guard that silently stops covering new files is worse than none. If this feature grows a
    module, it belongs in FEATURE_MODULES."""
    declared = {ROOT / m for m in FEATURE_MODULES}
    actual = set()
    for pattern in ("scripts/gate_*.py", "strategies/curve_spread.py",
                    "strategies/macro_spread.py", "strategies/longshort_candidates.py",
                    "forex/data/yahoo.py", "forex/backtest/gate.py"):
        actual.update(ROOT.glob(pattern))
    missing = sorted(p.relative_to(ROOT).as_posix() for p in actual - declared)
    assert not missing, f"these feature modules are not covered by the guard: {missing}"
