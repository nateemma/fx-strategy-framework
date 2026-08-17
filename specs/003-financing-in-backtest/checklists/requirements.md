# Specification Quality Checklist: Financing Cost in the Backtest

**Created**: 2026-08-16 | **Feature**: [spec.md](../spec.md)

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

No clarifications were needed: feature 002 had already established the schedule and the target the
model calibrates against, so the method and its limits were known before the spec was written.

**One assumption was corrected during implementation.** The spec originally claimed the modelled cost
was a *lower bound*, since the zero-interest tranche is not modelled. The cross-check disproved it:
the model charges −2.75% of gross against −2.18% measured, because rate levels come from FRED rather
than IBKR's own benchmark and FRED currently runs higher for several currencies, inflating the floored
credit shortfall. The approximations push both ways, so it is not a bound. Corrected in the spec and
the module docstring.

Implemented 2026-08-16, all 20 tasks. 370 tests pass; ruff unchanged at 21 pre-existing violations.
