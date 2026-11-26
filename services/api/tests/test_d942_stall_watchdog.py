"""D942: the stall watchdog of a self-test run (owner, 26 Nov 2026: "will they get stuck again?", "Your recomendation is
accepted"). Nothing moving for 15 minutes records "stalled at <step>" and closes the browsers; another 15 ends the run."""

from __future__ import annotations

import inspect
import signal
from pathlib import Path

from eax.testing import run, watchdog


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _dog(**kw):
    clock, stalls, closed, interrupts = Clock(), [], [], []
    d = watchdog.Watchdog(lambda step, idle: stalls.append((step, idle)), limit=900, clock=clock,
                          close=lambda: closed.append(1) or 1, interrupt=lambda: interrupts.append(1), **kw)
    return d, clock, stalls, closed, interrupts


def test_the_limit_is_fifteen_minutes():
    assert watchdog.LIMIT == 900


def test_moving_is_not_a_stall():
    d, clock, stalls, closed, _ = _dog()
    for _ in range(10):
        clock.t += 600
        d.touch("reports: from the screens")
        assert d.look() == ""
    assert not stalls and not closed


def test_a_stall_is_recorded_once_and_the_browsers_closed():
    d, clock, stalls, closed, interrupts = _dog()
    d.touch("reports: from the screens")
    clock.t += 901
    assert d.look() == "stalled"
    assert stalls == [("reports: from the screens", 901)] and closed == [1] and not interrupts
    clock.t += 60
    assert d.look() == ""                       # the next look waits another limit


def test_still_stuck_after_another_limit_ends_the_run():
    d, clock, stalls, closed, interrupts = _dog()
    d.touch("browser: every page")
    clock.t += 901
    d.look()
    clock.t += 901
    assert d.look() == "ended"
    assert interrupts == [1] and len(stalls) == 1
    assert "stalled at browser: every page" in d.ended
    clock.t += 5000
    assert d.look() == ""                       # ended once


def test_progress_after_a_stall_starts_again():
    d, clock, stalls, _, interrupts = _dog()
    clock.t += 901
    d.look()
    d.touch("the next suite")
    clock.t += 901
    assert d.look() == "stalled" and len(stalls) == 2 and not interrupts


def test_a_long_step_is_allowed_more():
    d, clock, stalls, _, _ = _dog()
    with d.allow(3600):
        clock.t += 3000
        assert d.look() == ""
    clock.t += 600
    assert d.look() == "" and not stalls        # the clock starts again when the long step ends


def test_a_broken_stall_record_never_breaks_the_watchdog():
    clock = Clock()

    def boom(step, idle):
        raise RuntimeError("database gone")
    d = watchdog.Watchdog(boom, limit=10, clock=clock, close=lambda: 0, interrupt=lambda: None)
    clock.t += 11
    assert d.look() == "stalled"


def _proc(tmp: Path, procs: dict[int, tuple[int, str]]) -> Path:
    for pid, (ppid, comm) in procs.items():
        (tmp / str(pid)).mkdir()
        (tmp / str(pid) / "stat").write_text(f"{pid} ({comm} x) S {ppid} 1 1 0")
        (tmp / str(pid) / "comm").write_text(comm + "\n")
    (tmp / "self").mkdir()
    return tmp


def test_only_the_browsers_under_this_process_are_found(tmp_path):
    proc = _proc(tmp_path, {
        10: (1, "python"), 11: (10, "node"), 12: (11, "headless_shell"), 13: (12, "chrome"),
        14: (11, "chromium"), 20: (1, "chrome"), 21: (10, "psql")})
    assert sorted(watchdog.browser_pids(10, proc)) == [12, 13, 14]


def test_closing_kills_each_and_counts():
    killed = []
    assert watchdog.close_browsers([5, 6], kill=lambda pid, sig: killed.append((pid, sig))) == 2
    assert killed == [(5, signal.SIGKILL), (6, signal.SIGKILL)]

    def gone(pid, sig):
        raise ProcessLookupError
    assert watchdog.close_browsers([7], kill=gone) == 0


def test_the_runner_watches_its_checks_and_log_lines():
    src = inspect.getsource(run)
    assert "watchdog.Watchdog(stall_recorder(r))" in src and "r.dog.start()" in src
    assert inspect.getsource(run.Run.log).count("self.dog.touch(") == 1
    assert "self.dog.touch()" in inspect.getsource(run.Run.recorder)
    assert "r.dog.allow(BACKUP_ALLOW)" in inspect.getsource(run._backup_suite) and run.BACKUP_ALLOW == 3600
    body = inspect.getsource(run.cmd_run)
    assert "except KeyboardInterrupt" in body and "error = r.dog.ended" in body and "dog_stop.set()" in body


def test_a_stall_is_a_failed_check_in_the_suite_at_hand(tmp_path):
    added = []

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Engine:
        def begin(self):
            return Conn()

    r = run.Run.__new__(run.Run)
    r.engine, r.id, r.dir, r.suite_now = Engine(), 18, tmp_path, "reports"
    orig = run.store.add_result
    run.store.add_result = lambda conn, *a: added.append(a)
    try:
        run.stall_recorder(r)("reports: from the screens", 960)
    finally:
        run.store.add_result = orig
    (run_id, suite, name, outcome, detail, ms) = added[0][:6]
    assert (run_id, suite, name, outcome, ms) == (18, "reports", "stalled at reports: from the screens", "failed", 960000)
    assert "16 minutes" in detail and "STALLED" in (tmp_path / "run.log").read_text()
