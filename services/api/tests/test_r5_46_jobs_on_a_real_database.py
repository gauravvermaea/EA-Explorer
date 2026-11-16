"""R5.46: the job queue's code tried against the job runner's real tables and triggers (owner, 16 Nov 2026, 08:41:
"ensure if jobs are dead then they dont show up. Please review your code of jobs, add tests for jobs and ensure there
are no bugs"). R5.45's faults (Kill and Cancel failing on the runner's own trigger; jobs left "doing" by a stopped runner
holding up their next runs for ever) passed tests made with fakes; these run the same code on PostgreSQL with the job
runner's own schema (procrastinate's schema.sql, as installed in the jobs schema).

They need a PostgreSQL server the tests may create a database on: EAX_JOBS_TEST_DSN, for example
postgresql+psycopg://postgres@/postgres?host=/tmp/pgjobs&port=55432. Without it they are skipped."""
import importlib.resources
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DSN = os.environ.get("EAX_JOBS_TEST_DSN", "")
pytestmark = pytest.mark.skipif(not DSN, reason="needs EAX_JOBS_TEST_DSN (a PostgreSQL server to make a test database on)")


@pytest.fixture()
def engine(monkeypatch):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from eax import settings
    monkeypatch.setattr(settings, "values", lambda *a, **k: {})        # the limits' and slots' defaults
    monkeypatch.setenv("EAX_API_SERVERS", "1")
    admin = create_engine(DSN, isolation_level="AUTOCOMMIT")
    name = f"jobs_test_{uuid.uuid4().hex[:10]}"
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    eng = create_engine(make_url(DSN).set(database=name))
    schema = (importlib.resources.files("procrastinate") / "sql" / "schema.sql").read_text()
    with eng.begin() as c:
        c.execute(text("CREATE SCHEMA jobs; CREATE SCHEMA core"))
        c.execute(text("""CREATE TABLE core.tasks (id bigserial PRIMARY KEY, job_id bigint, kind text, label text,
                          requested_by text, status text, message text, finished_at timestamptz)"""))
        c.execute(text("SET LOCAL search_path TO jobs, public"))
        c.connection.driver_connection.execute(schema)      # no parameters: its '%' are the SQL's own
    yield eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


def _defer(c, task, lock=None, status="todo", queue="default", scheduled_at=None):
    from sqlalchemy import text
    c.execute(text("SET LOCAL search_path TO jobs, public"))
    jid = c.execute(text("""INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, lock, queueing_lock, args, scheduled_at)
                            VALUES (:q, :t, :l, NULL, '{"timestamp": 1}'::jsonb, :s) RETURNING id"""),
                    {"q": queue, "t": task, "l": lock, "s": scheduled_at}).scalar()
    if status == "doing":                        # as the job runner takes it: the 'started' event comes from its trigger
        c.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'doing' WHERE id = :j"), {"j": jid})
    return jid


def _events(c, jid):
    from sqlalchemy import text
    return [r[0] for r in c.execute(text("SELECT type::text FROM jobs.procrastinate_events WHERE job_id = :j ORDER BY id"),
                                    {"j": jid})]


def _status(c, jid):
    from sqlalchemy import text
    return c.execute(text("SELECT status::text FROM jobs.procrastinate_jobs WHERE id = :j"), {"j": jid}).scalar()


def _fetch(c, queue="default"):
    from sqlalchemy import text
    c.execute(text("SET LOCAL search_path TO jobs, public"))
    return c.execute(text("SELECT id FROM procrastinate_fetch_job(ARRAY[:q]::varchar[])"), {"q": queue}).scalar()


def test_kill_cancel_and_move_work_on_the_runners_own_tables(engine):
    from eax import jobqueue as jq
    with engine.begin() as c:
        waiting = _defer(c, "eax.alerts_run")
        running = _defer(c, "eax.resource_sample", status="doing")
    with engine.begin() as c:
        jq.move(c, waiting, "t", "down")
        jq.move(c, waiting, "t", "up")
        jq.cancel(c, waiting, "t")
        first = jq.kill(c, running, "t")
    with engine.begin() as c:
        assert _status(c, waiting) == "cancelled" and _events(c, waiting) == ["deferred", "cancelled"]
        assert first["status"] == "aborting" and _status(c, running) == "aborting"
    with engine.begin() as c:
        assert jq.kill(c, running, "t")["status"] == "aborted"
    with engine.begin() as c:
        assert _status(c, running) == "aborted"
        assert _events(c, running) == ["deferred", "started", "abort_requested", "aborted"]


def test_a_job_killed_while_running_can_still_be_finished_by_the_runner(engine):
    """Kill must not leave a job the runner refuses to finish (its finish_job raises for a job no longer running, and
    the worker stops): a job asked to stop is still finished normally when its work ends."""
    from sqlalchemy import text

    from eax import jobqueue as jq
    with engine.begin() as c:
        running = _defer(c, "eax.housekeeping", status="doing")
    with engine.begin() as c:
        jq.kill(c, running, "t")
    with engine.begin() as c:
        c.execute(text("SET LOCAL search_path TO jobs, public"))
        c.execute(text("SELECT procrastinate_finish_job(:j, 'succeeded', false)"), {"j": running})
        assert _status(c, running) == "succeeded"


