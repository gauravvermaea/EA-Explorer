"""`eax jobs` (eax/jobqueue.main) and the queue's own steps run in the unit tests with the database stood in for (owner,
25 Nov 2026, 17:02: "add tests to unit tests and mock the DB etc"): every command prints what it did and puts it in the
audit trail; clear-stuck kills only the stuck jobs being worked on; the history is deleted only for finished jobs, all of
them or those older than the days given; a restart is asked of the operations helper. The database answers are the
rows a real queue gives (SELECT ... -> rows), so what is printed is checked word for word. Background jobs' figure, D926."""

import io
import json
import sys
import types
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

import eax  # noqa: E402
from eax import jobqueue as jq  # noqa: E402


class Conn:
    """A database connection that keeps what it was asked and answers the job ids given."""
    def __init__(self, ids=()):
        self.asked, self.ids = [], list(ids)

    def execute(self, sql, params=None):
        self.asked.append((str(sql), params or {}))
        return [(i,) for i in self.ids] if "SELECT j.id FROM jobs.procrastinate_jobs" in str(sql) else []


@pytest.fixture(autouse=True)
def plain_sql(monkeypatch):
    """The SQL kept as its text, to read what was asked."""
    monkeypatch.setattr(jq, "text", lambda sql: sql)


@pytest.fixture()
def cli(monkeypatch):
    """eax.db and eax.audit stood in for; returns what was audited."""
    audited, conn = [], Conn([11, 12])

    @contextmanager
    def begin():
        yield conn

    db = types.ModuleType("eax.db")
    db.get_engine = lambda: types.SimpleNamespace(begin=begin)
    audit = types.ModuleType("eax.audit")
    audit.record = lambda conn, **k: audited.append(k["action"])
    monkeypatch.setitem(sys.modules, "eax.db", db)
    monkeypatch.setitem(sys.modules, "eax.audit", audit)
    monkeypatch.setattr(eax, "audit", audit, raising=False)
    monkeypatch.setattr(eax, "db", db, raising=False)
    return types.SimpleNamespace(audited=audited, conn=conn)


def run(argv) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = jq.main(argv)
    return code, out.getvalue()


QUEUE = {"summary": {"running": 1, "waiting": 1, "stuck": 1, "free_slots": 3, "slots": 4,
                     "advice": [{"text": "Kill the stuck job."}]},
         "jobs": [{"id": 5, "what": "Back up", "who": "eaadmin", "status": "doing", "minutes": 61.0, "stuck": True,
                   "why": "over an hour"},
                  {"id": 6, "what": "Measure quality", "who": "system", "status": "todo", "minutes": None, "why": "a slot"}],
         "finished": [{"id": 4, "what": "Tag", "who": "eaadmin", "status_words": "done", "ended_at": "2026-11-25T10:00"}]}


def test_list_and_history_print_the_queue(cli, monkeypatch):
    monkeypatch.setattr(jq, "queue", lambda conn, *a, **k: QUEUE)
    code, out = run(["list"])
    assert code == 0 and "Job queue: 1 being worked on, 1 waiting, 1 stuck, 3 of 4 slots free." in out
    assert "STUCK: over an hour" in out and "(a slot)" in out and "- Kill the stuck job." in out
    code, out = run(["history", "5"])
    assert code == 0 and "Tag" in out and "1 finished job(s)." in out


def test_cancel_kill_and_move_are_audited(cli, monkeypatch):
    monkeypatch.setattr(jq, "cancel", lambda conn, i, by: {"id": i})
    monkeypatch.setattr(jq, "kill", lambda conn, i, by: {"id": i, "message": "asked to stop."})
    monkeypatch.setattr(jq, "move", lambda conn, i, by, d: {"id": i, "moved": d})
    assert run(["cancel", "7"]) == (0, "Job 7: cancel done.\n")
    assert run(["kill", "7"]) == (0, "Job 7: asked to stop.\n")
    assert run(["up", "7"])[0] == 0 and run(["down", "7"])[0] == 0
    assert cli.audited == ["jobs.cancel", "jobs.kill", "jobs.up", "jobs.down"]


def test_clear_stuck_kills_only_the_stuck_ones_being_worked_on(cli, monkeypatch):
    monkeypatch.setattr(jq, "queue", lambda conn, *a, **k: QUEUE)
    killed = []
    monkeypatch.setattr(jq, "kill", lambda conn, i, by: killed.append(i) or {"id": i})
    out = jq.clear_stuck(cli.conn, "eax")
    assert killed == [5] and out == {"killed": [{"id": 5, "what": "Back up"}], "restart_needed": True}
    code, said = run(["clear-stuck"])
    assert code == 0 and "1 stuck job(s) killed: 5 Back up" in said and cli.audited == ["jobs.clear_stuck"]


def test_clear_stuck_with_restart_asks_the_operations_helper(cli, monkeypatch):
    monkeypatch.setattr(jq, "queue", lambda conn, *a, **k: {**QUEUE, "jobs": []})
    monkeypatch.setattr(jq, "_restart_runner", lambda: "Restarting the API.")
    code, said = run(["clear-stuck", "--restart"])
    assert code == 0 and "Restarting the API. The screens come back within a minute." in said
    code, said = run(["restart"])
    assert code == 0 and "jobs.restart_runner" in cli.audited


def test_the_restart_goes_to_the_operations_helper_with_its_token(monkeypatch):
    asked = {}

    @contextmanager
    def urlopen(req, timeout=0):
        asked.update(url=req.full_url, method=req.get_method(), token=req.headers.get("X-ops-token"),
                     body=json.loads(req.data))
        yield io.BytesIO(b'{"message": "Restarting."}')
    monkeypatch.setattr(jq.httpopen, "urlopen", urlopen)
    monkeypatch.setenv("EAX_OPS_URL", "http://ops:8090")
    monkeypatch.setenv("EAX_OPS_TOKEN", "t0k")
    assert jq._restart_runner() == "Restarting."
    assert asked == {"url": "http://ops:8090/restart/api", "method": "POST", "token": "t0k", "body": {"by": "eax"}}


def test_the_history_is_deleted_for_finished_jobs_only(cli):
    out = jq.delete_history(cli.conn, None, "eax")
    assert out == {"deleted": 2, "older_than_days": 0}
    select = next(s for s, _p in cli.conn.asked if "SELECT j.id" in s)
    assert "status::text = ANY(:f)" in select and "make_interval" not in select
    deletes = [s for s, _p in cli.conn.asked if s.startswith(("DELETE", "UPDATE"))]
    assert len(deletes) == 3 and "procrastinate_periodic_defers SET job_id = NULL" in deletes[0]   # no job twice
    c2 = Conn([])
    assert jq.delete_history(c2, 30, "eax") == {"deleted": 0, "older_than_days": 30}
    assert "make_interval(days => :d)" in next(s for s, _p in c2.asked if "SELECT j.id" in s)
    assert not any(s.startswith("DELETE") for s, _p in c2.asked)                 # nothing finished that long ago
    with pytest.raises(ValueError):
        jq.delete_history(Conn(), -1, "eax")


def test_delete_history_from_the_command_line(cli):
    code, said = run(["delete-history", "--older-than", "3650"])
    assert code == 0 and "2 finished job(s) deleted from the history." in said and cli.audited == ["jobs.delete_history"]


def test_a_wrong_command_shows_the_help_and_a_wrong_number_an_error(cli):
    code, said = run(["nonsense"])
    assert code == 2 and "clear-stuck [--restart]" in said
    code, said = run(["kill", "x"])
    assert code == 1 and said.startswith("ERROR:")
