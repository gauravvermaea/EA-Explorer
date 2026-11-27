"""R5.5 enterprise discovery on a real database: a whole run as the AI makes it through MCP, against every migration
(0001 to the newest) on PostgreSQL. Each test runs in a transaction rolled back at the end.

They need a PostgreSQL database every migration has run on: EAX_MIGRATED_TEST_DSN, for example
postgresql+psycopg://postgres@127.0.0.1:55432/eaxmig. Without it they are skipped (the code tests in
test_r5_5_discovery.py run anywhere)."""
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")
pytestmark = pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")


class U:
    def __init__(self, name, roles):
        self.username, self.roles, self.break_glass = name, tuple(roles), False


SA = U("sue_admin", ["super-admin"])
DA = U("dan_discovery", ["discovery-admin", "user"])
PLAIN = U("pat", ["user"])


@pytest.fixture()
def conn(monkeypatch):
    from sqlalchemy import create_engine, text

    from eax import kpis, notify, permissions, settings
    monkeypatch.setattr(notify, "create", lambda *a, **k: 1)
    monkeypatch.setattr(settings, "values", lambda *a, **k: {})
    monkeypatch.setattr(kpis, "on_tag", lambda *a, **k: None)
    eng = create_engine(DSN)
    c = eng.connect()
    tx = c.begin()
    c.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
    permissions.current.set(SA)
    m = c.execute(text("INSERT INTO core.models (name, kind_code) VALUES ('Discovery target', 'project') RETURNING id, guid")).first()
    c.execute(text("INSERT INTO core.domains (model_id, code, name) VALUES (:m, 'app', 'Application')"), {"m": m.id})
    from eax import metamodel_edit as me
    me.apply(c, str(m.guid), "entity_type.create", {"name": "Application", "domain": "app"}, "sue_admin")
    c.model = str(m.guid)
    yield c
    tx.rollback()
    c.close()
    eng.dispose()


def _project(conn, **kw):
    from eax import discovery_projects as dp
    p = dp.create(conn, DA, {"name": "Claims estate", "target_model": conn.model, **kw})
    dp.add_resource(conn, DA, p["id"], {"kind": "git", "name": "Claims repo", "location": "https://git.example.com/claims.git"})
    return p


def _add(conn, *names):
    from eax import commits as cm
    cm.record_entity_rows(conn, conn.model, "Application", [{"name": n} for n in names], SA.username)


def test_only_a_discovery_admin_sets_up_and_everyone_on_the_model_sees_it(conn):
    from eax import discovery_projects as dp
    from eax.metamodel_edit import EditError
    with pytest.raises(EditError) as e:
        dp.create(conn, PLAIN, {"name": "x", "target_model": conn.model})
    assert e.value.status == 403
    p = _project(conn)
    assert p["set_up_by"] == "dan_discovery" and p["target_model"]["name"] == "Discovery target"
    with pytest.raises(EditError):
        dp.create(conn, DA, {"name": "claims ESTATE", "target_model": conn.model})        # names are unique
    assert [x["name"] for x in dp.listing(conn, PLAIN)["projects"]] == ["Claims estate"]   # (RLS bypassed here)


def test_a_run_asks_first_then_tags_and_hands_over_the_sources(conn):
    from eax import discovery_projects as dp
    _project(conn, read_default="all", gone_default="delete")
    ask = dp.start_run(conn, SA, "Claims estate")
    assert ask["ask"] and ask["read"]["default"] == "all" and ask["gone"]["default"] == "delete"
    run = dp.start_run(conn, SA, "Claims estate", "new", "mark", "a client")
    assert run["number"] == 1 and "run 1 " in run["tagged"] and run["tagged"].endswith("(before)") and run["who"] == "AI agent on behalf of dan_discovery"
    assert run["sources"][0]["name"] == "Claims repo" and "read everything" in run["sources"][0]["position"]
    from eax.metamodel_edit import EditError
    with pytest.raises(EditError):
        dp.start_run(conn, SA, "Claims estate", "new", "mark")                           # one run at a time


def test_a_whole_run_found_in_skipped_maybe_same_committed_and_tagged(conn):
    from sqlalchemy import text

    from eax import discovery_projects as dp
    _project(conn, schedule="daily", schedule_time="03:00")
    _add(conn, "Policy admin")
    from eax import commits as cm
    from eax import repository as repo
    cm.commit(conn, conn.model, SA, message="before")
    run = dp.start_run(conn, SA, "Claims estate", "all", "mark")["run"]
    _add(conn, "Claims API")
    dp.record_found(conn, SA, run, [{"element": "Claims API", "source": "Claims repo", "item": "README.md", "place": "line 3",
                                     "link": "https://git.example.com/claims/README.md", "may_be_same": "Policy admin"}])
    dp.record_skipped(conn, SA, run, [{"source": "Claims repo", "title": "Board pack.docx", "date": "2026-11-01"}])
    out = dp.finish_run(conn, SA, run, {"Claims repo": "commit abc123"}, [{"element": "Policy admin", "source": "Claims repo"}],
                        "One application found.")
    assert out["run"]["status"] == "finished" and out["run"]["counts"] == {"found": 1, "skipped": 1, "may_be_same": 1,
                                                                            "not_found": 1, "committed": 1}
    assert out["found"][0]["element_id"] and out["may_be_same"][0]["other_id"]
    assert out["skipped"][0]["title"] == "Board pack.docx" and "NOT FOR AI" in out["skipped"][0]["reason"]
    assert out["not_found"][0]["action"] == "marked" and "&right=tag:" in out["compare"]
    m = repo.get_model(conn, conn.model)
    msg = conn.execute(text("SELECT message FROM core.commits WHERE model_id = :m ORDER BY id DESC LIMIT 1"), {"m": m["_id"]}).scalar()
    assert msg == "AI agent on behalf of dan_discovery: discovery Claims estate run 1"
    e = conn.execute(text("SELECT guid FROM core.entities WHERE name = 'Claims API' AND NOT is_deleted")).scalar()
    f = dp.found_in(conn, PLAIN, conn.model, str(e))
    assert f["found_in"][0]["item"] == "README.md" and f["found_in"][0]["who"] == "AI agent on behalf of dan_discovery"
    pa = conn.execute(text("SELECT guid FROM core.entities WHERE name = 'Policy admin' AND NOT is_deleted")).scalar()
    assert dp.found_in(conn, PLAIN, conn.model, str(pa))["not_found_since"]["action"] == "marked"
    d = dp.detail(conn, PLAIN, "Claims estate")
    assert d["sources"][0]["position"] == "commit abc123" and d["next_due_at"] is not None