def test_a_job_left_doing_by_a_stopped_runner_holds_its_next_run_until_recovered(engine):
    """The owner's screen of 08:36: Build the project repositories "being worked on" 38 minutes after the runner
    restarted, and its next run "waiting" behind it."""
    from eax import jobqueue as jq
    with engine.begin() as c:
        dead = _defer(c, "eax.project_repositories", lock="project_repositories", status="doing")
        nxt = _defer(c, "eax.project_repositories", lock="project_repositories")
    with engine.begin() as c:
        assert _fetch(c) is None                 # the next run cannot start: the dead one holds the lock
        row = next(j for j in jq.queue(c)["jobs"] if j["id"] == nxt)
        assert row["behind"] == dead and not row["stuck"] and "earlier run" in row["why"]
    with engine.begin() as c:
        out = jq.recover(c, servers=1)
    assert [r["id"] for r in out["recovered"]] == [dead]
    with engine.begin() as c:
        assert _status(c, dead) == "failed" and _events(c, dead)[-1] == "failed"
        assert _fetch(c) == nxt                  # and now it starts
        shown = {j["id"] for j in jq.queue(c)["jobs"] if j["status"] in ("doing", "aborting")}
        assert dead not in shown                 # a dead job no longer shows as being worked on


def test_with_several_servers_recover_leaves_running_jobs_alone(engine):
    from eax import jobqueue as jq
    with engine.begin() as c:
        live = _defer(c, "eax.housekeeping", lock="housekeeping", status="doing")
    with engine.begin() as c:
        assert jq.recover(c, servers=2)["recovered"] == []
        assert _status(c, live) == "doing"


def test_put_off_and_long_running_jobs_are_judged_right(engine):
    from sqlalchemy import text

    from eax import jobqueue as jq
    now = datetime.now(UTC)
    with engine.begin() as c:
        later = _defer(c, "eax.run_task", scheduled_at=now + timedelta(hours=2))
        hung = _defer(c, "eax.housekeeping", lock="housekeeping", status="doing")
        c.execute(text("UPDATE jobs.procrastinate_events SET at = now() - interval '3 hours' WHERE job_id = :j"), {"j": hung})
    with engine.begin() as c:
        q = jq.queue(c, now=now)
    rows = {j["id"]: j for j in q["jobs"]}
    assert rows[later]["later"] and not rows[later]["stuck"] and rows[later]["why"].startswith("starts at")
    assert rows[hung]["stuck"] and "running for" in rows[hung]["why"]
    assert q["summary"]["stuck_running"] == 1 and q["summary"]["stuck_waiting"] == 0


def test_delete_history_keeps_what_is_waiting_or_running(engine):
    from sqlalchemy import text

    from eax import jobqueue as jq
    with engine.begin() as c:
        done = _defer(c, "eax.housekeeping", status="doing")
        c.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'succeeded' WHERE id = :j"), {"j": done})
        c.execute(text("""INSERT INTO jobs.procrastinate_periodic_defers (task_name, defer_timestamp, job_id)
                          VALUES ('eax.housekeeping', 1, :j)"""), {"j": done})
        waiting = _defer(c, "eax.alerts_run")
        running = _defer(c, "eax.resource_sample", status="doing")
    with engine.begin() as c:
        assert jq.delete_history(c, None, "t")["deleted"] == 1
    with engine.begin() as c:
        assert _status(c, done) is None and _status(c, waiting) == "todo" and _status(c, running) == "doing"
        assert c.execute(text("SELECT job_id FROM jobs.procrastinate_periodic_defers")).scalar() is None


def test_the_self_tests_jobs_suite(engine):
    """System Admin > Self-test's Jobs item (R5.46): on a healthy queue every check passes, and its probes leave nothing."""
    from sqlalchemy import text

    from eax.testing import jobs_check
    with engine.begin() as c:
        for task in ("eax.alerts_run", "eax.resource_sample"):
            jid = _defer(c, task, status="doing")
            c.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'succeeded' WHERE id = :j"), {"j": jid})
        before = c.execute(text("SELECT count(*) FROM jobs.procrastinate_jobs")).scalar()
    got = []
    counts = jobs_check.run(engine, lambda name, outcome, detail="", ms=0: got.append((name, outcome, detail)))
    assert counts["failed"] == 0, got
    assert {n for n, _o, _d in got} >= {"jobs: the job runner takes jobs", "jobs: the alert checks run",
                                       "jobs: Cancel, Move and Kill work", "jobs: every scheduled job has its lock"}
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM jobs.procrastinate_jobs")).scalar() == before


def test_the_jobs_suite_says_when_the_runner_is_not_taking_jobs(engine):
    from eax.testing import jobs_check
    got = []
    jobs_check.run(engine, lambda name, outcome, detail="", ms=0: got.append((name, outcome)))
    assert ("jobs: the job runner takes jobs", "failed") in got
