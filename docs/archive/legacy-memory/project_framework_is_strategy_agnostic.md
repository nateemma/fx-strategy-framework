---
name: forex is a GENERAL FX framework; carry/G10 is only the first strategy
description: The forex project is a general, strategy-agnostic systematic-FX framework — NOT a carry project. G10 carry + the vol-target overlay are the first reference implementation, not the purpose. Keep strategy-specific assumptions inside strategy classes; the core/drivers must never assume carry, the G10 universe, or any signal.
metadata:
  node_type: memory
  type: project
---

2026-07-12: The user corrected the framing ("this is intended as a general tool for any forex
trading — we happen to be using G10 and the carry trade as a first implementation").

**The principle:** the framework (`DataView`/`Strategy`/`Result`, the `backtest`/`walk_forward`/
`hyperopt` drivers, `assert_causal`, config tiers, registry, CLI) is strategy-agnostic. Its only
contract with a strategy is the atom: *point-in-time data → target currency weights*. A driver or
`DataView` that "knows" about carry, rate differentials, or the specific G10 set is a design smell —
the carry-ness lives ONLY in `forex/strategies/` and the signal maths it calls (`forex/features/`).

**How to apply:**
- New strategies (momentum, value/PPP, mean-reversion, ML-fitted, any universe) are added by
  implementing `Strategy.target_weights` (+ optional `fit`/`params`/`search_space`) and registering a
  name in `forex/strategies/registry.py`. Every mode then works unchanged. See README "Adding a
  strategy" and the "Framework vs strategies" section in the architecture spec.
- Do NOT put strategy-specific constants/branches in `forex/core/` or `forex/run/`. (Direct echo of
  the crypto lesson [[feedback_framework_directory]] / no-strategy-specific-code, now for FX.)
- The ONE deliberate exception: carry accrual in `backtest` (the rate differential) is a market fact
  of holding any FX position, not a strategy property — so it's computed from the `DataView` and
  applies to every strategy uniformly.
- When writing new specs/plans, frame carry as "the first reference strategy", not "the strategy".
