# Specification Quality Checklist: FX-Only Performance Reporting

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-16
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
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

**Iteration 1 (2026-08-16)** — two [NEEDS CLARIFICATION] markers raised, both because no reasonable
default existed and each materially changes the headline number the operator judges the strategy by.

**Iteration 2 (2026-08-16)** — both resolved by the user; markers removed and requirements rewritten:

- **FR-009** — FX returns are expressed against **gross FX exposure**, matching the basis on which
  the walk-forward expectation is quoted, so realised vs expected is a like-for-like comparison.
- **FR-008** — rebalance-contaminated observations are **excluded and counted**, not silently
  dropped. Costs ~1 observation per month; preferred to a knowingly wrong value in a small sample.

All checklist items pass. Spec is ready for `/speckit.plan`.

**Carried into planning** (not spec defects):

1. The spec assumes rebalance days are identifiable from the recorded history alone (a jump in gross
   exposure, and unsettled FX trades briefly inflating the position count). The plan MUST verify this
   detection is reliable before relying on it — the alternative source, the activity log, is not
   versioned and so cannot be reproduced from a clone.
2. No git branch was created; no `before_specify` hook is installed, so the spec directory is the
   feature identity and work proceeds on `main`.
3. Only one snapshot with FX values exists today. The feature is fully buildable and testable now
   against constructed histories, but will not yield a meaningful live reading for several weeks.
