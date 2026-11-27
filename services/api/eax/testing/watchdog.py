"""The stall watchdog of a self-test run (D942; owner, 26 Nov 2026: "will they get stuck again? I mean the tests got stuck
in the end", then "Your recomendation is accepted").

Run 18 stopped for good after "from the screens": a call in a browser page that never came back. The heartbeat (alive.py)
kept saying the run was being run, so nothing closed it. The watchdog watches progress, not life: every recorded check and
every log line of the run is progress. When nothing moves for LIMIT seconds (a step known to take longer says so with
`allow`), the run records "stalled at <step>" as a failed check and closes the browsers this process started; the blocked
call then fails, its suite records that and the run goes on to the next check or suite. When nothing moves for another
LIMIT after that, the run ends cleanly as an error with the reason (the main thread is interrupted; cmd_run closes it).

Only the runner's own process is watched: the security scans, the load test and the attack test run in the operations
helper afterwards, with their own limits."""

from __future__ import annotations

import _thread
import os
import signal
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

LIMIT = 900          # seconds without a recorded check or a log line: the run is stuck (15 minutes)
EVERY = 30           # seconds between looks
BROWSERS = ("chrome", "chromium", "headless_shell")


def _children(pid: int, proc: Path = Path("/proc")) -> dict[int, list[int]]:
    """Each process's children, read from /proc (Linux, where the runner runs)."""
    kids: dict[int, list[int]] = {}
    try:
        entries = list(proc.iterdir())
    except OSError:
        return kids
    for e in entries:
        if not e.name.isdigit():
            continue
        try:
            stat = (e / "stat").read_text()
        except OSError:
            continue
        # "pid (comm) state ppid ...": the name can hold spaces and brackets, so read after the last ")"
        rest = stat[stat.rfind(")") + 2:].split()
        if len(rest) > 1 and rest[1].isdigit():
            kids.setdefault(int(rest[1]), []).append(int(e.name))
    return kids


def browser_pids(root: int | None = None, proc: Path = Path("/proc")) -> list[int]:
    """The browser processes under this process (Playwright's driver starts them: they are its children)."""
    root = os.getpid() if root is None else root
    kids, found, todo = _children(root, proc), [], [root]
    seen: set[int] = set()
    while todo:
        pid = todo.pop()
        for c in kids.get(pid, []):
            if c in seen:
                continue
            seen.add(c)
            todo.append(c)
            try:
                name = (proc / str(c) / "comm").read_text().strip().lower()
            except OSError:
                continue
            if any(b in name for b in BROWSERS):
                found.append(c)
    return found


def close_browsers(pids: list[int] | None = None, kill: Callable[[int, int], None] = os.kill) -> int:
    """Ends the browsers this process started; how many were ended."""
    n = 0
    for pid in browser_pids() if pids is None else pids:
        try:
            kill(pid, signal.SIGKILL)
            n += 1
        except OSError:
            pass
    return n


class Watchdog:
    """Watches a run's progress. touch() on every check and log line; allow(seconds) around a step known to be long."""

    def __init__(self, on_stall: Callable[[str, int], None], limit: int = LIMIT, clock: Callable[[], float] = time.time,
                 close: Callable[[], int] = close_browsers, interrupt: Callable[[], None] = _thread.interrupt_main):
        self.on_stall, self.limit, self.clock, self.close, self.interrupt = on_stall, limit, clock, close, interrupt
        self.last = clock()
        self.step = "the start of the run"
        self.extra = 0                 # seconds more a step in hand may take (allow)
        self.stalls = 0                # stalls in a row without progress since
        self.ended = ""                # why the run was ended, once it was
        self._lock = threading.Lock()

    def touch(self, step: str | None = None) -> None:
        """Marks progress now (a check done, a log line), with the step the run is on when one is given."""
        with self._lock:
            self.last = self.clock()
            self.stalls = 0
            if step:
                self.step = step[:200]

    @contextmanager
    def allow(self, seconds: int) -> Iterator[None]:
        """A step known to take longer than the limit (the backups and their trial restores)."""
        with self._lock:
            self.extra += seconds
        try:
            yield
        finally:
            with self._lock:
                self.extra -= seconds
                self.last = self.clock()

    def look(self) -> str:
        """One look: "" (moving), "stalled" (recorded, browsers closed) or "ended" (the main thread interrupted)."""
        with self._lock:
            idle = int(self.clock() - self.last)
            if self.ended or idle <= self.limit + self.extra:
                return ""
            self.stalls += 1
            self.last = self.clock()           # the next look waits another limit
            step, stalls = self.step, self.stalls
        if stalls == 1:
            try:
                self.on_stall(step, idle)
            except Exception:  # noqa: BLE001 - the watchdog never breaks the run itself
                pass
            try:
                self.close()
            except Exception:  # noqa: BLE001
                pass
            return "stalled"
        self.ended = f"the run stalled at {step}: nothing moved for {(idle + self.limit) // 60} minutes, even with the browsers closed"
        self.interrupt()
        return "ended"

    def start(self, stop: threading.Event | None = None, every: int = EVERY) -> threading.Event:
        """Looks every few seconds in a thread of its own until the event returned is set (the run closing)."""
        stop = stop or threading.Event()

        def loop() -> None:
            while not stop.wait(every):
                if self.look() == "ended":
                    return
        threading.Thread(target=loop, daemon=True, name="selftest-watchdog").start()
        return stop
