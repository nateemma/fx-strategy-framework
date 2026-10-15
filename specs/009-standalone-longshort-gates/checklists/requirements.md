# Specification Quality Checklist: Standalone Long/Short Candidate Gates

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-15
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

Validation run 2026-10-15. Three items needed a second pass:

1. **"No implementation details"** — the first draft named FRED, the Yahoo chart API, `forex/data/`,
   and the specific ETF tickers (SHY/IEF/TLT, TIP, HYG/LQD) inside the functional requirements. Those
   are *how*. FR-013 now says "free sources, cached locally"; the named sources moved to Assumptions as
   the evidence for believing the data exists, which is where a reader checking feasibility wants them.
   The candidate list in "Why this exists" keeps its survey IDs deliberately — without them the reader
   cannot tie a verdict back to the thing that was ranked.

2. **"Success criteria are measurable"** — SC-007 originally read "most candidates are expected to be
   rejected quickly", which is not checkable. Now "at least three of the six rejected on data
   availability or economics within hours each", with the explicit failure condition that a feature
   where everything "needs more investigation" has failed.

3. **"Requirements are testable"** — an early requirement said candidates should be "judged fairly on
   their own merits", which is unfalsifiable. Split into FR-001 (standalone is the bar, and
   portfolio contribution may not be the reason for a rejection) and FR-002 (must beat a stated simpler
   alternative), both of which a reviewer can check against a findings doc.

**No [NEEDS CLARIFICATION] markers.** One judgement was made by informed default rather than asked: the
pass bar is **comparative, not absolute** — "beats the simpler alternative, net, in both eras" — with no
fixed Sharpe threshold. This follows the repo's own practice, where the momentum basket was killed by
losing to equal-weight of its own names and RSP by losing to SPY, rather than by missing a number. An
absolute bar would have to be invented, and inventing one would be the more arbitrary choice.

**One scope note for the planning phase.** SC-002 budgets one working day per candidate, and FR-005
requires the data gate before any modelling. These two together are what keep the feature bounded, and
they are in tension with doing A3 first (US1), which also has to build the shared harness. The plan
should put the *harness* cost on US1 explicitly rather than pretending the first verdict is as cheap as
the later ones.
