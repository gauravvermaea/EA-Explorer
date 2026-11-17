"""The restore drill made sturdier (owner, 17 Nov 2026, 18:54: "I am getting worried about DR testing, we need it to be
more robust"; 19:05: "Yes build both and have make things warning and fail and can we continue with it"; the split agreed
at 19:06). Each problem is a failure (the drill stops) or a warning (noted, the drill carries on, the report lists it):
a kind of test content not made, a smoke test only slow, a container still starting, the background busy are warnings;
too little disk is found in seconds by the pre-flight and fails; a failure leaves diagnostics beside the report."""
from __future__ import annotations

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
sys.path.insert(0, str(REPO))

from eaxcli import drill as D  # noqa: E402

GB = D.GB


def test_a_kind_of_content_not_made_is_a_warning_not_a_failure(monkeypatch, tmp_path):
    answers = {"start": {"sid": "abc", "made": [{"what": "a tag", "ok": True},
                                                {"what": "a document with its file", "ok": False, "detail": "not built yet"}]},
               "snapshot": {"documents": {"rows": []}}}
    monkeypatch.setattr(D, "_api", lambda cmd, state: answers[cmd])
    out = D.content(str(tmp_path / "state.json"))
    assert "error" not in out and out["made"] == 1
    assert out["warnings"] == ["not made (not checked after the restore): a document with its file: not built yet"]


def test_the_test_itself_not_starting_still_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(D, "_api", lambda cmd, state: {"error": "the test's accounts could not be made"})
    assert D.content(str(tmp_path / "s.json"))["error"]


def test_too_little_disk_is_found_before_anything_is_touched(tmp_path):
    same = lambda p: 1                                                    # noqa: E731 - all on one disk
    # a 10 GB backup needs 15 + 12 + 5 = 32 GB on one disk
    assert D.disk_needs(10 * GB, str(tmp_path), str(tmp_path / "temp"), str(tmp_path / "dr"), free=lambda p: 31 * GB, device=same)
    assert not D.disk_needs(10 * GB, str(tmp_path), str(tmp_path / "temp"), str(tmp_path / "dr"), free=lambda p: 33 * GB, device=same)
    # on separate disks each needs only its own share
    disks = {"b": 15 * GB, "t": 12 * GB, "d": 5 * GB}
    names = {str(tmp_path / "b"): "b", str(tmp_path / "t"): "t", str(tmp_path / "d"): "d"}
    for n in names:
        Path(n).mkdir()
    assert not D.disk_needs(10 * GB, str(tmp_path / "b"), str(tmp_path / "t"), str(tmp_path / "d"),
                            free=lambda p: disks[names[str(p)]], device=lambda p: names[str(p)])


def test_the_preflight_fails_on_disk_and_warns_on_the_rest(monkeypatch, tmp_path):
    monkeypatch.setattr(D, "info", lambda: {"backups": str(tmp_path)})
    monkeypatch.setattr(D, "container_states", lambda: [{"name": "mayan", "state": "running", "status": "Up (health: starting)",
                                                         "health": "starting"}])
    monkeypatch.setattr(D, "_api", lambda cmd, state: {"busy": ["the documents of project X (building)"]})
    monkeypatch.setattr(D, "disk_needs", lambda *a, **k: [])
    out = D.preflight(str(tmp_path / "t"), str(tmp_path / "d"))
    assert "error" not in out and any("mayan" in w for w in out["warnings"]) and any("busy" in w for w in out["warnings"])
    monkeypatch.setattr(D, "disk_needs", lambda *a, **k: ["C:\\: 2.0 GB free, 8.0 GB needed"])
    assert "too little disk" in D.preflight(str(tmp_path / "t"), str(tmp_path / "d"))["error"]


def test_a_smoke_test_only_slow_is_a_warning_and_a_fault_is_a_failure(monkeypatch):
    slow = [{"suite": "reports", "name": "VP-25 as super-admin", "detail": "not loaded after 60 seconds"}]
    monkeypatch.setattr(D, "_api", lambda cmd, state: {"run": 9, "state": "failed", "failed": slow})
    out = D.smoke_result()
    assert "error" not in out and len(out["warnings"]) == 1
    fault = slow + [{"suite": "api", "name": "a model opens", "detail": "500 Internal Server Error"}]
    monkeypatch.setattr(D, "_api", lambda cmd, state: {"run": 9, "state": "failed", "failed": fault})
    assert "found faults" in D.smoke_result()["error"]
    monkeypatch.setattr(D, "_api", lambda cmd, state: {"run": 9, "state": "failed", "failed": []})
    assert D.smoke_result()["error"]


def test_both_drills_do_the_same(monkeypatch):
    """eax-drill.ps1 and eax-drill.sh kept in step (D331): the pre-flight, the smoke test's warnings, the diagnostics, the
    warnings in the report; and dr-common notes eax drill's warnings in both."""
    ps, sh = (REPO / "dr/eax-drill.ps1").read_text(encoding="utf-8"), (REPO / "dr/eax-drill.sh").read_text(encoding="utf-8")
    for text in (ps, sh):
        assert '"preflight"' in text or "drill preflight" in text
        assert '"smoke-result"' in text or "drill smoke-result" in text
        assert '"diagnose"' in text or "drill diagnose" in text
        assert "## Warnings (the drill carried on)" in text and "## Diagnostics" in text
        assert "warning(s)" in text
    assert ps.count("{ Smoke }") == 2 and sh.count('" smoke\n') == 2
    pc, sc = (REPO / "dr/dr-common.ps1").read_text(encoding="utf-8"), (REPO / "dr/dr-common.sh").read_text(encoding="utf-8")
    assert "$json.warnings" in pc and "json_list warnings" in sc


def test_the_preflight_does_not_count_the_repositories_recurring_job(monkeypatch):
    from eax.testing import backup_restore as T
    monkeypatch.setattr(T, "busy", lambda: ["the job eax.project_repositories (waiting)", "the job eax.import (running)"])
    assert T.busy_now({}) == {"busy": ["the job eax.import (running)"]}


def test_a_container_that_ran_once_and_ended_well_is_not_a_warning():
    """The owner's drill, 19:45: setup and reports-init, "Exited (0)", were warned about."""
    assert not D.not_well({"name": "setup", "state": "exited", "status": "Exited (0) 4 minutes ago", "health": ""})
    assert D.not_well({"name": "api", "state": "exited", "status": "Exited (1) 2 minutes ago", "health": ""})
    assert D.not_well({"name": "mayan", "state": "running", "status": "Up (unhealthy)", "health": "unhealthy"})
    assert not D.not_well({"name": "api", "state": "running", "status": "Up (healthy)", "health": "healthy"})
