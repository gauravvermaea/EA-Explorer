"""Release 12, R12.4 (D879, D884, D886, D889): the base improvements.

* project management (TOGAF Series Guide G188): RACI chosen at setup (none, per phase, per deliverable or per step),
  approval gates chosen by the architect, a free roadmap period, a plan of the phases, milestones, status reports;
* maps always live: the map and catalogue items open their view on the project's primary working model;
* business scenarios in Requirements Management, building blocks in phases E and F (an attribute on existing types, no
  new type, D887; view VP-58);
* every existing project and every existing model brought up to date by script at start (D884, D886).

The flows were run on a real PostgreSQL while building (23 Nov 2026), the modules' own SQL through psql:
- the project upgrade added the one missing step and item to a project running phase E, set the live views and queued
  its repository once; a second run changed nothing;
- the model upgrade gave a model stripped of its Release 12 attributes back its 14 attributes, their places on its
  types, the rules and the pick lists; a second run changed nothing; models not made from the root were left alone;
- the plan: bad settings refused, RACI refused while none, two Accountable refused, a stranger refused, a phase plan
  ending before it starts refused, a late milestone and a late phase counted, a gated phase with deliverables waiting
  refused completion while an ungated one completed, RACI per step kept.
These tests keep the rules that run said."""

from __future__ import annotations

import inspect
import json
import types
from pathlib import Path

import pytest

