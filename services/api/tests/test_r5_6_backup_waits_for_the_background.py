"""R5.6-B1, the owner's run (16 Nov 2026, 23:09): B2 was taken while the test's new project's repository was still being
built in Documents (45 of its documents); restored, the build carried on (128), so "everything the test made is back,
row for row" failed. Before every backup the test (and eax-drill and eax dr-pack) now waits until the background has
finished: no project repository building or waiting, no template library loading, no job running or due that is not a
recurring one skipping its turn while quiet.

busy() on a real job queue (EAX_JOBS_TEST_DSN, procrastinate's own schema) and a real projects table; idle() alone."""
from __future__ import annotations

import importlib.resources
import os
import sys
import uuid
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
sys.path.insert(0, str(API))
sys.path.insert(0, str(REPO))

from eax.testing import backup_restore as T  # noqa: E402

DSN = os.environ.get("EAX_JOBS_TEST_DSN", "")


@pytest.fixture()
def engine(monkeypatch):
    if not DSN:
        pytest.skip("needs EAX_JOBS_TEST_DSN (a PostgreSQL server to make a test database on)")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    admin = create_engine(DSN, isolation_level="AUTOCOMMIT")
    name = f"jobs_idle_{uuid.uuid4().hex[:10]}"
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    eng = create_engine(make_url(DSN).set(database=name))
    schema = (importlib.resources.files("procrastinate") / "sql" / "schema.sql").read_text()
    with eng.begin() as c:
        c.execute(text("CREATE SCHEMA jobs; CREATE SCHEMA proj"))
        c.execute(text("""CREATE TABLE proj.projects (id bigserial PRIMARY KEY, name text NOT NULL, repo_state text NOT NULL
                          DEFAULT 'done', repo_tries int NOT NULL DEFAULT 0)"""))
        c.execute(text("CREATE TABLE proj.template_library_uploads (library_id bigint PRIMARY KEY)"))
        c.execute(text("SET LOCAL search_path TO jobs, public"))
        c.connection.driver_connection.execute(schema)
    from eax import db
    monkeypatch.setattr(db, "get_engine", lambda: eng)
    monkeypatch.setattr(db, "get_projects_engine", lambda: eng)
    yield eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


def _job(c, task, periodic, status="todo", minutes=-1):
    from sqlalchemy import text
    c.execute(text("SET LOCAL search_path TO jobs, public"))
    return c.execute(text("""INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args, scheduled_at, status)
                             VALUES ('default', :t, CAST(:a AS jsonb), now() + make_interval(mins => :m), CAST(:s AS procrastinate_job_status))
                             RETURNING id"""),
                     {"t": task, "a": '{"timestamp": 1}' if periodic else "{}", "m": minutes, "s": status}).scalar()


def test_busy_names_what_would_change_the_data_under_a_backup(engine):
    from sqlalchemy import text
    assert T.busy() == []
    with engine.begin() as c:
        c.execute(text("INSERT INTO proj.projects (name, repo_state) VALUES ('self_test_x_3', 'building'), ('old', 'done'),"
                       " ('given up', 'pending')"))
        c.execute(text("UPDATE proj.projects SET repo_tries = 30 WHERE name = 'given up'"))     # no more tries: not waited for
        _job(c, "eax.db_check", periodic=True, status="doing")          # a recurring job skipping its turn while quiet
        _job(c, "eax.project_repositories", periodic=True, status="doing")   # the one that keeps running (QUIET_RUNS)
        _job(c, "eax.build_index", periodic=False)                          # asked for, due
        _job(c, "eax.later", periodic=False, minutes=120)                   # not for two hours: not waited for
    got = T.busy()
    assert got[0] == "the documents of project self_test_x_3 (building)"
    assert "the job eax.project_repositories (running)" in got and "the job eax.build_index (waiting)" in got
    assert not any("db_check" in g or "later" in g or "given up" in g for g in got)
    with engine.begin() as c:
        c.execute(text("UPDATE proj.projects SET repo_state = 'done'"))
        c.execute(text("SET LOCAL search_path TO jobs, public"))
        c.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'succeeded' WHERE task_name <> 'eax.later'"))
        c.execute(text("INSERT INTO proj.template_library_uploads VALUES (7)"))
    assert T.busy() == ["1 template library loading"]


def test_idle_waits_until_calm_twice_and_says_what_is_still_going(monkeypatch):
    seen = iter([["the documents of project p (building)"], [], ["a job"], [], []])
    monkeypatch.setattr(T, "busy", lambda: next(seen))
    monkeypatch.setattr(T, "IDLE_EVERY", 0)
    assert T.idle({})["idle"] is True                                   # calm twice in a row, not once
    monkeypatch.setattr(T, "busy", lambda: ["the documents of project p (building)"])
    out = T.idle({"wait": 0})
    assert out["idle"] is False and "did not finish" in out["error"] and "project p" in out["error"]


def test_every_backup_the_test_drill_and_pack_take_waits_for_the_background_first():
    src = (REPO / "eaxcli/backup_restore.py").read_text()
    for before in ('f0 = t.step("fingerprint before B1', 'snap2 = t.step("what the test made, read back"'):
        i = src.index(before)
        assert 't.api("idle", {})' in src[i - 400:i], before
    assert src.index('t.api("idle"') > src.index('t.ops("quiet", "on")')       # the background paused first, then drained
    sh = (REPO / "dr/eax-drill.sh").read_text()
    assert sh.index("eax drill idle") < sh.index('eax drill fingerprint "$RUN/before.json"') and sh.index("quiet_on") < sh.index("eax drill idle")
    ps = (REPO / "dr/eax-drill.ps1").read_text()
    assert ps.index('@("drill", "idle")') < ps.index('"fingerprint", (Join-Path $Run "before.json")')
    pk = (REPO / "eaxcli/drpack.py").read_text()
    assert pk.index('_api("idle", {})') < pk.index('_ops("fingerprint")')
    assert "idle" in T.COMMANDS
