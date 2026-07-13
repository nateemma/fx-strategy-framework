# Architecture Review — FX Strategy Framework

*2026-07-13. Review + recommendations for restructuring toward modularity/extensibility. Three
concerns raised: (1) pull strategies out of the framework directory; (2) replace the registry with
dynamic loading + self-describing strategies; (3) rewrite the README for the general framework.*

## Current state

Layering is **already sound at the core**: `core/`, `backtest/`, `run/`, `diagnostics/`, `data/`
import zero concrete strategies. The only strategy coupling is `registry.py`, reached by `cli.py` and
`run/hyperopt.py`. ~1,260 LOC, 138 tests guard any move.

Weaknesses matching the three concerns:
- **Mixing:** `forex/strategies/` and `forex/features/` (strategy signal maths) live *inside* the
  framework package.
- **Central registry:** adding a strategy means hand-editing `registry.py` (imports + builder +
  `available()` set).
- **Stale, carry-centric README:** "~65 tests" (actually 138), "four modes" (six), `--strategy: carry
  or carry_voltarget` (13 exist), "sklearn later" (went numpy), results carry-only (no
  momentum/value/trend/**blend** — the actual headline).

## Concern 1 — pull strategies out of the framework directory

**Recommendation: a sibling `strategies/` package that imports `forex` (framework as a library).**

```
forex/                    # THE FRAMEWORK (strategy-agnostic library)
  core/ backtest/ run/ diagnostics/ data/ cli.py
  features/volforecast.py   # generic vol utils stay (ewma_vol; HAR is a judgment call)
strategies/               # THE STRATEGY LIBRARY (imports forex)
  carry.py momentum.py value.py trend.py overlay.py mloverlay.py blend.py
  features/                 # strategy signal maths (carry_signal, trend_signal, …)
  research/
```

Split line: **"does it know a specific signal?"** `carry_signal`/`trend_signal`/etc. → `strategies/`;
`ewma_vol` stays generic. Keep `config.py`'s `CURRENCIES` (G10 universe) and `data/prices.py` in
`forex/data/` — FX *data* config, shared by all strategies, not strategy-specific. Aligns with the
standing "framework directory stays strategy-agnostic" principle.

Effort: medium-mechanical (import rewrites + `pyproject` packages), low logic risk, suite-guarded.

## Concern 2 — replace the registry with self-describing strategies

**Recommendation: Option A — discovery + a checked contract.**
- `Strategy` base gains required, load-time-checked members:
  ```python
  class Strategy(ABC):
      NAME: str                                    # required; checked (non-empty, unique)
      @classmethod
      def build(cls, params: dict) -> "Strategy":   # default cls(**params); OVERRIDE for
          return cls(**params)                      # defaults / composition / param-routing
      @abstractmethod
      def target_weights(self, view): ...
  ```
- A loader imports the `strategies/` package (or `strategies/<name>.py` on demand), collects every
  `Strategy` subclass exposing a `NAME` → name→class map at runtime. **Add a strategy = drop a file.**
  Missing/duplicate NAME raises at load (the "checked override").
- Param-routing/defaults currently in `registry.py` move onto each composed strategy's `build`, using
  shared helpers in a `forex.core.compose` (`split_params(prefixes)`, …). Named configs (e.g.
  `carry_trend` with ema/108 defaults) become small `Strategy` subclasses that live with their
  definitions. `registry.py` shrinks to a ~20-line discovery loop.

**Option B (pure path loading, `--strategy path/to/file.py`)** — supported as an optional escape
hatch, not the primary mechanism (arbitrary-path import is a robustness/security surface; loses
`available()`).

## Coupling insight: concerns 1 and 2 are linked

Pulling strategies out **cleanly** requires a bit of concern 2. If `strategies/` is a sibling package,
`registry.py` (which hard-imports strategy classes) must live on the strategy side — but then
`forex/cli.py` and, worse, the framework-core `forex/run/hyperopt.py` would import `strategies.*`,
i.e. the framework depending on the strategy library. Two ways out:
- **Dependency injection:** `optimize(...)` should take a `strategy_factory` callable (like
  `walk_forward` already does) rather than importing `build_strategy`; the CLI (the composition root)
  wires the builder in. Removes the framework-core → catalog edge.
- **Discovery:** the CLI resolves a strategy name via a loader that scans a configured strategies
  location, so no module hard-imports specific strategies.

**Therefore: do concerns 1 & 2 as one coordinated restructure**, or sequence 1→2 accepting a
transitional `cli.py → strategies.registry` edge (core stays clean; only the app entry knows the
catalog). Recommendation: **combined**, because "strategies out" isn't truly clean until the framework
stops importing them — which is concern 2.

## Concern 3 — README for the general framework

**Recommendation: lead with the framework + strategy *library*; demote carry to one reference; fix
staleness.**
- Lead with the `Strategy` contract ("one definition, every mode") + the post-restructure layout.
- Add a **Strategy Library** table (carry/momentum/value/trend/overlay/blend) with the honest flagship
  result up top: `carry_trend_voltarget`, **OOS Sharpe 0.52**, not bare carry.
- Results = the factor-stack narrative (carry 0.32 → +trend 0.50 → vol-targeted 0.52; momentum
  benched; value dilutes), leverage-scaled-to-your-vol-budget framing.
- Fix facts: six modes (add `download`/`dryrun`), 138 tests, numpy (drop sklearn), full `--strategy`
  list, real date range.
- Keep the FX-concepts primer + the framework-general vs strategy-specific split.

Effort: low, standalone, zero code risk. Do it **last** so it documents the final structure.

## Suggested sequencing

1. **Concern 1 + 2 combined** (decouple strategies into a discoverable sibling package with
   dependency-injected building) — the real extensibility win; suite-guarded to stay behaviour-identical.
2. **Concern 3** (README) — document the end state.

Each is its own brainstorm → spec → subagent-driven build.
