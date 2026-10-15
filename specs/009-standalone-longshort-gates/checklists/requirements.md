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

## Post-analysis record (2026-10-15)

`/speckit-analyze` ran after tasks generation: **0 critical, 2 high, 2 medium, 4 low**, 90% requirement
coverage. All eight findings were resolved. Two were resolved by *deciding and recording* rather than by
changing anything, which is logged here so they are not re-raised:

- **U2 — SC-002 ("no candidate consumes more than one working day") has no verification mechanism.**
  **Accepted as unverifiable by design.** It is a *budget* the operator holds, not a property of the
  software, and inventing a timing harness to police an afternoon would cost more than the afternoon.
  The kill criteria in the register (T001) are the real enforcement: they are what make a day enough.
- **D1 — the no-Gateway constraint is restated in spec (5×), plan (3×), research, quickstart and tasks.**
  **Accepted as deliberate.** Normally this would be redundancy worth trimming; here the paper track was
  shut down days earlier and the operator asked specifically whether this feature needs the Gateway, so
  repetition at every entry point is the point. It is now also enforced by a test (T014) rather than only
  asserted.

The six substantive fixes: a new **T014** making FR-012/SC-005 structural (they had *zero* verifying
tasks, on a NON-NEGOTIABLE principle); **T032** extended to cover B4, which had no verdict path if it
survived its economics check and is the likeliest survivor; **T007** extended to pin the
`(recent, distant)` return order of `distant_window()`, which reads backwards and would otherwise
silently invert every verdict's eras while all other tests passed; **T011** extended to assert a missing
benchmark fails (FR-002 required it and nothing checked it); **T019/T035** now record the chosen
`holdout_years` and window boundaries, without which a per-candidate judgement call makes the verdict
irreproducible; and plan.md's structure tree updated with the four files tasks.md had introduced.

Tasks renumbered T001→T037 to insert T014 in execution order; verified no duplicates, no gaps, and every
cross-reference resolving.

**One scope note for the planning phase.** SC-002 budgets one working day per candidate, and FR-005
requires the data gate before any modelling. These two together are what keep the feature bounded, and
they are in tension with doing A3 first (US1), which also has to build the shared harness. The plan
should put the *harness* cost on US1 explicitly rather than pretending the first verdict is as cheap as
the later ones.
