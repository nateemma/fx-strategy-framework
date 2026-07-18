import pytest
from forex.run.ibconnect import connect_with_retry


class _IB:
    def __init__(self, fail_times=0, exc=None):
        self.fail_times = fail_times
        self.exc = exc or ConnectionRefusedError("refused")
        self.calls = 0
        self.args = None

    def connect(self, host, port, clientId, timeout, readonly):
        self.calls += 1
        self.args = dict(host=host, port=port, clientId=clientId, timeout=timeout, readonly=readonly)
        if self.calls <= self.fail_times:
            raise self.exc


def test_succeeds_first_try_no_sleep():
    ib = _IB(fail_times=0); slept = []
    connect_with_retry(ib, "h", 1, 2, readonly=True, sleep=slept.append)
    assert ib.calls == 1 and slept == []


def test_retries_then_succeeds():
    ib = _IB(fail_times=2); slept = []
    connect_with_retry(ib, "h", 1, 2, readonly=True, retries=6, backoff=10, sleep=slept.append)
    assert ib.calls == 3 and slept == [10, 10]


def test_exhausts_and_raises_last():
    ib = _IB(fail_times=99); slept = []
    with pytest.raises(ConnectionRefusedError):
        connect_with_retry(ib, "h", 1, 2, readonly=True, retries=3, backoff=5, sleep=slept.append)
    assert ib.calls == 3 and slept == [5, 5]      # no sleep after the final failed attempt


def test_timeout_is_retried():
    ib = _IB(fail_times=1, exc=TimeoutError("timed out")); slept = []
    connect_with_retry(ib, "h", 1, 2, readonly=True, retries=4, backoff=3, sleep=slept.append)
    assert ib.calls == 2 and slept == [3]


def test_non_connection_error_not_retried():
    class C:
        def connect(self, *a, **k): raise ValueError("auth failure")
    with pytest.raises(ValueError):
        connect_with_retry(C(), "h", 1, 2, readonly=True, retries=6, sleep=lambda s: None)


def test_passes_connect_args_through():
    ib = _IB(fail_times=0)
    connect_with_retry(ib, "127.0.0.1", 4002, 26, readonly=False, timeout=20)
    assert ib.args == dict(host="127.0.0.1", port=4002, clientId=26, timeout=20, readonly=False)
