"""Release 10 (D788, D818, D857): scenario planning and game theory in a project, run by the person's AI over MCP.

The study's rules (eax/scenario_planning.py) on an in-memory store standing in for proj.sp_runs and
proj.sp_signpost_marks (the SQL is four small helpers), and **the MCP tools as an AI calls them**
(eax/mcp_scenario_planning.py): a changing tool answers with a preview and a confirm token, and does it only when called
again with the same arguments and that token (D458); the working is EA Explorer's own (eax/game_theory.py)."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import re
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from eax import permissions as perms
from eax import scenario_planning as sp
from eax.metamodel_edit import EditError
from eax.seed import sample_planning as sample

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
WHO = perms.Principal("user_lead_architect", ("user",))


class Store:
    """proj.sp_runs and proj.sp_signpost_marks in memory, behind the module's helpers."""

    def __init__(self):
        self.runs: list[dict] = []
        self.marks: list[dict] = []

    def install(self, mp, models=("Protea scenario A: build", "Protea scenario B: buy")):
        p = {"id": 7, "guid": "pg-7", "name": "Protea build or buy (sample)"}
        mp.setattr(sp, "_project", lambda pc, project, user, what="read": p)
        mp.setattr(sp, "_models", lambda pc, p: {m.lower() for m in models})
        mp.setattr(sp, "_runs", lambda pc, p: sorted(self.runs, key=lambda r: -r["version"]))
        mp.setattr(sp, "_insert", self.insert)
        mp.setattr(sp, "_set", self.set)
        mp.setattr(sp, "_delete_draft", lambda pc, rid: self.runs.remove(next(r for r in self.runs if r["id"] == rid)))
        mp.setattr(sp, "_add_mark", lambda pc, rid, ref, seen, note, by: self.marks.append(
            {"run_id": rid, "signpost": ref, "seen": seen, "note": note, "marked_by": by, "marked_at": datetime.now(UTC)}))
        mp.setattr(sp, "_marks", lambda pc, rid: [m for m in self.marks if m["run_id"] == rid])
        return self

    def insert(self, pc, row):
        self.runs.append({"id": len(self.runs) + 100, "guid": f"run-{len(self.runs)}", "status": "draft", "results": {},
                          "recommendation": "", "recommended": "", "created_at": datetime.now(UTC), "finished_at": None, **row})

    def set(self, pc, rid, **cols):
        r = next(x for x in self.runs if x["id"] == rid)
        r.update(cols)
        if cols.get("status") == "done":
            r["finished_at"] = datetime.now(UTC)


@pytest.fixture()
def store(monkeypatch):
    return Store().install(monkeypatch)


def _whole(pc=None, version_two=True):
    """The sample study, through the module's own functions (as the seed and the AI do)."""
    sp.start(pc, "P", WHO, "Build or buy?", "grid", confirm=True)
    for part, items in (("forces", sample.FORCES), ("uncertainties", sample.UNCERTAINTIES), ("futures", sample.FUTURES),
                        ("signposts", sample.SIGNPOSTS), ("players", sample.PLAYERS),
                        ("games", [sample._pricing(), sample._negotiation()]), ("options", sample.OPTIONS),
                        ("scores", sample._scores({"value": 2}))):
        sp.save(pc, "P", WHO, part, items, confirm=True)
    return sp.finish(pc, "P", WHO, "Buy the policy suite.", sample.BUY, confirm=True)


