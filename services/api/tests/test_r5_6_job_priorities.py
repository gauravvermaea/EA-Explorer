"""R5.6-Q2: job priorities, and low-priority recurring jobs skipped when the queue is too full (owner, 15 Nov 2026,
22:47: "If the queue is too full then low priorty reoccuring jobs may not be done like DQ check (automated),
notifications etc"; agreed 16 Nov 2026, 15:46: the four groups low; too full = more than 20 waiting or the oldest over
10 minutes; a missed turn not caught up; after 5 skips in a row it runs anyway).

The decisions alone, then the keeper on the job runner's real tables (EAX_JOBS_TEST_DSN, as test_r5_46's)."""
import importlib.resources
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def _w(i, task, minutes=1, periodic=True, priority=None):
    from eax import job_priorities as jp
    return {"id": i, "task_name": task, "scheduled_at": NOW - timedelta(minutes=minutes), "periodic": periodic,
            "priority": jp.number(jp.default_level(task)) if priority is None else priority}


def test_the_owners_lists_are_low_and_peoples_work_and_alerts_high():
    from eax import job_priorities as jp
    for t in ("eax.quality_scheduler", "eax.quality_watch", "eax.quality_entities", "eax.quality_measure", "eax.quality_digest",
              "eax.surveys", "eax.servicedesk_overdue", "eax.kpi_monthly", "eax.resource_sample", "eax.reports_refresh",
              "eax.industry_packs", "eax.sites_health", "eax.optimise_report", "eax.discovery_scheduler"):
        assert jp.default_level(t) == "low", t
    assert jp.default_level("eax.alerts_run") == "high" and jp.default_level("eax.run_task") == "high"
    assert jp.default_level("eax.db_check") == "normal"
    assert jp.number("high") > jp.number("normal") > jp.number("low")


def test_every_task_gets_its_level_and_the_keeper_runs_every_minute_on_the_alerts_queue():
    from eax import job_priorities as jp
    from eax import jobs as J
    for t in J.app.tasks.values():
        if t.name.startswith("eax."):
            assert t.priority == jp.number(jp.default_level(t.name)), t.name
    k = J.app.tasks["eax.queue_keeper"]
    assert k.queue == "watch" and k.lock == "queue_keeper"
    assert any(p.task.name == "eax.queue_keeper" and p.cron == "* * * * *" for p in J.app.periodic_registry.periodic_tasks.values())


def test_too_full_is_more_than_20_waiting_or_the_oldest_over_10_minutes():
    from eax import job_priorities as jp
    assert not jp.too_full(20, 10)
    assert jp.too_full(21, 0) and jp.too_full(1, 10.5)
    assert not jp.too_full(30, 0, {"jobs_full_waiting": 50})


def test_when_full_only_low_recurring_jobs_are_skipped_never_peoples():
    from eax import job_priorities as jp
    waiting = [_w(i, "eax.db_check") for i in range(21)] + [_w(100, "eax.quality_watch"), _w(101, "eax.resource_sample"),
                                                           _w(102, "eax.quality_watch", periodic=False)]   # asked for: kept
    out = jp.decide(waiting, NOW, {}, {})
    assert out["full"] and out["skip"] == [100, 101]
    calm = jp.decide([_w(1, "eax.quality_watch")], NOW, {}, {})
    assert not calm["full"] and calm["skip"] == []


def test_after_five_skips_in_a_row_it_runs_anyway():
    from eax import job_priorities as jp
    waiting = [_w(i, "eax.db_check", minutes=30) for i in range(3)] + [_w(9, "eax.kpi_monthly")]
    assert jp.decide(waiting, NOW, {}, {"eax.kpi_monthly": 4})["skip"] == [9]
    out = jp.decide(waiting, NOW, {}, {"eax.kpi_monthly": 5})
    assert out["skip"] == [] and out["let_through"] == ["eax.kpi_monthly"]


def test_a_level_changed_on_the_page_is_applied_and_a_job_moved_by_hand_keeps_its_place():
    from eax import job_priorities as jp
    waiting = [_w(1, "eax.db_check"), _w(2, "eax.db_check", priority=7)]      # 7: moved by hand (Move up)
    out = jp.decide(waiting, NOW, {"eax.db_check": "high"}, {})
    assert out["reprioritise"] == {1: 100}
    full = [_w(i, "eax.db_check", minutes=30) for i in range(2)] + [_w(5, "eax.quality_watch")]
    assert jp.decide(full, NOW, {"eax.quality_watch": "normal"}, {})["skip"] == []    # no longer low: not skipped


