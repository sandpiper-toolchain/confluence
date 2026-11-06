import importlib.util
import pathlib
import time

# Load by path so the test doesn't need apscheduler (imported by the package __init__).
_spec = importlib.util.spec_from_file_location(
    "watchdog", pathlib.Path(__file__).parents[1] / "Interfaces" / "Scheduler" / "watchdog.py"
)
watchdog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watchdog)


def _reset():
    watchdog._last_ok.clear()
    watchdog._timeouts.clear()


def test_fresh_job_not_stale():
    _reset()
    watchdog.register("a", timeout_s=60)
    assert watchdog._stale_jobs() == []


def test_failures_do_not_refresh_deadline():
    _reset()
    watchdog.register("a", timeout_s=0.05)
    time.sleep(0.1)
    watchdog.report("a", False)
    assert [j for j, _ in watchdog._stale_jobs()] == ["a"]


def test_success_refreshes_deadline():
    _reset()
    watchdog.register("a", timeout_s=0.05)
    time.sleep(0.1)
    watchdog.report("a", True)
    assert watchdog._stale_jobs() == []


def test_start_resets_clocks_and_stale_job_exits(monkeypatch):
    _reset()
    codes = []
    monkeypatch.setattr(watchdog, "_exit", lambda: codes.append(1))
    monkeypatch.setattr(watchdog, "CHECK_PERIOD_S", 0.02)
    watchdog.register("a", timeout_s=0.1)
    time.sleep(0.15)  # slow startup would be stale...
    watchdog.start()  # ...but start() restarts the clock
    assert watchdog._stale_jobs() == []
    time.sleep(0.3)  # now no successes arrive
    assert codes
