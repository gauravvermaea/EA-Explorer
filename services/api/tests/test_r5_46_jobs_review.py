"""R5.46: the review of the job queue's code (owner, 16 Nov 2026, 08:41: "ensure if jobs are dead then they dont show
up. Please review your code of jobs, add tests for jobs and ensure there are no bugs"; 08:42: "in self test dasboard have
another item for job tests"). What the review found, each with its test here or in test_r5_46_jobs_on_a_real_database.py:

1. A waiting job behind an earlier run of itself (its lock) was called stuck; it now says which job it waits for.
2. A job put off to a later time (run at a time, a retry) counted as waiting from when it was asked for: stuck before
   its time had come. It now says when it starts and is not judged until then.
3. A job asked to stop ("aborting") was never judged and counted from the wrong time.
4. Kill marked a job that was still running as ended; when its work did end the job runner could not finish it and
   stopped. Kill now asks it to stop; a second Kill marks it stopped at once (a job no runner has any more).
5. Delete history failed on the job runner's own trigger (its tables named without their schema), as Kill did (R5.45).
6. Cancel and Kill wrote their event twice (the runner's trigger writes it too).
7. Only one of the three job runners was watched: the scheduled or the alerts runner could stop and nothing restarted it.
8. The self-test has a Jobs item (the full test, Self-test's Jobs, eax test jobs)."""
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import jobqueue as jq  # noqa: E402

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
NOW = datetime(2026, 11, 16, 6, 36, tzinfo=UTC)


def _row(**k):
    base = {"id": 1, "task_name": "eax.project_repositories", "status": "todo", "deferred_at": NOW - timedelta(minutes=38)}
    base.update(k)
    return base


def test_behind_an_earlier_run_is_not_stuck_and_says_why():
    j = jq.judge(_row(id=442, behind=214), NOW, 5, 60)
    assert not j["stuck"] and j["why"] == "waiting for the earlier run of this job (job 214) to finish"


def test_put_off_to_later_is_not_waiting_yet():
    j = jq.judge(_row(scheduled_at=NOW + timedelta(hours=1)), NOW, 5, 60)
    assert j["later"] and not j["stuck"] and j["minutes"] is None and j["why"].startswith("starts at 2026-11-16 07:36")
    j = jq.judge(_row(deferred_at=NOW - timedelta(hours=2), scheduled_at=NOW - timedelta(minutes=2)), NOW, 5, 60)
    assert not j["stuck"] and j["minutes"] == 2.0           # waiting counts from its time, not from when it was asked


def test_a_job_being_stopped_is_judged_from_when_it_started():
    j = jq.judge(_row(status="aborting", started_at=NOW - timedelta(minutes=90), deferred_at=NOW - timedelta(minutes=91)),
                 NOW, 5, 60)
    assert j["stuck"] and j["minutes"] == 90.0 and "running for 90 minutes" in j["why"]


def test_a_long_running_job_is_stuck_and_a_short_one_is_not():
    assert jq.judge(_row(status="doing", started_at=NOW - timedelta(minutes=61)), NOW, 5, 60)["stuck"]
    assert not jq.judge(_row(status="doing", started_at=NOW - timedelta(minutes=30)), NOW, 5, 60)["stuck"]
    backup = _row(status="doing", task_name="eax.run_task", kind="backup", started_at=NOW - timedelta(minutes=100))
    assert not jq.judge(backup, NOW, 5, 60)["stuck"]          # long by nature: three times the limit


class Conn:
    def __init__(self, status):
        self.status, self.sql = status, []

    def execute(self, stmt, params=None):
        q = " ".join(str(stmt).split())
        self.sql.append(q)

        class R:
            def scalar(s):
                return self.status
            rowcount = 1
        return R()


def test_kill_asks_first_then_marks_stopped():
    c = Conn("doing")
    out = jq.kill(c, 9, "t")
    assert out["status"] == "aborting" and out["restart_needed"]
    assert any("SET status = 'aborting'" in q for q in c.sql) and not any("'aborted'" in q for q in c.sql)
    c = Conn("aborting")
    out = jq.kill(c, 9, "t")
    assert out["status"] == "aborted" and any("SET status = 'aborted'" in q for q in c.sql)


def test_no_event_written_twice():
    src = (API / "eax" / "jobqueue.py").read_text()
    assert "INSERT INTO jobs.procrastinate_events" not in src


def test_delete_history_puts_the_runner_schema_on_the_path():
    src = (API / "eax" / "jobqueue.py").read_text()
    body = src[src.index("def delete_history"):src.index("def _restart_runner")]
    assert body.index("_jobs_path(conn)") < body.index("DELETE FROM jobs.procrastinate_jobs")


def test_every_job_runner_is_watched():
    ep = (API / "entrypoint.sh").read_text()
    assert "SCHED_PID=$!" in ep and "WATCH_PID=$!" in ep
    loop = ep[ep.index("while kill -0"):ep.index("done", ep.index("while kill -0"))]
    for pid in ("$API_PID", "$JOBS_PID", "$SCHED_PID", "$WATCH_PID"):
        assert f"kill -0 {pid}" in loop, pid


def test_the_self_test_has_a_jobs_item():
    from eax import testing
    assert "jobs" in testing.SUITES and "jobs" in testing.FULL_SUITES and "jobs" in testing.WEB_FULL_SUITES
    ops = (REPO / "services" / "ops" / "testruns.py").read_text()
    assert 'SUITES = ("api", "ui", "db", "jobs",' in ops
    run = (API / "eax" / "testing" / "run.py").read_text()
    assert run.count("jobs_check.run(") == 2 and '"jobs": "Jobs"' in run
    store = (API / "eax" / "testing" / "store.py").read_text()
    assert '"jobs": (0, 1)' in store and '"jobs": "Jobs"' in store
    web = (REPO / "services" / "web" / "src" / "TestRuns.jsx").read_text(encoding="utf-8")
    assert '["jobs", "Jobs",' in web
    assert '"jobs"' in (REPO / "eaxcli" / "commands.py").read_text()
    assert "### test [smoke|full|jobs|" in (REPO / "eaxcli" / "help.txt").read_text()


def test_the_jobs_page_says_why_a_job_waits_and_offers_mark_stopped():
    web = (REPO / "services" / "web" / "src" / "Jobs.jsx").read_text(encoding="utf-8")
    assert "{!j.stuck && j.why &&" in web and '"Mark stopped"' in web
    c = json.loads((REPO / "services" / "web" / "src" / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "Being stopped" in c["button:Kill"] and c.get("button:Mark stopped")


def test_the_static_job_checks_pass_on_the_code():
    from eax.testing import jobs_check
    assert jobs_check.scheduled_without_lock() == []
    assert jobs_check.unnamed_tasks() == []
