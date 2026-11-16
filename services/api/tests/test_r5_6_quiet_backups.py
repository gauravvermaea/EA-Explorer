"""Every infrastructure backup with the maintenance page on and the background paused and finished first (the owner,
17 Nov 2026, 00:43: "When we backup we must ensure mantainance page comes up and all background jobs shut down. Thats the
only way this will work"; 00:45: every infrastructure backup, scheduled and on demand; application backups stay online).
Nothing is killed: when the background has not finished in time the backup goes ahead and says so."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_backups_infra import _ops  # noqa: E402


def _watch(ops, monkeypatch, idle_answer):
    """docker exec: the API's idle answer, and at backup.sh whether the page and the pause were on."""
    seen = {"order": []}
    real = ops.subprocess.run

    def run(args, **k):
        if "eax.testing.backup_restore" in args:
            seen["order"].append("idle")
            seen["wait"] = json.loads(k.get("input") or "{}").get("wait")

            class R:
                returncode, stderr = 0, ""
                stdout = "waiting...\n" + json.dumps(idle_answer) + "\n"
            return R()
        if args[3] == "backup.sh":
            seen["order"].append("backup.sh")
            seen["quiet_at_backup"] = ops.brtest.is_quiet()
            seen["page_at_backup"] = open(ops.PROXY_FLAG, encoding="utf-8").read() if ops.os.path.exists(ops.PROXY_FLAG) else ""
        return real(args, **k)
    monkeypatch.setattr(ops.subprocess, "run", run)
    return seen


def test_a_backup_puts_the_page_on_waits_for_the_background_then_puts_everything_back(tmp_path, monkeypatch):
    ops, work, backups, calls, _ = _ops(tmp_path, monkeypatch)
    seen = _watch(ops, monkeypatch, {"idle": True, "waited": 42})
    m = ops._do_backup("nightly", "system", "scheduled", "0.12.0")
    assert m["status"] == "ok" and seen["order"] == ["idle", "backup.sh"]           # drained first, then backed up
    assert seen["quiet_at_backup"] and "A backup is being taken" in seen["page_at_backup"]
    assert not ops.brtest.is_quiet() and not ops.os.path.exists(ops.PROXY_FLAG)   # both back after
    saved = json.loads((backups / "infrastructure" / m["name"] / "manifest.json").read_text())
    assert saved["quiet"] == {"paused": True, "waited": 42}


def test_a_busy_background_is_never_killed_the_backup_goes_ahead_and_says_so(tmp_path, monkeypatch):
    ops, work, backups, calls, _ = _ops(tmp_path, monkeypatch)
    _watch(ops, monkeypatch, {"idle": False, "waited": 1800, "error": "the background did not finish within 30 minutes: "
                                                                      "the job eax.big_import (running)"})
    m = ops._do_backup("nightly", "system", "scheduled", "0.12.0")
    saved = json.loads((backups / "infrastructure" / m["name"] / "manifest.json").read_text())
    assert m["status"] == "ok" and "eax.big_import" in saved["quiet"]["still_busy"]
    assert not any(c[:2] in (["docker", "kill"], ["kill"]) or "cancel" in " ".join(map(str, c)) for c in calls)
    assert not ops.brtest.is_quiet()


def test_already_quiet_it_is_left_as_it_is_and_a_failed_backup_still_puts_everything_back(tmp_path, monkeypatch):
    ops, work, backups, calls, state = _ops(tmp_path, monkeypatch)
    seen = _watch(ops, monkeypatch, {"idle": True, "waited": 0})
    ops.brtest.quiet("on", "eax test backup-restore")                    # the test (or the drill, or a DR pack) holds it
    m = ops._do_backup("brt-x", "test", "on-demand", "0.12.0")
    assert m["status"] == "ok" and seen["order"] == ["backup.sh"] and ops.brtest.is_quiet()   # its own wait; left on
    ops.brtest.quiet("off", "test")
    state["backup"] = "exited"                                           # the backup fails
    m = ops._do_backup("nightly", "system", "scheduled", "0.12.0")
    assert m["status"] == "failed" and not ops.brtest.is_quiet() and not ops.os.path.exists(ops.PROXY_FLAG)
