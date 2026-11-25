"""The background task functions a test run never reaches (eax/tasks.py), run in the unit tests with the operations helper
and the database stood in for (owner, 25 Nov 2026, 17:02: "add tests to unit tests and mock the DB etc"): an
infrastructure backup followed until it is made, stopped or failed; a backup's trial restore with its checks; the self-test
fixtures purged run by run; a person's own finished tasks deleted, all or those chosen. Background jobs' figure, D926."""

import sys
import types
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax import tasks as tk  # noqa: E402
from eax.metamodel_edit import EditError  # noqa: E402

USER = types.SimpleNamespace(username="EAadmin", roles=("super-admin",))


def _ops(monkeypatch, answers):
    """eax.api.admin._ops_raw stood in for: each GET /backups answers the next state; what was asked is kept."""
    asked, states = [], iter(answers)
    admin = types.ModuleType("eax.api.admin")

    def ops_raw(method, path, body=None, timeout=0):
        asked.append((method, path, body))
        if path == "/backups":
            return {"state": next(states)}
        if path.endswith("/verify"):
            return answers[0]
        return {}
    admin._ops_raw = ops_raw
    monkeypatch.setitem(sys.modules, "eax.api.admin", admin)
    import time
    monkeypatch.setattr(time, "sleep", lambda *_a: None)
    return asked


def _task(params):
    return {"id": "t1", "params": params}


def test_an_infrastructure_backup_is_followed_until_it_is_made(monkeypatch):
    asked = _ops(monkeypatch, [{"busy": True}, {"busy": False, "result": {"status": "ok", "tag": "nightly", "name": "b1",
                                                                           "parts": {"databases": ["a", "b", "c"]}}}])
    said, out = tk._backup_infrastructure(None, _task({"tag": "nightly", "pinned": 1, "keep": "3"}), USER)
    assert said == "Infrastructure backup 'nightly' made: b1 (3 databases)." and out == {"name": "b1"}
    assert asked[0] == ("POST", "/backups/backup", {"tag": "nightly", "by": "EAadmin", "kind": "on-demand", "version": "",
                                                   "pinned": True, "keep": 3})
    assert [a[1] for a in asked[1:]] == ["/backups", "/backups"]


def test_a_stopped_or_failed_backup_says_so(monkeypatch):
    _ops(monkeypatch, [{"busy": False, "result": {"status": "stopped", "error": "stopped by EAadmin", "name": "b2"}}])
    said, out = tk._backup_infrastructure(None, _task({}), USER)
    assert said == "Infrastructure backup stopped: stopped by EAadmin" and out == {"name": "b2", "stopped": True}
    _ops(monkeypatch, [{"busy": False, "result": {"status": "failed", "error": "disk full"}}])
    with pytest.raises(EditError, match="The backup failed: disk full"):
        tk._backup_infrastructure(None, _task({}), USER)


def test_a_trial_restore_names_the_checks_that_failed(monkeypatch):
    _ops(monkeypatch, [{"checks": [{"name": "db", "ok": True, "detail": ""}, {"name": "files", "ok": False, "detail": "2 missing"}]}])
    said, out = tk._backup_verify(None, _task({"name": "b1"}), USER)
    assert said == "Trial restore of b1: 1 check(s) failed: files: 2 missing" and len(out["checks"]) == 2
    _ops(monkeypatch, [{"checks": [{"name": "db", "ok": True}]}])
    assert tk._backup_verify(None, _task({"name": "b1"}), USER)[0] == "Trial restore of b1: every check passed (1)."


def test_the_self_test_fixtures_are_purged_run_by_run(monkeypatch):
    fx = types.ModuleType("eax.testing.fixtures")
    runs = []

    def purge(conn, run, by, fixture_ids=None, progress=None):
        runs.append((run, by, fixture_ids))
        progress(50, "half")
        return {"models": 2, "projects": 1, "service_accounts": 3, "credentials": 4, "history_versions": 10, "notes": ["n"]}
    fx.purge = purge
    monkeypatch.setitem(sys.modules, "eax.testing.fixtures", fx)
    import eax.testing
    monkeypatch.setattr(eax.testing, "fixtures", fx, raising=False)
    said_progress = []
    monkeypatch.setattr(tk, "progress", lambda pct, note: said_progress.append(pct))
    said, total = tk._selftest_purge(None, _task({"runs": ["7", 8], "fixtures": []}), USER)
    assert runs == [(7, "EAadmin", None), (8, "EAadmin", None)] and said_progress == [25, 75]
    assert total["models"] == 4 and total["notes"] == ["n", "n"]
    assert said.startswith("Purged 4 model(s), 2 project(s), 6 account(s) and 8 credential(s) of 2 self-test run(s)")
    tk._selftest_purge(None, _task('{"runs": [9], "fixtures": [3]}'), USER)          # the parameters kept as text
    assert runs[-1] == (9, "EAadmin", [3])


class Conn:
    def __init__(self, n):
        self.n, self.asked = n, []

    def execute(self, sql, params):
        self.asked.append((sql, params))
        return types.SimpleNamespace(rowcount=self.n)


def test_a_person_deletes_their_own_finished_tasks(monkeypatch):
    monkeypatch.setattr(tk, "text", lambda sql: sql)
    c = Conn(3)
    assert tk.delete_history(c, USER) == {"deleted": 3, "message": "3 finished tasks deleted from your history."}
    sql, params = c.asked[0]
    assert "requested_by = :u AND status IN ('done', 'failed')" in sql and params == {"u": "eaadmin"}
    c = Conn(1)
    assert tk.delete_history(c, USER, ["g1", ""])["message"] == "1 finished task deleted from your history."
    assert c.asked[0][1]["g"] == ["g1"] and "ANY (CAST(:g AS text[]))" in c.asked[0][0]
    with pytest.raises(EditError, match="Choose the tasks to delete."):
        tk.delete_history(Conn(0), USER, ["", None])
