# Specification Quality Checklist: Cross-Asset Trend Sleeve (Futures)

**Created**: 2026-08-17 | **Feature**: [spec.md](../spec.md)

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

Two clarifications were resolved with the user before drafting: funding by **reallocation** from the
ETF sleeves (which is what the blend result measured — adding on top would not reproduce the drawdown
improvement) and a **20%** target allocation.

Three findings from the pre-spec feasibility work shaped the scope:

1. **Contract granularity nearly sank it.** At a $200k risk base across 16 markets, 8 of them round
   to 0 or 1 contract — a ≥50% sizing error that would destroy the risk-parity construction that *is*
   the edge. Restricting to the eight markets with workable granularity fixed it.
2. **The narrower universe is better, not a compromise.** The feasible-8 book beat the full 16 on
   Sharpe (0.83 vs 0.78), drawdown (−16.8% vs −21.1%), and correlation to the existing basket
   (+0.06 vs +0.17) — and is *positive* on the basket's 20 worst days rather than merely flat. This is
   a fortunate result rather than a designed one, and it should be re-checked if the universe changes.
3. **The market-data subscription is genuinely blocking.** The A1 gate found IBKR returns 7 daily bars
   on a front-month contract without one — a degraded signal rather than an error, which is the
   dangerous failure mode. FR-007 makes the system refuse rather than trade on it.

**This spec inverts the usual priority order.** Every prior feature put the valuable thing first; here
the signal is P2 and the executor is P1, because this is the first feature to trade an asset class the
engine has never touched. The failure mode is wrong orders in a live account, not a wrong number in a
report.
