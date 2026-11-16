"""Quiet while the backup and restore test runs (R5.6-B1; owner, 16 Nov 2026, 19:28: "before we run this test let us put
mantainance page and stop everything in background ... can you do that in the script?").

The operations helper writes work/quiet.json (mounted read-only here at /eax-work) when the test starts and removes it
when it ends. While it is there every recurring job of the job runner misses its turn (it is not caught up; its next
run after the test does the work) and the scheduled backups, eax commands and updates wait. Jobs a person or the test
asks for still run (a project's folders in Documents, for one). The proxy shows its maintenance page meanwhile, so
nobody else works on the installation. The API itself stays writable: the test makes its content through it.

A flag older than eight hours is stale (a test that was stopped hard) and ignored, so nothing stays paused for good."""

from __future__ import annotations

import json
import os
import time

STALE_SECONDS = 8 * 3600


def path() -> str:
    """Where the flag is kept (work/quiet.json)."""
    return os.path.join(os.environ.get("EAX_WORK_MOUNT", "/eax-work"), "quiet.json")


def state(now: float | None = None) -> dict | None:
    """The quiet in force ({since, by, what}), or None (no flag, or a stale one)."""
    try:
        with open(path(), encoding="utf-8") as f:
            s = json.load(f)
        if (now or time.time()) - os.path.getmtime(path()) > STALE_SECONDS:
            return None
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return None


def on() -> bool:
    """Whether recurring work waits now."""
    return state() is not None