def test_what_is_gone_is_deleted_when_the_run_says_so(conn):
    from sqlalchemy import text

    from eax import commits as cm
    from eax import discovery_projects as dp
    _project(conn)
    _add(conn, "Old system")
    cm.commit(conn, conn.model, SA, message="before")
    run = dp.start_run(conn, SA, "Claims estate", "new", "delete")["run"]
    out = dp.finish_run(conn, SA, run, {}, [{"element": "Old system"}])
    assert out["not_found"][0]["action"] == "deleted"
    assert conn.execute(text("SELECT count(*) FROM core.entities WHERE name = 'Old system' AND NOT is_deleted")).scalar() == 0


def test_only_the_ai_that_started_a_run_reports_into_it(conn):
    from eax import discovery_projects as dp
    from eax.metamodel_edit import EditError
    _project(conn)
    run = dp.start_run(conn, SA, "Claims estate", "new", "mark")["run"]
    with pytest.raises(EditError) as e:
        dp.record_found(conn, DA, run, [{"element": "x"}])
    assert e.value.status == 403


def test_a_run_left_running_is_abandoned_by_the_next(conn):
    from eax import discovery_projects as dp
    _project(conn)
    t0 = datetime.now(UTC)
    first = dp.start_run(conn, SA, "Claims estate", "new", "mark", now=t0)
    second = dp.start_run(conn, SA, "Claims estate", "new", "mark", now=t0 + timedelta(hours=13))
    assert second["number"] == 2
    assert dp.report(conn, SA, first["run"])["run"]["status"] == "abandoned"


def test_due_and_overdue(conn):
    from sqlalchemy import text

    from eax import discovery_projects as dp
    _project(conn, schedule="daily")
    now = datetime.now(UTC)
    conn.execute(text("UPDATE core.discovery_projects SET next_due_at = :d"), {"d": now - timedelta(hours=3)})
    due = dp.due(conn, SA, now)
    assert [x["name"] for x in due] == ["Claims estate"] and due[0]["state"] == "overdue"
    assert dp.overdue_count(conn, now) == 1


def test_the_ai_logs_a_decision_it_found_as_a_draft_for_the_board(conn):
    from eax import decisions as dec
    from eax import discovery_projects as dp
    _project(conn)
    run = dp.start_run(conn, SA, "Claims estate", "new", "mark")["run"]
    out = dp.log_decision(conn, conn, SA, run, {"kind": "ADR", "title": "Use event streaming for claims", "source": "Claims repo",
                                                 "item": "docs/adr/0007.md"})
    r = next(x for x in dec.org_listing(conn, SA)["records"] if x["id"] == out["id"])
    assert r["status"] == "Draft" and r["found_in"]["item"] == "docs/adr/0007.md"
    assert r["found_in"]["who"] == "AI agent on behalf of dan_discovery"


def test_a_project_deleted_and_set_up_again_runs_again(conn):
    """Its runs start at 1 again: the tags of a run carry the run's own id, so they never clash with the earlier ones."""
    from eax import discovery_projects as dp
    p = _project(conn)
    run = dp.start_run(conn, SA, "Claims estate", "new", "mark")["run"]
    dp.finish_run(conn, SA, run)
    dp.delete(conn, DA, p["id"])
    _project(conn)
    again = dp.start_run(conn, SA, "Claims estate", "new", "mark")
    assert again["number"] == 1 and dp.finish_run(conn, SA, again["run"])["run"]["status"] == "finished"


def test_a_library_frozen_or_read_only_model_is_refused_as_the_target(conn):
    from sqlalchemy import text

    from eax import discovery_projects as dp
    from eax.metamodel_edit import EditError
    for change in ("kind_code = 'reference', library_state = 'published'", "frozen_at = now()", "lifecycle = 'archived'", "lock_level = 'content'"):
        m = conn.execute(text("INSERT INTO core.models (name, kind_code) VALUES ('Not a target', 'project') RETURNING id, guid")).first()
        conn.execute(text(f"UPDATE core.models SET {change} WHERE id = :i"), {"i": m.id})
        with pytest.raises(EditError) as e:
            dp.create(conn, DA, {"name": f"refused {change}", "target_model": str(m.guid)})
        assert e.value.status == 400, change
        conn.execute(text("UPDATE core.models SET name = name || id WHERE id = :i"), {"i": m.id})
    p = _project(conn)                                       # one set up keeps its target, even if it is frozen later
    conn.execute(text("UPDATE core.models SET frozen_at = now() WHERE guid = :g"), {"g": conn.model})
    assert dp.update(conn, DA, p["id"], {"purpose": "still saved"})["purpose"] == "still saved"
