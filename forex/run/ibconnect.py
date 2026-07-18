"""Connect to IB Gateway with retry — rides through the brief daily auto-restart window.

IB Gateway's auto-restart (auto-logon) briefly drops the API each day; a bare connect fails during that
window. connect_with_retry retries transient connection failures (refused / timeout) with a fixed backoff
so unattended scheduled jobs survive the restart. Non-connection errors (e.g. auth) are NOT retried."""
import asyncio
import sys
import time


def connect_with_retry(ib, host, port, client_id, *, readonly, timeout=15,
                       retries=6, backoff=10.0, sleep=None):
    """Call ib.connect(...), retrying refused/timeout connects with `backoff` seconds between tries.
    Returns on success; raises the last error after `retries` failed attempts."""
    sleep = sleep or time.sleep
    last = None
    for attempt in range(1, retries + 1):
        try:
            ib.connect(host, port, clientId=client_id, timeout=timeout, readonly=readonly)
            return
        except (OSError, asyncio.TimeoutError, TimeoutError) as e:
            last = e
            if attempt < retries:
                print(f"IB connect attempt {attempt}/{retries} failed ({e!r}); retrying in {backoff:.0f}s",
                      file=sys.stderr)
                sleep(backoff)
    raise last
