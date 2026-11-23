"""Release 12, R12.2 (D858, D879, D880): architecture in sprints, only for a project of the Agile type.

The whole flow was run on a real PostgreSQL while building (22 Nov 2026), the module's own SQL through psql: a project
of another type refused; the usual length 14 from the template, set to 10; two items added; Sprint 1 planned with a
deliverable, two steps and phases B and C, ending 10 days on; a second open sprint refused; a review with an item left
undecided refused; the review recorded one accepted and one back to the backlog (returned once); Sprint 2 planned from
what was left. These tests keep the rules that run said."""

from __future__ import annotations

import inspect
import types
from pathlib import Path

import pytest

from eax import agile as ag
from eax import project_backup as pb
from eax.metamodel_edit import EditError

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "web" / "src"
SQL = (ROOT / "migrations" / "sql" / "0117_r12_agile_sprints.sql").read_text(encoding="utf-8")
SRC = inspect.getsource(ag)


def test_the_tables():
    for t in ("proj.agile_settings", "proj.sprints", "proj.backlog_items", "proj.sprint_decisions"):
        assert f"CREATE TABLE IF NOT EXISTS {t}" in SQL
    assert "steps         text[]" in SQL                    # labels, so a project restored elsewhere keeps them
    assert "backlog_items_entity" in SQL and "WHERE entity_guid IS NOT NULL" in SQL   # a requirement once only
    v = (ROOT / "migrations" / "versions" / "0117_r12_agile_sprints.py").read_text(encoding="utf-8")
    assert 'down_revision = "0116_release_11_0_0"' in v and "DROP TABLE IF EXISTS proj." in v


def test_only_an_agile_project_has_sprints():
    assert ag.is_agile({"template_code": "agile"}) and not ag.is_agile({"template_code": "transformation"})
    assert not ag.is_agile({"template_code": None})
    assert "sprints are only for a project made from the Agile template" in SRC
    assert ag.count(None, {"template_code": "transformation", "id": 1}) is None


def test_the_backlog_is_offered_from_the_models_never_taken_in_by_itself():
    assert ag.BACKLOG_TYPES == ("Requirement", "SecurityRequirement", "Epic", "Feature")
    fill = inspect.getsource(ag.overview)
    assert "add_to_backlog" not in fill and "offered(pc" in fill          # the overview counts what is offered, adds nothing
    assert "is not a requirement, epic or feature in this project's models, or is in the backlog already" in SRC


def test_planning_rules():
    plan = inspect.getsource(ag.plan)
    assert "A sprint is still open in this project: review it first." in plan
    assert "Agree the ADM phases the sprint runs" in plan
    assert "Name who accepts the sprint's deliverables" in plan
    assert "timedelta(days=sprint_days(pc, p) - 1)" in plan                 # the usual length unless dates are given
    assert "Pick at least one backlog item or deliverable" in plan
    assert ag.template_days.__doc__ and ag.DEFAULT_DAYS == 14


def test_the_review_sends_what_is_not_accepted_back():
    rv = inspect.getsource(ag.review)
    assert "Decide every item of the sprint" in rv
    assert "status = 'backlog', sprint_id = NULL, returned = returned + 1" in rv
    assert "status = 'accepted'" in rv and "accepted_by" in rv


def test_the_accepter_decides_when_a_member():
    calls = []

    class PC:
        def execute(self, *_a, **_k):
            raise AssertionError("not reached")

    orig_rows, orig_need = ag._rows, ag.pj._need
    try:
        ag._rows = lambda pc, sql, **p: [{"u": "po"}]
        ag.pj._need = lambda pc, p, user, what: calls.append(what)
        ag._may_accept(PC(), {"id": 1}, types.SimpleNamespace(username="po"), {"accepter": "PO"})
        assert calls == []                                   # the accepter themself
        ag._may_accept(PC(), {"id": 1}, types.SimpleNamespace(username="other"), {"accepter": "po"})
        assert calls == ["admin"]                            # someone else needs to be a project admin
        calls.clear()
        ag._may_accept(PC(), {"id": 1}, types.SimpleNamespace(username="other"), {"accepter": "The product owner"})
        assert calls == []                                   # a named person outside: a contributor records it
    finally:
        ag._rows, ag.pj._need = orig_rows, orig_need


def test_the_sprint_length_is_checked():
    orig = ag._project
    try:
        ag._project = lambda *a, **k: {"id": 1, "name": "X"}
        for bad in ("x", 0, 91):
            with pytest.raises(EditError):
                ag.set_sprint_days(None, "p", types.SimpleNamespace(username="u"), bad)
    finally:
        ag._project = orig


def test_dates():
    assert ag._date("2026-12-01", "x").isoformat() == "2026-12-01"
    with pytest.raises(EditError):
        ag._date("soon", "The start")


def test_the_routes_the_backup_and_the_project_page():
    api = (ROOT / "eax" / "api" / "agile.py").read_text(encoding="utf-8")
    for route in ("/projects/<string:project>/agile\"", "/agile/offered", "/agile/backlog\"", "/agile/backlog/<string:item>",
                  "/agile/sprint-length", "/agile/sprints\"", "/agile/sprints/<string:sprint>\"", "/review\""):
        assert route in api, route
    assert "agile_blp" in (ROOT / "eax" / "app.py").read_text(encoding="utf-8")
    tables = [t for t, *_ in pb.TABLES] if hasattr(pb, "TABLES") else inspect.getsource(pb)
    for t in ("agile_settings", "sprints", "backlog_items", "sprint_decisions"):
        assert t in tables, t
    assert 'out["agile"] = agile.count(conn, p)' in (ROOT / "eax" / "projects.py").read_text(encoding="utf-8")


def test_the_sprints_tab_only_on_an_agile_project():
    pj = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    assert '["sprints", "Sprints"]' in pj and '(k !== "sprints" || !!p.agile)' in pj
    assert '{tab === "sprints" && p.agile && <SprintsTab p={p} />}' in pj
    tab = (WEB / "Sprints.jsx").read_text(encoding="utf-8")
    for s in ("/agile/offered", "/agile/backlog", "/agile/sprints", "/review", "Plan the sprint", "Record the review",
              "back to the backlog"):
        assert s in tab, s
    assert '"tab:Sprints"' in (WEB / "help" / "catalogue.json").read_text(encoding="utf-8")