# ---------------------------------------------------------------- the study's rules
def test_the_migration_holds_rows_only_and_backups_carry_it():
    sql = (ROOT / "migrations" / "sql" / "0113_r10_scenario_planning.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS proj.sp_runs" in sql and "CREATE TABLE IF NOT EXISTS proj.sp_signpost_marks" in sql
    assert "UNIQUE (project_id, version)" in sql
    for word in ("CREATE TRIGGER", "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", "CREATE POLICY"):
        assert word not in sql.upper(), word                      # D248
    v = (ROOT / "migrations" / "versions" / "0113_r10_scenario_planning.py").read_text(encoding="utf-8")
    assert 'down_revision = "0112_release_8_0_0"' in v
    from eax import project_backup as pb
    names = [t[0] for t in pb.TABLES]
    assert names.index("sp_runs") < names.index("sp_signpost_marks") and "sp_runs" in pb.NEW_GUID


def test_a_change_is_a_preview_first(store):
    out = sp.start(None, "P", WHO, "Build or buy?", "grid")
    assert "preview" in out and not store.runs
    sp.start(None, "P", WHO, "Build or buy?", "grid", confirm=True)
    assert store.runs[0]["version"] == 1 and store.runs[0]["status"] == "draft"
    prev = sp.save(None, "P", WHO, "forces", sample.FORCES)
    assert "preview" in prev and store.runs[0]["forces"] == []


def test_the_whole_study_and_its_working(store):
    done = _whole()
    assert done["status"] == "done"
    r = store.runs[0]
    assert r["organisation"] == "Protea" and [s["ref"] for s in r["signposts"]] == ["SP-1", "SP-2", "SP-3", "SP-4"]
    opt = r["results"]["options"]
    assert opt["robust"] == [sample.BUY] and sample.BUY in opt["least_regret"]
    assert opt["best_in_each"] == {sample.F1: [sample.BUILD], sample.F2: [sample.BUY], sample.F3: [sample.BUILD],
                                   sample.F4: [sample.BUY]}
    assert {x["option"]: x["regret"] for x in opt["table"]} == {sample.BUILD: 6.0, sample.BUY: 2.0}
    games = {g["name"]: g for g in r["results"]["games"]}
    assert games["Digital pricing"]["stable"] == [{"Protea": "Cut price", "Rival insurer": "Cut price"}]
    assert games["Suite negotiation"]["path"][0] == f"Protea: {sample.BUY}"
    assert any("Protea" in s for s in r["results"]["players_answers"])
    ov = sp.overview(None, "P", WHO)
    assert ov["latest"]["version"] == 1 and ov["draft"] is None and ov["signposts_due"] == 4


def test_a_rerun_needs_a_finished_study(store):
    with pytest.raises(EditError, match="no finished study"):
        sp.start(None, "P", WHO, "Again", "grid", copy_latest=True, confirm=True)


def test_a_rerun_and_the_newest_shown(monkeypatch):
    s = Store().install(monkeypatch)
    _whole()
    sp.start(None, "P", WHO, "Again after the price rise", "grid", copy_latest=True, confirm=True)
    draft = next(r for r in s.runs if r["status"] == "draft")
    assert draft["version"] == 2 and draft["futures"] == s.runs[0]["futures"] and draft["organisation"] == "Protea"
    with pytest.raises(EditError, match="draft study is open"):
        sp.start(None, "P", WHO, "A third", "grid", confirm=True)
    ov = sp.overview(None, "P", WHO)
    assert ov["latest"]["version"] == 1 and ov["draft"]["version"] == 2 and [v["version"] for v in ov["versions"]] == [2, 1]
    sp.finish(None, "P", WHO, "Still buy.", sample.BUY, confirm=True)
    assert sp.overview(None, "P", WHO)["latest"]["version"] == 2
    assert sp.get_run(None, "P", WHO, "v1")["version"] == 1
    with pytest.raises(EditError, match="no scenario planning version 9"):
        sp.get_run(None, "P", WHO, 9)


def test_finish_needs_what_the_template_asks(store):
    sp.start(None, "P", WHO, "Build or buy?", "grid", confirm=True)
    sp.save(None, "P", WHO, "uncertainties", sample.UNCERTAINTIES[:1], confirm=True)
    with pytest.raises(EditError, match="2 critical uncertainties .there are 1.*4 futures"):
        sp.finish(None, "P", WHO, "Buy", confirm=True)
    sp.discard(None, "P", WHO, confirm=True)
    assert store.runs == []
    sp.start(None, "P", WHO, "Who moves?", "games", confirm=True)
    sp.save(None, "P", WHO, "players", sample.PLAYERS, confirm=True)
    with pytest.raises(EditError, match="at least one game"):
        sp.finish(None, "P", WHO, "Watch the rival", confirm=True)
    sp.save(None, "P", WHO, "games", [sample._pricing()], confirm=True)
    assert sp.finish(None, "P", WHO, "Watch the rival", confirm=True)["status"] == "done"


def test_each_part_is_checked_against_the_others(store):
    sp.start(None, "P", WHO, "Build or buy?", "grid", confirm=True)
    with pytest.raises(EditError, match="impact is 1 to 5"):
        sp.save(None, "P", WHO, "forces", [{"name": "X", "kind": "economic", "impact": 9, "uncertainty": 1}])
    with pytest.raises(EditError, match="kind is one of"):
        sp.save(None, "P", WHO, "forces", [{"name": "X", "kind": "astrology", "impact": 1, "uncertainty": 1}])
    with pytest.raises(EditError, match="not one of the uncertainties saved"):
        sp.save(None, "P", WHO, "futures", sample.FUTURES)
    sp.save(None, "P", WHO, "uncertainties", sample.UNCERTAINTIES, confirm=True)
    with pytest.raises(EditError, match="not in the project"):
        sp.save(None, "P", WHO, "futures", [dict(sample.FUTURES[0], model="No such model")])
    with pytest.raises(EditError, match="one of the futures saved"):
        sp.save(None, "P", WHO, "signposts", sample.SIGNPOSTS)
    with pytest.raises(EditError, match="Only one player is the organisation"):
        sp.save(None, "P", WHO, "players", [{"name": "A", "kind": "organisation"}, {"name": "B", "kind": "organisation"}])
    with pytest.raises(EditError, match="not one of the players saved"):
        sp.save(None, "P", WHO, "games", [sample._pricing()])
    sp.save(None, "P", WHO, "players", sample.PLAYERS, confirm=True)
    bad = sample._pricing()
    bad["payoffs"] = bad["payoffs"][:2]
    with pytest.raises(EditError, match="Digital pricing: .*no values"):
        sp.save(None, "P", WHO, "games", [bad])
    with pytest.raises(EditError, match="Two forces are called"):
        sp.save(None, "P", WHO, "forces", [sample.FORCES[0], sample.FORCES[0]])
    with pytest.raises(EditError, match="A part is one of"):
        sp.save(None, "P", WHO, "horoscopes", [])
    sp.save(None, "P", WHO, "futures", sample.FUTURES, confirm=True)
    sp.save(None, "P", WHO, "options", sample.OPTIONS, confirm=True)
    with pytest.raises(EditError, match="score the person agreed"):
        sp.save(None, "P", WHO, "scores", [{"option": sample.BUY, "future": sample.F1, "value": {"words": "better"}}])
    with pytest.raises(EditError, match="one of the options saved"):
        sp.save(None, "P", WHO, "scores", [{"option": "Lease", "future": sample.F1, "value": 1}])


def test_signposts_marked_at_a_review_and_due_again_after_90_days(store):
    _whole()
    with pytest.raises(EditError, match="not one of the signposts"):
        sp.mark_signposts(None, "P", WHO, [{"signpost": "SP-9", "seen": True}])
    with pytest.raises(EditError, match="seen is true or false"):
        sp.mark_signposts(None, "P", WHO, [{"signpost": "SP-1", "seen": "yes"}])
    out = sp.mark_signposts(None, "P", WHO, [{"signpost": "sp-1", "seen": True, "note": "draft rules out"}], confirm=True)
    assert out["seen"] == ["SP-1"]
    due = {s["ref"]: s for s in sp.overview(None, "P", WHO)["signposts"]}
    assert not due["SP-1"]["due"] and due["SP-1"]["last"]["seen"] and due["SP-2"]["due"]
    store.marks[0]["marked_at"] = datetime.now(UTC) - timedelta(days=91)
    assert sp.overview(None, "P", WHO)["signposts_due"] == 4


def test_the_report_section(store):
    assert sp.report_section(None, {"id": 7}) is None
    _whole()
    sec = sp.report_section(None, {"id": 7})
    assert sec["version"] == 1 and sec["recommended"] == sample.BUY and sec["signposts_due"] == 4
    assert any("robust" in x for x in sec["options"]) and len(sec["futures"]) == 4


def test_templates_are_offered_for_the_person_to_pick():
    keys = [t["key"] for t in sp.templates()]
    assert keys == ["grid", "range", "single", "games"]
    assert len(sp.STEPS) == 9


# ---------------------------------------------------------------- the MCP tools, as an AI calls them
def _mcp_module():
    try:
        importlib.import_module("eax.mcp_server")
    except Exception:  # noqa: BLE001 - the real server's library may not load here; the tools are plain functions
        fake = types.ModuleType("eax.mcp_server")
        fake.mcp = types.SimpleNamespace(tool=lambda *a, **k: (lambda f: f), prompt=lambda *a, **k: (lambda f: f))
        fake._clean = lambda x: x
        sys.modules["eax.mcp_server"] = fake
    for m in ("eax.mcp_scenarios", "eax.mcp_scenario_planning"):
        sys.modules.pop(m, None)
    return importlib.import_module("eax.mcp_scenario_planning")


@pytest.fixture()
def ai(monkeypatch, store):
    """The MCP tools with the projects' connection, the preview tokens and the audit stood in for."""
    tools = _mcp_module()
    from eax import audit
    from eax import mcp_scenarios as ms
    from eax import projects as pj
    from eax import settings as app_settings
    monkeypatch.setattr(pj, "connections", lambda write=False: contextlib.nullcontext(types.SimpleNamespace()))
    monkeypatch.setattr(pj, "core", lambda pc: pc)
    monkeypatch.setattr(app_settings, "parts", lambda: {"projects": True})
    monkeypatch.setattr(audit, "record", lambda *a, **k: None)
    monkeypatch.setattr(ms, "_may_write", lambda: None)
    kept: dict[str, tuple] = {}

    def keep(core, user, tool, args, summary):
        t = f"pv_{len(kept) + 1}"
        kept[t] = (user.username, tool, ms._hash(tool, args))
        return t

    def use(core, user, tool, args, token):
        if kept.pop(token, None) != (user.username, tool, ms._hash(tool, args)):
            raise EditError("That confirm token is not for this call.")
    monkeypatch.setattr(ms, "_token_new", keep)
    monkeypatch.setattr(ms, "_token_use", use)
    tok = perms.current.set(WHO)
    yield tools
    perms.current.reset(tok)


def _run(coro):
    return asyncio.run(coro)


def test_the_mcp_tools_are_registered_with_the_prompt():
    src = (ROOT / "eax" / "mcp_scenario_planning.py").read_text(encoding="utf-8")
    tools = set(re.findall(r"@mcp\.tool\(\)\nasync def (\w+)", src))
    assert tools == {"how_to_run_scenario_planning", "sp_templates", "sp_overview", "sp_version", "sp_work_out", "sp_start",
                     "sp_save", "sp_finish", "sp_discard", "sp_mark_signposts"}
    for t in ("sp_start", "sp_save", "sp_finish", "sp_discard", "sp_mark_signposts"):
        body = src.split(f"async def {t}(")[1].split("@mcp.tool()")[0]
        assert "write=True" in body and "confirm=confirm" in body, t
    assert "def scenario_planning_wizard(" in src
    server = (ROOT / "eax" / "mcp_server.py").read_text(encoding="utf-8")
    assert re.search(r"from \. import \(.*?\bmcp_scenario_planning\b", server, re.S)
    from eax import mcp_catalogue
    assert mcp_catalogue.AREAS["mcp_scenario_planning"] == "Futures, players and games"
    names = {t["name"] for t in mcp_catalogue.tools()}
    assert tools <= names


def test_the_ai_runs_the_wizard_preview_then_confirm(ai, store):
    assert "sp_save" in _run(ai.how_to_run_scenario_planning())["guide"]
    assert [t["key"] for t in _run(ai.sp_templates())["templates"]][0] == "grid"
    pv = _run(ai.sp_start("Protea", "Build or buy?", "grid"))
    assert pv["confirm"].startswith("pv_") and "preview" in pv and not store.runs
    bad = _run(ai.sp_start("Protea", "Build or buy, changed?", "grid", confirm=pv["confirm"]))
    assert "error" in bad and not store.runs                       # the token is bound to the arguments
    pv = _run(ai.sp_start("Protea", "Build or buy?", "grid"))
    done = _run(ai.sp_start("Protea", "Build or buy?", "grid", confirm=pv["confirm"]))
    assert done["version"] == 1 and store.runs[0]["status"] == "draft"
    again = _run(ai.sp_start("Protea", "Build or buy?", "grid", confirm=pv["confirm"]))
    assert "error" in again                                         # a token is used once
    for part, items in (("forces", sample.FORCES), ("uncertainties", sample.UNCERTAINTIES), ("futures", sample.FUTURES),
                        ("signposts", sample.SIGNPOSTS), ("players", sample.PLAYERS),
                        ("games", [sample._pricing(), sample._negotiation()]), ("options", sample.OPTIONS),
                        ("scores", sample._scores({"value": 2}))):
        pv = _run(ai.sp_save("Protea", part, items))
        assert "confirm" in pv, (part, pv)
        if part == "games":
            assert pv["preview"]["working"][0]["stable"]          # the working is shown before the yes
        ok = _run(ai.sp_save("Protea", part, items, confirm=pv["confirm"]))
        assert ok["saved"] == part, ok
    w = _run(ai.sp_work_out("Protea"))
    assert w["still_needed"] == [] and w["working"]["options"]["robust"] == [sample.BUY]
    pv = _run(ai.sp_finish("Protea", "Buy the policy suite.", sample.BUY))
    assert _run(ai.sp_finish("Protea", "Buy the policy suite.", sample.BUY, confirm=pv["confirm"]))["status"] == "done"
    ov = _run(ai.sp_overview("Protea"))
    assert ov["latest"]["recommended"] == sample.BUY and ov["signposts_due"] == 4
    assert _run(ai.sp_version("Protea", 1))["version"] == 1
    pv = _run(ai.sp_mark_signposts("Protea", [{"signpost": "SP-1", "seen": True}]))
    assert _run(ai.sp_mark_signposts("Protea", [{"signpost": "SP-1", "seen": True}], confirm=pv["confirm"]))["seen"] == ["SP-1"]


def test_the_ai_is_told_in_words_what_is_wrong(ai, store):
    assert "error" in _run(ai.sp_save("Protea", "forces", sample.FORCES))           # no draft yet
    assert "error" in _run(ai.sp_overview("Protea")) or _run(ai.sp_overview("Protea"))["latest"] is None
    assert "error" in _run(ai.sp_work_out("Protea"))
    assert "error" in _run(ai.sp_start("Protea", "", "grid"))
    assert "error" in _run(ai.sp_start("Protea", "Q", "tarot"))
    pv = _run(ai.sp_start("Protea", "Q", "grid"))
    _run(ai.sp_start("Protea", "Q", "grid", confirm=pv["confirm"]))
    assert "still needs" in _run(ai.sp_finish("Protea", "Buy"))["error"]
    pv = _run(ai.sp_discard("Protea"))
    _run(ai.sp_discard("Protea", confirm=pv["confirm"]))
    assert store.runs == []


def test_the_ai_must_be_signed_in(ai):
    tok = perms.current.set(None)
    try:
        assert _run(ai.sp_overview("Protea")) == {"error": "Sign in required."}
    finally:
        perms.current.reset(tok)


# ---------------------------------------------------------------- the screens, the API, the sample, the help
def test_the_tab_api_report_sample_and_help_are_wired():
    api = (ROOT / "eax" / "api" / "scenarios.py").read_text(encoding="utf-8")
    assert "/projects/<string:project>/scenario-planning\")" in api and "/scenario-planning/<string:version>" in api
    assert 'out["scenario_planning"] = spl.count(conn, p)' in (ROOT / "eax" / "projects.py").read_text(encoding="utf-8")
    web = REPO / "services" / "web" / "src"
    projects = (web / "Projects.jsx").read_text(encoding="utf-8")
    assert '["planning", "Scenario planning"]' in projects and 'p.scenario_planning > 0' in projects
    tab = (web / "ScenarioPlanning.jsx").read_text(encoding="utf-8")
    assert "Read only" in tab and "<button" not in tab                   # D818: no screen changes any of it
    assert "PlanningSummary" in (web / "ProjectTabs.jsx").read_text(encoding="utf-8")
    import json
    cat = json.loads((web / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "tab:Scenario planning" in cat
    later = (ROOT / "eax" / "seed" / "later.py").read_text(encoding="utf-8")
    assert later.index("sample_scenarios)") < later.index("sample_planning)")
    assert '"scenario_planning"' in (ROOT / "eax" / "deck.py").read_text(encoding="utf-8")
