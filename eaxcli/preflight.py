"""Before a full test (R14.27, R14.33; owner, 23 Nov 2026, 20:46: "we have struggled whole day to test"; 16:30: "The paging
file is too small"): what would slow it down or stop it, said at its start, so a run left overnight is not found crawling
in the morning. It warns and goes on (a refused run is a lost night); the warnings are the first lines of its log.

  * Docker's memory against what EA Explorer and the test need while they run;
  * Documents' OCR jobs waiting (on 23 Nov 2026 they kept Documents at 400% CPU and starved the run).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .core import capture, say, warn

GB = 1024 ** 3
# what runs at once during a full test, in GB (eax/sizing.py's figures rounded up, the start-up peaks of 23 Nov 2026):
# Documents 3, the API 2, Reports 2, Keycloak 1, the database and the rest 2, the test runner and its browser 2
NEEDS = {"Documents": 3, "the API": 2, "Reports": 2, "Keycloak": 1, "the database and the rest": 2, "the test runner": 2}
NEED_GB = sum(NEEDS.values())


def docker_memory(run: Callable = capture) -> int:
    """Docker's memory in bytes (0 when Docker does not say)."""
    code, out = run(["docker", "info", "--format", "{{.MemTotal}}"])
    try:
        return int(out.strip()) if code == 0 else 0
    except ValueError:
        return 0


def memory_warning(total: int) -> str:
    """What to say about Docker's memory, or "" when there is enough."""
    if not total or total >= NEED_GB * GB:
        return ""
    have = total / GB
    parts = ", ".join(f"{k} {v}" for k, v in NEEDS.items())
    return (f"Docker has {have:.1f} GB of memory; a full test needs about {NEED_GB} GB ({parts}). With less, containers "
            "are stopped for want of memory and the run crawls or stops. Give Docker more (Docker Desktop: Settings > "
            "Resources, or memory= in %UserProfile%\\.wslconfig, then restart Docker), or close other programs.")


def ocr_waiting(run: Callable = capture, compose_args: Callable | None = None) -> int | None:
    """Documents' OCR jobs waiting (None when it cannot be read: Documents off or not running)."""
    from . import packs
    from .core import compose_args as ca
    args = (compose_args or ca)(["exec", "-T", "-e", "EAX_CLEAR=0", "dms-broker", "sh", "-c", packs.OCR_SCRIPT])
    code, out = run(args)
    if code != 0 or "done" not in out.split():
        return None
    return sum(int(x) for x in re.findall(r"^queue (\d+)$", out, re.MULTILINE))     # one line a queue, as packs.ocr


def check(run: Callable = capture, compose_args: Callable | None = None) -> list[str]:
    """The warnings before a full test, each said as it is found; [] when nothing is in the way."""
    found = []
    m = memory_warning(docker_memory(run))
    if m:
        found.append(m)
    n = ocr_waiting(run, compose_args)
    if n:
        found.append(f"Documents has {n} OCR job(s) waiting: while it reads them it takes most of the processor and the "
                     "test crawls. .\\eax packs ocr --clear deletes them (the documents and their text stay), or switch "
                     "OCR off on System Admin > Settings > Documents.")
    say("Before the full test: " + ("nothing in the way." if not found else f"{len(found)} thing(s) that will slow it down:"))
    for w in found:
        warn(w)
    return found