from eax import pm
from eax import project_backup as pb
from eax import projects as pj
from eax.metamodel_edit import EditError
from eax.report_defs import VIEWS
from eax.seed import archimate4 as A
from eax.seed import build
from eax.seed import project_library as pl

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "web" / "src"
SQL = (ROOT / "migrations" / "sql" / "0119_r12_project_management.sql").read_text(encoding="utf-8")
MAIN = (ROOT / "eax" / "seed" / "__main__.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- the tables
def test_the_tables():
    for t in ("pm_settings", "phase_plans", "milestones", "raci", "status_reports"):
        assert f"CREATE TABLE IF NOT EXISTS proj.{t}" in SQL
    assert "CHECK (raci IN ('none', 'phase', 'deliverable', 'step'))" in SQL
    assert "raci          text NOT NULL DEFAULT 'none'" in SQL and "gates         text[] NOT NULL DEFAULT '{}'" in SQL   # as before
    assert "ADD COLUMN IF NOT EXISTS live_view" in SQL
    # RACI kept by reference, so a project's backup and restore keep it
    assert "item_id       bigint REFERENCES proj.items (id) ON DELETE CASCADE" in SQL
    assert "step_id       bigint REFERENCES proj.steps (id) ON DELETE CASCADE" in SQL
    v = (ROOT / "migrations" / "versions" / "0119_r12_project_management.py").read_text(encoding="utf-8")
    assert 'down_revision = "0118_r12_agile_dorp"' in v and "DROP TABLE IF EXISTS proj." in v


def test_the_plan_is_in_a_project_backup_in_order():
    names = [t[0] for t in pb.TABLES]
    for t in ("pm_settings", "phase_plans", "milestones", "raci", "status_reports"):
        assert t in names
    raci = dict((t[0], t[2]) for t in pb.TABLES)["raci"]
    assert raci == {"item_id": "items", "step_id": "steps"}
    assert names.index("items") < names.index("raci") and names.index("steps") < names.index("raci")


# ---------------------------------------------------------------- the library and maps always live
def test_the_new_steps_and_document_types():
    lib = json.loads((ROOT / "eax" / "seed" / "project_library.json").read_text(encoding="utf-8"))
    phases = {p["code"] for p in lib["phases"]}
    assert {s[0] for s in pl.R12_STEPS} == {"A", "RM", "E", "F"} and all(s[0] in phases for s in pl.R12_STEPS)
    assert any("business scenarios" in s[1] for s in pl.R12_STEPS if s[0] == "RM")
    assert any("building blocks" in s[1] for s in pl.R12_STEPS if s[0] == "E")
    assert any("building blocks" in s[1] for s in pl.R12_STEPS if s[0] == "F")
    have = {i["id"] for i in lib["items"]}
    assert not {i[0] for i in pl.R12_ITEMS} & have                   # new ids
    assert all(i[1] in phases and i[3] in ("Deliverable", "Artifact") for i in pl.R12_ITEMS)
    sql = pl.r12_library_sql()
    assert "ON CONFLICT (phase, name) DO NOTHING" in sql and "coalesce(max(seq), 0) + 1" in sql   # after the phase's last step
    assert "AND i.live_view = ''" in sql                             # a Super Admin's choice is kept
    assert "r12_library_sql()" in inspect.getsource(pl.library_sql)


def test_the_maps_are_always_live_from_their_views():
    codes = {v["code"] for v in VIEWS}
    assert pl.LIVE_VIEWS["G047"] == "VP-01" and pl.LIVE_VIEWS["G045"] == "VP-47"      # Organization Map, Information Map
    assert pl.LIVE_VIEWS["G036"] == "VP-19" and pl.LIVE_VIEWS["G020"] == "VP-49"      # capability map, business scenarios
    assert pl.LIVE_VIEWS["G113"] == pl.LIVE_VIEWS["G120"] == "VP-58"                  # the building blocks
    assert set(pl.LIVE_VIEWS.values()) <= codes
    src = inspect.getsource(pj)
    assert "i.live_view" in inspect.getsource(pj._items) and "i.mayan_cabinet_id IS NOT NULL AS stored, i.live_view," in src
    assert 'it["live_view_as"]' in src
    ui = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    assert "i.live_view && p.home_model" in ui and "live view</a>" in ui


def test_building_blocks_are_an_attribute_on_existing_types_and_a_view():
    assert A.LISTS["BuildingBlock"] == ["Architecture building block", "Solution building block"]
    assert "BuildingBlock" in [a[0] for a in A.ATTRS] and "BuildingBlock" in build.UPGRADE_ATTRS
    for t in A.BUILDING_BLOCK_TYPES:
        assert t in A.ALL_TYPES and ("BuildingBlock", "N", "Architecture") in A.MAP[t]
    vp = {v["code"]: v for v in VIEWS}["VP-58"]
    assert vp["name"] == "Building blocks" and "BuildingBlock" in json.dumps(vp) and vp["default_view"] == "catalog"
    assert len(VIEWS) == 58


# ---------------------------------------------------------------- existing projects and models, by script
def test_existing_projects_are_brought_up_to_date_at_start():
    sql = pl.project_upgrade_sql()
    # only in the phases the project runs, only what it lacks
    assert "h.phase = s.phase" in sql and "h.library_id = s.id" in sql
    assert "h.phase = i.phase" in sql and "h.library_id = i.id" in sql
    assert "repo_state = CASE WHEN repo_state = 'building' THEN repo_state ELSE 'pending' END" in sql   # folders made
    assert "t.live_view = ''" in sql
    assert "INSERT INTO proj.pm_settings (project_id) SELECT id FROM proj.projects ON CONFLICT (project_id) DO NOTHING" in sql
    assert "pconn.execute(project_library.project_upgrade_sql())" in MAIN
    assert MAIN.index("project_library.library_sql()") < MAIN.index("project_library.project_upgrade_sql()")


def test_existing_models_get_the_new_attributes_at_start():
    sql = build.model_upgrade_sql()
    assert "WITH RECURSIVE" in sql and "s.guid = u.cur_origin" in sql      # traced through copies of copies
    for t in ("pick_lists", "pick_list_values", "attribute_types", "item_attributes", "validation_rules", "allowed_relationships"):
        assert f"INSERT INTO core.{t}" in sql
    # what a model has, or once had and deleted, is left alone: no is_deleted filter on what it already has
    assert "NOT EXISTS (SELECT 1 FROM core.attribute_types x WHERE x.model_id = m.model_id AND (x.code = a.code OR x.column_name = a.column_name))" in sql
    assert "rs.code = 'Control'" in sql and "rt.code = 'Assessment'" in sql
    for code in build.UPGRADE_ATTRS:
        assert f"'{code}'" in sql
    assert "conn.execute(model_upgrade_sql())" in MAIN
    assert MAIN.index("conn.execute(root_upgrade_sql())") < MAIN.index("conn.execute(model_upgrade_sql())")


# ---------------------------------------------------------------- the plan's rules
class _Pc:
    """Records what is written."""
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((str(sql), params or {}))
        return types.SimpleNamespace(mappings=lambda: types.SimpleNamespace(all=lambda: [], first=lambda: None))


@pytest.fixture
def phases(monkeypatch):
    monkeypatch.setattr(pm, "_rows", lambda pc, sql, **k: [{"code": c} for c in ("P", "A", "B", "C", "E", "F", "G", "RM")]
                        if "lib_phases" in sql else [])


def _now():
    return {"raci": "none", "gates": [], "roadmap_from": None, "roadmap_to": None, "roadmap_marks": "year"}


def test_settings_are_checked(phases):
    with pytest.raises(EditError, match="RACI is one of"):
        pm._checked(None, {}, {"raci": "always"}, _now())
    with pytest.raises(EditError, match="No phase Z"):
        pm._checked(None, {}, {"gates": ["Z"]}, _now())
    with pytest.raises(EditError, match="end comes after its start"):
        pm._checked(None, {}, {"roadmap_from": "2027-01-01", "roadmap_to": "2026-01-01"}, _now())
    with pytest.raises(EditError, match="marks are one of"):
        pm._checked(None, {}, {"roadmap_marks": "week"}, _now())
    s = pm._checked(None, {}, {"raci": "step", "gates": ["B", "B", "F"], "roadmap_from": "2026-01-01", "roadmap_to": "",
                               "roadmap_marks": "quarter"}, _now())
    assert s["raci"] == "step" and s["gates"] == ["B", "F"] and s["roadmap_to"] is None and s["roadmap_marks"] == "quarter"
    # nothing chosen at setup: as before
    assert pm._checked(None, {}, {}, _now()) == _now()


def _raci_setup(monkeypatch, mode="phase"):
    monkeypatch.setattr(pm, "text", lambda s: s)
    monkeypatch.setattr(pm, "_project", lambda pc, project, user, what="read": {"id": 1, "name": "X"})
    monkeypatch.setattr(pm, "settings", lambda pc, p: {**_now(), "raci": mode})
    monkeypatch.setattr(pm, "_refs", lambda pc, p, scope: {"B": ("Phase B", "B")})
    monkeypatch.setattr(pm, "_rows", lambda pc, sql, **k: [{"username": "ann"}, {"username": "bob"}] if "members" in sql else [])


def test_raci_rules(monkeypatch):
    user = types.SimpleNamespace(username="ann")
    _raci_setup(monkeypatch, "none")
    with pytest.raises(EditError, match="does not record RACI"):
        pm.set_raci(_Pc(), "p", user, "B", {"ann": ["A"]})
    _raci_setup(monkeypatch)
    with pytest.raises(EditError, match="No such phase"):
        pm.set_raci(_Pc(), "p", user, "Z", {"ann": ["A"]})
    with pytest.raises(EditError, match="One person is Accountable, not 2"):
        pm.set_raci(_Pc(), "p", user, "B", {"ann": ["A"], "bob": ["A"]})
    with pytest.raises(EditError, match="not one of the project's people"):
        pm.set_raci(_Pc(), "p", user, "B", {"cat": ["R"]})
    with pytest.raises(EditError, match="R, A, C and I"):
        pm.set_raci(_Pc(), "p", user, "B", {"ann": ["X"]})
    pc = _Pc()
    out = pm.set_raci(pc, "p", user, "B", {"ann": ["A", "R"], "bob": "C"})
    assert out["accountable"] == "ann"
    writes = [p for s, p in pc.sql if "INSERT INTO proj.raci" in s]
    assert sorted((w["u"], w["x"]) for w in writes) == [("ann", "A"), ("ann", "R"), ("bob", "C")]
    assert all(w["v"] == "B" for w in writes) and "phase = :v" in pc.sql[0][0]    # replaces what was there for that phase


def test_gates():
    src = inspect.getsource(pm.gate_waiting)
    assert "i.chosen AND i.kind = 'Deliverable'" in src and "d.state IN ('Approved', 'Accepted')" in src
    assert "is an approval gate" in inspect.getsource(pm.check_gate)
    mark = inspect.getsource(pj.mark_phase)
    assert mark.index("pm.check_gate(conn, p, phase)") < mark.index("INSERT INTO proj.phase_states")   # only completing


def test_phase_plans_milestones_and_status():
    assert "The end comes on or after the start." in inspect.getsource(pm.set_phase_plan)
    assert "Give the milestone a name." in inspect.getsource(pm.add_milestone)
    assert pm.RAG == ("green", "amber", "red") and "The status is green, amber or red." in inspect.getsource(pm.add_status)
    ov = inspect.getsource(pm.overview)
    assert 'm["late"] = not m["done_at"] and m["due_on"] < today' in ov and "pl[\"ends_on\"] < today" in ov


def test_setup_chooses_raci_and_gates_nothing_forced():
    assert 'pm.from_wizard(conn, p, user, d.get("management"))' in inspect.getsource(pj.create)
    ui = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    assert 'management: { raci: "none", gates: [] }' in ui                 # offered, none by default (D880)
    assert "function Management(" in ui and "{!live && <Management" in ui
    assert 'management: editId ? undefined : d.management || undefined' in ui


def test_the_tab_the_routes_and_the_page():
    app = (ROOT / "eax" / "app.py").read_text(encoding="utf-8")
    assert "from .api.pm import blp as plan_blp" in app and "agile_blp, plan_blp, risk_blp):" in app
    api = (ROOT / "eax" / "api" / "pm.py").read_text(encoding="utf-8")
    for r in ("/plan\")", "/plan/settings\")", "/plan/phases/<string:phase>\")", "/plan/milestones\")",
              "/plan/milestones/<string:milestone>\")", "/plan/raci/<string:ref>\")", "/plan/status\")"):
        assert r in api
    assert 'out["plan"] = pm.count(conn, p)' in inspect.getsource(pj.detail)
    ui = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    assert '["projectplan", "Project plan"]' in ui and '"phases", "projectplan", "sprints"' in ui
    assert '{tab === "projectplan" && <ProjectPlanTab p={p} />}' in ui
    tab = (WEB / "ProjectPlan.jsx").read_text(encoding="utf-8")
    assert "<Roadmap model={p.home_model} from={s.roadmap_from} to={s.roadmap_to} marks={s.roadmap_marks} />" in tab
    help_ = json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "tab:Project plan" in help_ and "field:RACI" in help_


def test_the_roadmap_period_is_free_and_as_before_by_default():
    maps = (WEB / "Maps.jsx").read_text(encoding="utf-8")
    assert 'export function Roadmap({ model, from = "", to = "", marks = "year" })' in maps
    assert "function roadmapTicks(lo, hi, marks)" in maps
    assert "outside the period shown" in maps
    # with no period the span is the items' whole years, as it was
    assert "getUTCFullYear() + 1, 0, 1)).getTime();" in maps


def test_the_release_12_screens_have_browser_journeys():
    """The owner, 23 Nov 2026: "can you not write tests for screens?": the self-test's browser journeys click through
    the Release 12 screens (eax test full, or watched from Self-test), each in the run's own fixtures."""
    from eax.testing import ui_flows
    keys = {ui_flows.key(j) for j in ui_flows.JOURNEYS}
    assert {"project plan", "live maps", "risk register", "ready-made survey", "TOGAF skills", "guides"} <= keys
    plan = [j for j in ui_flows.JOURNEYS if ui_flows.key(j) == "project plan"][0]
    said = [s.get("expect") for s in plan["steps"]]
    assert "is an approval gate" in said and "Status reported: amber" in said     # the gate refuses; the status is kept
    assert plan["steps"][-1] == {"expect_not": "RACI, per phase", "timeout": 5000}  # put back as it was
