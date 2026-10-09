# Specification Quality Checklist: Truthful Outage Detection

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-09
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

Validation run 2026-10-09. Three items needed a second pass:

1. **"No implementation details"** — the first draft named `forex/run/health.py`, `check_health()`,
   `st_mtime`, and `track.log` inside the functional requirements. Those are *how*, not *what*. Moved the
   file-level detail into the "Why this exists" narrative and the Assumptions section, where it belongs as
   evidence, and restated FR-001/FR-002 behaviourally. The narrative keeps them deliberately: this spec's
   credibility rests on naming the exact defect, and a reader who cannot see which file lied cannot check
   the claim.
2. **"Success criteria are technology-agnostic"** — SC-002 originally read "port 4002 probe completes in
   under 2s", which is a mechanism, not an outcome. Replaced with the operator-facing latency (within one
   hour, against the 25 days actually observed).
3. **"Requirements are testable"** — an early FR said the watchdog should "recover sensibly", which is not
   testable. Split into FR-011 (must not start a second instance) and FR-012 (must start when none is
   running), both directly assertable with an injected process check.

**No [NEEDS CLARIFICATION] markers were left**, but one decision was made by informed default rather than
by the operator and is flagged in Assumptions: a wedged-but-alive Gateway is **alerted, not auto-recovered**.
The evidence for that default is in-repo and strong (duplicate login silently kills market data; a hard kill
measured 3h42m of server-side session lock), but it trades recovery speed for safety and is the one thing in
this spec worth an explicit yes/no before planning.

One deliberate exception to "no implementation details": FR-015 names `tests/test_health.py` and its 26
tests. That is a regression constraint the operator stated explicitly and it has to be checkable, so the
file is named on purpose rather than as leaked design.

One pre-existing discrepancy noticed while reading the constitution, unrelated to this feature and not
fixed here: `CLAUDE.md` cites the constitution as v1.0.0; `.specify/memory/constitution.md` is v1.1.0.
