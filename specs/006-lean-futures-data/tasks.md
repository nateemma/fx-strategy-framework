# Tasks: Futures History via LEAN

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [lean-migration-plan.md](../../docs/lean-migration-plan.md)

**Tests**: REQUIRED for the loader (Constitution III). The gate is a document.

---

## Phase 1: User Story 1 — The gate (Priority: P1) 🎯 *the whole decision*

- [ ] T001 Install the LEAN CLI and confirm it runs locally in Docker without a cloud subscription
- [ ] T002 Determine whether QC/LEAN carries daily history for M2K, MES, ZT, ZF, M6E, M6A, MCL, ZC, and from what date per market (FR-001)
- [ ] T003 Determine the roll convention — adjusted, unadjusted, or individual contracts available (FR-002). **This is the crux**: an unadjusted continuous series is unusable and closes the feature
- [ ] T004 Determine cost, and whether `lean data download` works locally without a subscription (FR-003)
- [ ] T005 Write `docs/lean-data-gate.md` with all four answers and a clear PASS/FAIL, in the form every prior gate took (FR-004)

**⛔ STOP HERE IF THE GATE FAILS.** A recorded negative and an unchanged repo is a good outcome.

---

## Phase 2: User Story 2 — The loader (Priority: P2, conditional on the gate)

- [ ] T006 Write failing tests for the loader against fixtures — caching, offline reads, and that short or missing data raises rather than truncating (FR-007, FR-008) — in `tests/test_lean_data.py`
- [ ] T007 Implement `forex/data/lean.py`: read LEAN's on-disk output, write `data_cache/*.parquet`, mirroring `forex/data/fred.py` (FR-005, FR-006)
- [ ] T008 Record the roll convention alongside the cached series so no downstream user can be unaware of it (FR-002)
- [ ] T009 Download and cache the eight markets; report coverage per market
- [ ] T010 Run `.venv/bin/python -m pytest -q` and `ruff check .`; confirm the suite is still network-free

---

## Phase 3: Handover

- [ ] T011 Update `specs/000-baseline/baseline.md` with the gate outcome and what it unblocks
- [ ] T012 If the gate passed, open the next feature: re-run the A2 trend gate on futures data (migration-plan stage 2). **Not** part of this feature

---

## Dependencies

```
Phase 1 (gate) ── fails ──> STOP, record the negative
      └─ passes ─> Phase 2 (loader) ─> Phase 3 (handover)
```

## Implementation Strategy

**The gate is the deliverable.** T001–T005 answer whether any of this is worth doing, and a failure
there is a successful outcome that costs an afternoon and leaves the framework untouched.

**Do not let this become a migration.** The spec's Out of Scope section and the staged plan's
stop-decision exist because "while we're in here" is how a one-input problem turns into a rewrite of
453 tests' worth of working, paper-validated machinery.

**The prize, if it passes**, is closing the A2 gate's acknowledged ETF-proxy-versus-futures gap — and
incidentally unblocking commodity carry, which has been stuck on roll-adjusted data since July.