def test_the_page_the_api_and_the_alert():
    api = (API / "eax/api/jobs.py").read_text()
    assert '@blp.route("/priorities")' in api and '@blp.route("/priorities/<string:task>")' in api
    assert api.count('@require_auth("system.operate")') >= 5
    page = (REPO / "services/web/src/Jobs.jsx").read_text()
    assert "<Priorities />" in page and "/api/v1/jobs/priorities" in page
    assert "jp.skipped_message(conn)" in (API / "eax/jobqueue.py").read_text()
    from eax import settings
    for k, d in (("jobs_full_waiting", 20), ("jobs_full_minutes", 10), ("jobs_skip_max", 5)):
        assert settings.REGISTRY[k][3] == d


# ---------------------------------------------------------------- on the job runner's real tables
DSN = os.environ.get("EAX_JOBS_TEST_DSN", "")


@pytest.fixture()
def engine(monkeypatch):
    if not DSN:
        pytest.skip("needs EAX_JOBS_TEST_DSN (a PostgreSQL server to make a test database on)")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from eax import settings
    monkeypatch.setattr(settings, "values", lambda *a, **k: {})
    admin = create_engine(DSN, isolation_level="AUTOCOMMIT")
    name = f"jobs_prio_{uuid.uuid4().hex[:10]}"
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    eng = create_engine(make_url(DSN).set(database=name))
    schema = (importlib.resources.files("procrastinate") / "sql" / "schema.sql").read_text()
    with eng.begin() as c:
        c.execute(text("CREATE SCHEMA jobs; CREATE SCHEMA core"))
        c.execute(text("""CREATE TABLE core.tasks (id bigserial PRIMARY KEY, job_id bigint, kind text, label text,
                          requested_by text, status text, message text, finished_at timestamptz)"""))
        c.execute(text((API / "migrations/sql/0098_r5_6_job_priorities.sql").read_text()))
        c.execute(text("SET LOCAL search_path TO jobs, public"))
        c.connection.driver_connection.execute(schema)
    yield eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


def _defer(c, task, periodic=True, priority=0, minutes=1):
    from sqlalchemy import text
    c.execute(text("SET LOCAL search_path TO jobs, public"))
    return c.execute(text("""INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, priority, args, scheduled_at)
                             VALUES ('default', :t, :p, CAST(:a AS jsonb), now() - make_interval(mins => :m)) RETURNING id"""),
                     {"t": task, "p": priority, "a": '{"timestamp": 1}' if periodic else "{}", "m": minutes}).scalar()


def test_the_keeper_on_a_real_queue(engine):
    from sqlalchemy import text

    from eax import job_priorities as jp
    with engine.begin() as c:
        normal = [_defer(c, "eax.db_check") for _ in range(21)]
        low = _defer(c, "eax.quality_watch", priority=-100)
        asked = _defer(c, "eax.quality_entities", periodic=False, priority=-100)
    with engine.begin() as c:
        out = jp.keep(c)
    with engine.connect() as c:
        st = dict(c.execute(text("SELECT id, status::text FROM jobs.procrastinate_jobs")).all())
        sk = jp.skips(c)
        ev = [r[0] for r in c.execute(text("SELECT type::text FROM jobs.procrastinate_events WHERE job_id = :j"), {"j": low})]
    assert out["full"] and st[low] == "cancelled" and st[asked] == "todo" and all(st[n] == "todo" for n in normal)
    assert sk["eax.quality_watch"]["in_row"] == 1 and sk["eax.quality_watch"]["total"] == 1 and "cancelled" in ev
    with engine.begin() as c:                                  # calm again: the next one waits, its row starts again
        c.execute(text("SET LOCAL search_path TO jobs, public"))     # the runner's trigger names its types bare
        c.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'cancelled' WHERE task_name = 'eax.db_check'"))
        nxt = _defer(c, "eax.quality_watch", priority=-100)
    with engine.begin() as c:
        jp.keep(c)
    with engine.connect() as c:
        assert c.execute(text("SELECT status::text FROM jobs.procrastinate_jobs WHERE id = :j"), {"j": nxt}).scalar() == "todo"
        assert jp.skips(c)["eax.quality_watch"]["in_row"] == 0


def test_a_level_set_on_the_page_moves_the_waiting_jobs(engine):
    from sqlalchemy import text

    from eax import job_priorities as jp
    with engine.begin() as c:
        j = _defer(c, "eax.db_check")
        jp.set_level(c, "eax.db_check", "high", "it_admin", ["eax.db_check"])
    with engine.begin() as c:
        jp.keep(c)
    with engine.connect() as c:
        assert c.execute(text("SELECT priority FROM jobs.procrastinate_jobs WHERE id = :j"), {"j": j}).scalar() == 100
        assert jp.listing(c, ["eax.db_check"])["kinds"][0]["level"] == "high"
    with engine.begin() as c:
        jp.set_level(c, "eax.db_check", "normal", "it_admin", ["eax.db_check"])     # as it ships: the change goes
        assert jp.overrides(c) == {}
