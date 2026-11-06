"""Exit the process when a polling job stops succeeding, so systemd restarts it.

Serial adapters on the node occasionally stall (``ftdi_sio ... urb stopped: -32``).
The interfaces swallow the resulting exceptions, or block forever in a read, so
the scheduler keeps running while no data is produced. A restart reopens the
serial ports and clears the stall. This module automates that restart.

Each job registers with ``register(job_id)`` and its task calls
``report(job_id, ok)`` after every poll. A background thread calls
``os._exit(1)`` if a registered job has had no successful poll for
``timeout_s`` seconds. That also covers a hung read, because the check does not
depend on the job returning. ``confluence.service`` uses ``Restart=on-failure``,
so a non-zero exit brings the node back up.
"""
import os
import threading
import time

DEFAULT_TIMEOUT_S = 60.0
CHECK_PERIOD_S = 5.0

_lock = threading.Lock()
_last_ok = {}
_timeouts = {}


def register(job_id, timeout_s=DEFAULT_TIMEOUT_S):
    """Start watching ``job_id``. The timeout counts from registration."""
    with _lock:
        _last_ok[job_id] = time.monotonic()
        _timeouts[job_id] = timeout_s


def report(job_id, ok):
    """Record the outcome of one poll. Only successes refresh the deadline."""
    if ok:
        with _lock:
            _last_ok[job_id] = time.monotonic()


def _stale_jobs():
    now = time.monotonic()
    with _lock:
        return [(j, now - t) for j, t in _last_ok.items() if now - t > _timeouts[j]]


def _exit():
    os._exit(1)  # hard exit: a thread blocked in a serial read would stall a clean shutdown


def _run():
    while True:
        time.sleep(CHECK_PERIOD_S)
        stale = _stale_jobs()
        if stale:
            for job_id, age in stale:
                print(f"Watchdog: no successful poll from {job_id} in {age:.0f}s; exiting for restart", flush=True)
            _exit()


def start():
    """Begin monitoring. Call after all interfaces are imported and before the
    scheduler starts, so slow imports don't count against the job timeouts."""
    with _lock:
        now = time.monotonic()
        for job_id in _last_ok:
            _last_ok[job_id] = now
    threading.Thread(target=_run, name="confluence-watchdog", daemon=True).start()
