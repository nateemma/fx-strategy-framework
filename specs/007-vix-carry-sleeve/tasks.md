# Tasks: VIX Carry Satellite Sleeve

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [A1 gate](../../docs/vix-carry-findings.md)

**Tests**: REQUIRED (Constitution III). Test tasks precede implementations.

---

## Phase 1: User Story 1 — The decision (Priority: P1) 🎯 MVP

- [X] T001 Write failing tests for the contango rule — in when VIX3M > VIX, out when not, at the boundary, and that the decision uses only prior data (FR-001, FR-002) — in `tests/test_vix_carry.py`
- [X] T002 Write failing tests that stale term-structure data refuses rather than trading (FR-003) — in `tests/test_vix_carry.py`
- [X] T003 Implement the signal and target in `strategies/vix_carry.py`, reporting the values behind the decision (FR-011)

**Checkpoint**: the in/out decision is settled and explainable, with no broker involved.

---

## Phase 2: User Story 2 — Placement (Priority: P2)

- [X] T004 Implement `scripts/vix_carry_sleeve.py` — preview by default, `--confirm` arms placement, `--allocation` required, `max_order_frac=1.0` for the single-symbol case (FR-005, FR-006)
- [X] T005 Verify against the live account in preview that an unchanged decision produces no orders (FR-004)
- [X] T006 Write the positions record on applied runs, reusing `forex/run/basket_track.py` (FR-008)

---

## Phase 3: User Story 3 — Schedule and watch (Priority: P3)

- [X] T007 Add a daily `com.fx.vix-carry` agent before the US open in `scripts/install_schedules.sh`
- [X] T008 Add the sleeve to `WATCHED` in `forex/run/health.py`, **dormant until first deployed**, and update its tests
- [X] T009 Add the positions CSV and log to `.gitignore`

---

## Phase 4: Deploy

- [ ] T010 Decide the allocation with the operator — the gate supports up to 10% of the ETF track, the tail argues for the lower end, and it must be cash-funded
- [ ] T011 Preview against the live account and confirm the decision matches the current term structure
- [ ] T012 Place, verify the fill, and enable the healthcheck entry

---

## Phase 5: Polish

- [X] T013 Run `pytest -q` and `ruff check .`; confirm green with no new violations
- [ ] T014 Update `specs/000-baseline/baseline.md` and document the sleeve in `docs/scheduled-paper-track.md`

---

## Implementation Strategy

**Small feature, two real constraints.** The code is a thin layer over `BasketExecution`; what matters
is the execution lag the gate did not model and the tail the instrument has never seen.

**T008 registers the sleeve DORMANT.** Adding a job to the watch list before it can run produced a
nightly false alarm two days ago. The `enabled` flag exists because of that; use it.

**T010 is a conversation, not a task.** Sizing is the whole risk decision here: a −40% to −50% sleeve
loss is survivable at 5% of the book and unpleasant at 10%.
