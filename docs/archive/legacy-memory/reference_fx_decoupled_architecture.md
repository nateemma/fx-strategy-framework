---
name: reference_fx_decoupled_architecture
description: FX framework is decoupled — strategies are a sibling strategies/ package with NAME/build discovery; no registry
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

2026-07-13: The forex framework (`~/Documents/forex`, public nateemma/fx-strategy-framework) was restructured so `forex/` imports ZERO concrete strategies.

**Layout:** `forex/` = framework (core/backtest/run/data/diagnostics/cli + generic `features/volforecast.py` ewma_vol + `features/carry.py` carry_signal). `strategies/` = SIBLING package importing forex (carry/momentum/value/trend/overlay/mloverlay/blend + `strategies/features/` for basket_weights/signal maths/HAR mlvol + `strategies/research/`).

**Adding a strategy now = drop a file in `strategies/`** — NO central registry (it was deleted). A strategy is a `Strategy` subclass with a class-level `NAME` and (if composed/defaulted) a `build(cls, params)` classmethod. `forex/core/discovery.py` eagerly scans the `strategies` package and collects classes where `"NAME" in cls.__dict__ and cls.NAME`. Composition bases (VolTargetOverlay/MLVolTargetOverlay/BlendStrategy) have no NAME → not discoverable. Composed named configs (e.g. `carry_voltarget`, `carry_trend`) are thin NAME+build subclasses co-located with their factor, using `forex/core/compose.py` helpers (`split_params`, `split_prefixed`, `build_components`).

**Key facts:** `build_strategy(name, params, package="strategies")` / `available()` live in `forex/core/discovery.py`. `optimize()` takes an injected `build` callable (DI) — `forex/run/hyperopt.py` imports nothing strategy-related; the CLI is the composition root. `carry_signal` STAYS framework (backtest carry accrual uses it); `ewma_vol` STAYS framework; `basket_weights`/momentum/value/trend signals/HAR moved to `strategies/features/`. Pure refactor — 148 tests, byte-identical behaviour. The 13 strategy NAMEs are unchanged.

**How to apply:** Don't look for `registry.py` (gone). To add a strategy: new file in `strategies/` with a NAMEd `Strategy` subclass; it's instantly available to backtest/walkforward/hyperopt/causal-check/CLI. Spec: `docs/superpowers/specs/2026-07-13-strategy-decoupling-design.md`; review: `docs/architecture-review.md`. Remaining follow-up: README rewrite (concern 3) — see [[project_deployable_blend]] context for the flagship result to lead with.
