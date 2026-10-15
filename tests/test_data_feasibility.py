"""The data cull's record logic. Spec 009 US2.

Filter 1 of this repo's method is "free data, or it does not get built", and this is the machinery
that enforces it. The statuses are terminal by design: a candidate marked dead must not then be
modelled, because the cheapest way to waste a week is to half-build something whose data does not
exist.

Probes are injected, so these tests perform no network I/O.
"""
import pytest

from forex.run.feasibility import DEAD_DATA, DEAD_ECON, TESTABLE, Feasibility, probe_candidate
from strategies.longshort_candidates import BY_ID


def ok_probe(span=("2002-07-30", "2026-10-13"), bars=6045, granularity="1d"):
    def _p(candidate):
        return Feasibility(candidate.id, TESTABLE, "free chart API + FRED", span, bars,
                           granularity, "")
    return _p


def dead_probe(status, note):
    def _p(candidate):
        return Feasibility(candidate.id, status, "checked, nothing free", None, 0, None, note)
    return _p


def test_a_testable_candidate_records_its_span_and_granularity():
    f = probe_candidate(BY_ID["A3"], ok_probe())
    assert f.status == TESTABLE
    assert f.usable_history == ("2002-07-30", "2026-10-13")
    assert f.bars == 6045
    assert f.granularity_confirmed == "1d"


def test_dead_on_data_is_terminal_and_names_what_was_missing():
    f = probe_candidate(BY_ID["B2"], dead_probe(DEAD_DATA, "no free discount/NAV history"))
    assert f.status == DEAD_DATA
    assert f.is_terminal
    assert "discount" in f.note


def test_dead_on_economics_is_terminal():
    f = probe_candidate(BY_ID["B4"], dead_probe(DEAD_ECON, "basis inside commission"))
    assert f.status == DEAD_ECON
    assert f.is_terminal


def test_a_testable_candidate_is_not_terminal():
    assert not probe_candidate(BY_ID["A3"], ok_probe()).is_terminal


def test_a_terminal_record_must_carry_a_note():
    """A rejection without a reason is not reproducible (FR-009), so it is rejected as a record."""
    with pytest.raises(ValueError, match="note"):
        Feasibility("B2", DEAD_DATA, "src", None, 0, None, "").validate()


def test_a_testable_record_must_carry_a_confirmed_granularity():
    """Recording what the source REPORTED rather than what was requested is the guard against the
    silently-monthly trap (research R1)."""
    with pytest.raises(ValueError, match="granularity"):
        Feasibility("A3", TESTABLE, "src", ("2002-01-01", "2026-01-01"), 100, None, "").validate()


def test_an_unknown_status_is_rejected():
    with pytest.raises(ValueError, match="status"):
        Feasibility("A3", "probably fine", "src", None, 0, None, "x").validate()


def test_a_probe_that_raises_is_recorded_as_dead_not_swallowed():
    """A probe blowing up must not silently read as 'testable'."""
    def boom(candidate):
        raise OSError("no such endpoint")

    f = probe_candidate(BY_ID["B3"], boom)
    assert f.status == DEAD_DATA
    assert "OSError" in f.note
