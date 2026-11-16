"""R5.45 (owner, 16 Nov 2026, 08:36: "When repo is built and all is up why is this job still there? Killing is not
really doing anything. Nor is cancelling"). Two faults:
1. Kill, Cancel and Move answered "type procrastinate_job_status does not exist": the job runner's own trigger names its
   types without their schema, and the change ran without the jobs schema on the search path.
2. The job runner was restarted at 06:12 (the API's log: "Stop requested"); the jobs it was running stayed "doing"
   for ever and each held its job's lock, so the next run of each waited for ever ("Stuck: waiting for 38 minutes")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import jobqueue as jq  # noqa: E402


class Res:
    def __init__(self, rows=None, scalar=None, rowcount=1):
        self._rows, self._scalar, self.rowcount = rows or [], scalar, rowcount

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows

    def one(self):
        return (0, 0)


class Conn:
    def __init__(self, status="doing", doing=()):
        self.sql, self.status, self.doing = [], status, list(doing)

    def execute(self, stmt, params=None):
        q = " ".join(str(stmt).split())
        self.sql.append(q)
        if q.startswith("SELECT status::text"):
            return Res(scalar=self.status)
        if "RETURNING id, task_name" in q:
            return Res(rows=self.doing)
        return Res()


def _path_before_change(conn):
    path = next(i for i, q in enumerate(conn.sql) if q.startswith("SET LOCAL search_path TO jobs"))
    change = next(i for i, q in enumerate(conn.sql) if q.startswith("UPDATE jobs.procrastinate_jobs"))
    return path < change


def test_kill_cancel_and_move_put_the_jobs_schema_on_the_path():
    c = Conn("doing")
    jq.kill(c, 668, "t")
    assert _path_before_change(c)
    c = Conn("todo")
    jq.cancel(c, 686, "t")
    assert _path_before_change(c)
    c = Conn("todo")
    jq.move(c, 686, "t", "down")
    assert _path_before_change(c)


def test_jobs_left_doing_by_the_last_runner_are_marked_stopped_with_one_server():
    c = Conn(doing=[(214, "eax.project_repositories"), (668, "eax.resource_sample")])
    out = jq.recover(c, servers=1)
    assert [r["id"] for r in out["recovered"]] == [214, 668]
    assert _path_before_change(c)
    assert any("UPDATE core.tasks SET status = 'failed'" in q for q in c.sql)


def test_with_several_servers_nothing_is_touched():
    c = Conn(doing=[(214, "eax.project_repositories")])
    assert jq.recover(c, servers=2)["recovered"] == []
    assert c.sql == []


def test_the_entrypoint_recovers_before_the_job_runner_starts():
    ep = (Path(__file__).resolve().parents[1] / "entrypoint.sh").read_text()
    assert ep.index("python -m eax.jobqueue recover") < ep.index("procrastinate --app=eax.jobs.app worker")
