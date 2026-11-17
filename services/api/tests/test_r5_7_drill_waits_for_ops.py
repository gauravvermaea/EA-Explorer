"""The restore drill waits for what eax up starts in the background (the owner's drill, 17 Nov 2026, 21:07 to 21:16:
"EA Explorer DR FAILED ... .\\eax drill quiet on failed: no answer: nothing printed", "service "ops" is not running";
then "The DR folder ... could not be deleted: The process cannot access the file 'eax-...-start-later.log' because it is
being used by another process").

eax-dr starts only the core of the DR copy (13:22 the same day), and eax up builds and starts the rest, the operations
helper among it, in the background (D255). The next step needed the operations helper at once: a command run in a
container now waits for it to be running (up to 20 minutes). And at the end the drill removed the DR copy while that
background start was still going (its log open, and about to create containers again): it now waits for it first."""

from __future__ import annotations

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
sys.path.insert(0, str(REPO))

from eaxcli import backup_restore as BR  # noqa: E402


def test_a_command_waits_for_its_container_to_run():
    states = iter([False, False, True])
    slept = []
    clock = iter(range(0, 10_000, 5))
    assert BR.wait_for_service("ops", limit=600, running=lambda s: next(states), sleep=slept.append,
                               clock=lambda: next(clock))
    assert len(slept) == 2


def test_it_gives_up_with_what_to_do():
    clock = iter(range(0, 10_000, 100))
    assert not BR.wait_for_service("ops", limit=300, running=lambda s: False, sleep=lambda s: None, clock=lambda: next(clock))
    out = BR.run_in(BR.OPS, ["quiet", "on"], wait=lambda s: False)
    assert "ops did not start" in out["error"] and "eax logs ops" in out["error"]


def test_the_drill_waits_for_the_background_start_before_removing_the_dr_copy():
    ps = (REPO / "dr/eax-drill.ps1").read_text(encoding="utf-8")
    sh = (REPO / "dr/eax-drill.sh").read_text(encoding="utf-8")
    assert ps.index("Wait-LaterStart $Dr 20") < ps.rindex('Eax @("drill", "remove-copy", $DrProject)')
    assert sh.index('wait_later_start "$DR" 20') < sh.index('eax drill remove-copy "$DR_PROJECT"')
    for common in ("dr/dr-common.ps1", "dr/dr-common.sh"):
        assert "Everything is started." in (REPO / common).read_text(encoding="utf-8")
    for launcher in ("eax.ps1", "eax.sh"):                  # what the wait looks for is what the launchers write
        assert "Everything is started." in (REPO / launcher).read_text(encoding="utf-8")


def test_wait_later_start_in_bash(tmp_path):
    import subprocess
    logs = tmp_path / "work" / "logs"
    logs.mkdir(parents=True)
    (logs / "eax-1-start-later.log").write_text("Starting after the core\nEverything is started.\n")
    script = f'LOG=/dev/null; source "{REPO}/dr/dr-common.sh"; wait_later_start "{tmp_path}" 1 && echo done'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert "done" in r.stdout, r.stderr


def test_the_drill_says_the_command_that_deletes_its_pinned_backup():
    """The owner, 17 Nov 2026, 21:25: the report said `.\\eax delete-backup <name>`, which refuses a pinned backup ("is
    pinned: unpin it first"); the drill's backup is pinned, so the command is `eax drill delete-backup` (unpins, deletes)."""
    for f in ("dr/eax-drill.ps1", "dr/eax-drill.sh"):
        text = (REPO / f).read_text(encoding="utf-8")
        assert "eax delete-backup $" not in text and "eax drill delete-backup $" in text
