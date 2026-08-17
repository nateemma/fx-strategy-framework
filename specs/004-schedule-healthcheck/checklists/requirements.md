# Specification Quality Checklist: Scheduled-Job Healthcheck

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

Two clarifications were resolved with the user before the spec was written: the alert channel
(desktop notification plus a durable status file, declining email for the secret it would need) and
the check scope (all three jobs by artifact staleness).

**Two design errors were caught by tests during implementation, not by review:**

1. The original model compared artifact *age* against a cadence. A test asserting the real 2026-08-01
   failure would be caught proved it would not: a monthly artifact is legitimately up to 31 days old,
   so an age threshold cannot flag a missed run until an entire extra cycle passes. Redesigned to
   compare against the last scheduled *fire time*, which catches it within grace.
2. Grace was then applied against the most recent fire time, meaning a job dead for weeks looked
   healthy whenever the check ran shortly after a fire — grace reset every cycle. Fixed by comparing
   against the last fire time that is itself older than grace.

A third bug was caught by making the code testable: the notification command was built with Python's
`repr()`, producing single-quoted strings. AppleScript requires double quotes and rejects single ones
outright, so the notification would never have fired — it would have failed silently into the
best-effort handler. Moved into the module with a regression test that actually executes `osascript`.

Implemented 2026-08-16, all 19 tasks. 391 tests pass; ruff unchanged at 21 pre-existing violations.
**Not yet installed** — `scripts/install_schedules.sh` needs `FRED_API_KEY` from the operator's shell.
