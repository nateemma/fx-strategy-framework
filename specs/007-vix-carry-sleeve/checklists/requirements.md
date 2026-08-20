# Specification Quality Checklist: VIX Carry Satellite Sleeve

**Created**: 2026-08-19 | **Feature**: [spec.md](../spec.md)

## Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness
- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

No clarifications were needed: the A1 gate had already settled the rule, the instrument, and the
constraints. Sizing was deliberately left out of code — like every other sleeve, `--allocation` is a
required argument — because it is the whole risk decision here and belongs with the operator.

**Two prior mistakes were avoided by design rather than rediscovered.** The single-symbol per-order
cap is set explicitly (the default made the cash sleeve literally unplaceable), and the sleeve is
registered in the healthcheck **dormant**, because registering the trend sleeve before it could run
produced a nightly false alarm two days earlier.

**One bug was found by running it.** The refuse-on-stale guard fired correctly on first live use — but
for the wrong reason: it was reading a 35-day-old cache rather than current data. The guard exists for
when the data source is behind, not for when we simply did not ask. The runner now refreshes, with the
cache as fallback.

Implemented 2026-08-19, phases 1–3 and polish. 469 tests pass; ruff clean. **Not deployed** — sizing
and funding are Phase 4 and require a decision, since the sleeve must be cash-funded and the account
holds only ~$12.8k in cash.
