"""Can a candidate be tested at all, with free data? Spec 009 US2.

Filter 1 of this repo's method: *free data, or it does not get built.* This is the cheapest gate
there is and it runs before any modelling, because the expensive mistake is half-building a
strategy whose history does not exist.

The statuses are terminal on purpose. `dead_on_data` and `dead_on_economics` mean *stop* — not
"revisit with a bigger model", which is how closed questions get relitigated.
"""
from typing import NamedTuple

TESTABLE, DEAD_DATA, DEAD_ECON = "testable", "dead_on_data", "dead_on_economics"
STATUSES = (TESTABLE, DEAD_DATA, DEAD_ECON)


class Feasibility(NamedTuple):
    candidate_id: str
    status: str
    source_checked: str          # specific enough that someone can re-check it
    usable_history: tuple | None  # (first, last) as ISO dates
    bars: int
    granularity_confirmed: str | None  # what the source REPORTED, not what was asked for
    note: str                    # what was missing, when dead

    @property
    def is_terminal(self) -> bool:
        return self.status in (DEAD_DATA, DEAD_ECON)

    def validate(self) -> "Feasibility":
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}; expected one of {STATUSES}")
        if self.is_terminal and not self.note.strip():
            raise ValueError(f"{self.candidate_id}: a terminal record needs a note saying why — "
                             f"a rejection without a reason is not reproducible")
        if self.status == TESTABLE and not self.granularity_confirmed:
            raise ValueError(f"{self.candidate_id}: a testable record must carry the granularity "
                             f"the source REPORTED — see spec 009 research R1")
        return self


def probe_candidate(candidate, probe) -> Feasibility:
    """Run `probe` for one candidate, turning a failure into a recorded death rather than a crash.

    A probe that raises is `dead_on_data` with the exception named: an endpoint that does not answer
    is indistinguishable, for our purposes, from data that does not exist — and silently treating it
    as testable would be the worse error.
    """
    try:
        return probe(candidate).validate()
    except (ValueError, TypeError) as exc:
        if "status" in str(exc) or "note" in str(exc) or "granularity" in str(exc):
            raise
        return Feasibility(candidate.id, DEAD_DATA, "probe raised", None, 0, None,
                           f"{type(exc).__name__}: {exc}")
    except Exception as exc:              # noqa: BLE001 - a dead probe is a finding, not a crash
        return Feasibility(candidate.id, DEAD_DATA, "probe raised", None, 0, None,
                           f"{type(exc).__name__}: {exc}")
