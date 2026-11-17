"""R5.7-J1, customer journey maps as first-class citizens (owner, 16 Nov 2026 from 15:58, and 17 Nov 13:50; D730): in a
project beside the Business Model Canvas, in tables of their own; stages and parts (steps with the emotion from -2 to
+2, touchpoints, pain points, moments that matter, opportunities, personas, and kinds of the project's own with
fields); links to model elements; versions like the canvas (kinds, lineage, compare, draft or agreed, every change
kept); PDF, PowerPoint and draw.io; MCP tools; a sample journey and a starter template. The database checks run on
EAX_MIGRATED_TEST_DSN, rolled back."""
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest

from eax import journeys as jy
from eax import project_backup as pb
from eax.metamodel_edit import EditError

API = Path(__file__).resolve().parents[1]
WEB = API.parent / "web" / "src"
DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")


# ---------------------------------------------------------------- what a journey is made of
def test_the_parts_the_faces_and_the_starter():
    assert jy.PART_CODES == ["step", "touchpoint", "pain_point", "moment", "opportunity"]
    assert sorted(jy.FACES) == [-2, -1, 0, 1, 2]                    # -2 to +2 with faces (owner, 17 Nov 13:50)
    assert set(jy.KINDS) == {"current", "target", "working", "scenario"} and set(jy.STATUSES) == {"draft", "agreed"}
    assert len(jy.STARTER) >= 5 and set(jy.TEMPLATES) == {"blank", "starter"}
    for bad in (3, -3, "x", 1.5):
        with pytest.raises(EditError):
            jy._score(bad)
    assert jy._score("2") == 2 and jy._score(None) is None and jy._score(0) == 0


def _j(stages):
    """A journey as get() gives it: [(stage name, lineage, {part: [(text, lineage, score)]})]."""
    out = []
    for n, (name, lin, parts) in enumerate(stages):
        out.append({"id": f"s{n}{name}", "name": name, "lineage": lin, "note": "", "links": [],
                    "parts": {c: [{"id": f"{name}{c}{k}", "text": t, "lineage": li, "score": sc, "note": "", "fields": {}, "sort_order": k}
                                  for k, (t, li, sc) in enumerate(parts.get(c, []))] for c in jy.PART_CODES}})
    return {"stages": out, "personas": []}


def test_two_journeys_compare_stage_by_stage_and_part_by_part():
    a = _j([("Report", "S1", {"step": [("Phone the call centre", "I1", -1), ("Fill in a paper form", "I2", -2)]}),
            ("Assess", "S2", {"pain_point": [("Nobody calls back", "I3", None)]}),
            ("Branch visit", "S3", {"step": [("Queue at the branch", "I4", -2)]})])
    b = _j([("Report a claim", "S1", {"step": [("Phone the call centre", "I1", 1), ("Claim in the app with photos", "I9", 2)]}),
            ("Assess", "S2", {"pain_point": [("Nobody calls back", "other", None)]}),
            ("Track", "S4", {"step": [("See the claim's status", "I8", 1)]})])
    d = jy.diff(a, b)
    by = {s["name"]: s for s in d["stages"]}
    assert by["Report a claim"]["state"] == "changed" and by["Report a claim"]["was_name"] == "Report"
    assert by["Track"]["state"] == "added" and by["Branch visit"]["state"] == "removed"
    steps = {r["text"]: r for r in by["Report a claim"]["parts"]["step"]}
    assert steps["Phone the call centre"]["state"] == "changed" and steps["Phone the call centre"]["was_score"] == -1
    assert steps["Claim in the app with photos"]["state"] == "added"
    assert steps["Fill in a paper form"]["state"] == "removed"
    assert by["Assess"]["parts"]["pain_point"][0]["state"] == "same"        # matched by its text
    assert all(r["state"] == "removed" for r in by["Branch visit"]["parts"]["step"])
    assert d["counts"]["added"] == 2 and d["counts"]["removed"] == 2 and d["counts"]["changed"] == 1


def _view():
    v = {"title": "Make a motor claim <today>", "subtitle": "Current state · Agreed", "persona": "Thandi",
         "labels": {c: lb for c, lb, _h in jy.PARTS}, "parts": list(jy.PART_CODES),
         "personas": [{"text": "Thandi, policyholder", "state": "same", "was_text": ""}], "stages": []}
    for name, steps in (("Report", [("Phone & wait", -2, "same", ""), ("Fill in a form", -1, "changed", "Post a form")]),
                        ("Settle", [("Paid", 1, "added", "")])):
        v["stages"].append({"name": name, "was_name": "", "state": "same", "note": "",
                            "links": [{"entity_type": "Capability", "name": "Claims Management", "state": "same"}],
                            "parts": {"step": [{"text": t, "score": sc, "state": st, "was_text": w, "note": ""} for t, sc, st, w in steps],
                                      "pain_point": [{"text": "Long waits", "score": None, "state": "removed", "was_text": "", "note": ""}]}})
    return v


def test_exports_are_files_with_the_emotion_curve():
    assert jy._pdf(_view()).startswith(b"%PDF")
    z = zipfile.ZipFile(io.BytesIO(jy._pptx(_view())))
    slide = z.read("ppt/slides/slide1.xml").decode()
    assert "Phone &amp; wait" in slide and "Make a motor claim &lt;today&gt;" in slide and 'strike="sngStrike"' in slide
    assert 'prst="ellipse"' in slide and "<p:cxnSp>" in slide                # the faces and the line through them
    xml = jy._drawio(_view())
    assert xml.startswith("<mxfile") and "😣" in xml and "curved=1" in xml and "dashed=1" in xml
    assert "Claims Management" in xml and "&lt;s&gt;Post a form&lt;/s&gt;" in xml


# ---------------------------------------------------------------- wired in everywhere
def test_tables_backups_api_mcp_and_tab():
    sql = (API / "migrations" / "sql" / "0101_r5_7_journeys.sql").read_text(encoding="utf-8")
    tabs = [x for x, _w, _m in pb.TABLES]
    for t in ("journeys", "journey_stages", "journey_items", "journey_links", "journey_part_kinds", "journey_documents", "journey_events"):
        assert f"CREATE TABLE IF NOT EXISTS proj.{t} " in sql
        assert t in tabs, t
    assert tabs.index("journey_documents") > tabs.index("documents")
    assert tabs.index("journey_items") > tabs.index("journey_stages") > tabs.index("journeys")
    assert "CREATE TRIGGER" not in sql and "FUNCTION" not in sql          # no logic in the database (D248)
    mcp = (API / "eax" / "mcp_build.py").read_text(encoding="utf-8")
    assert "async def customer_journey(" in mcp and "async def change_customer_journey(" in mcp
    projects = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    assert '["journeys", "Customer journeys"]' in projects
    assert projects.index('["canvas", "Business model canvas"]') < projects.index('["journeys", "Customer journeys"]')
    from eax.app import create_app
    rules = {r.rule for r in create_app().url_map.iter_rules()}
    assert {"/api/v1/projects/<string:project>/journeys", "/api/v1/projects/<string:project>/journeys/<string:jid>/<string:act>",
            "/api/v1/projects/<string:project>/journeys/<string:a>/compare/<string:b>"} <= rules


def test_the_sample_shows_current_and_target_linked_to_its_model():
    src = (API / "eax" / "seed" / "sample_journeys.py").read_text(encoding="utf-8")
    for want in ('"kind": "current"', '"kind": "target"', '"status": "agreed"', "jy.link(", '"template": "starter"', "pain_point",
                 "opportunity", "moment", "touchpoint", "persona"):
        assert want in src, want
    assert "sample_journeys" in (API / "eax" / "seed" / "later.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- on a real database
needs_db = pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")


@pytest.fixture
def db():
    from sqlalchemy import create_engine, text

    from eax import permissions as perms
    eng = create_engine(DSN)
    with eng.connect() as c:
        tx = c.begin()
        try:
            pid = c.execute(text("""INSERT INTO proj.projects (name, purpose, created_by) VALUES ('Journey test', 'test', 'tester')
                                    RETURNING guid::text""")).scalar()
            model = c.execute(text("SELECT m.guid::text FROM core.models m JOIN core.entities e ON e.model_id = m.id LIMIT 1")).scalar()
            if model:
                c.execute(text("""INSERT INTO proj.project_models (project_id, model_guid, how, added_by)
                                  SELECT id, CAST(:m AS uuid), 'added', 'tester' FROM proj.projects WHERE guid::text = :p"""), {"m": model, "p": pid})
            yield c, pid, perms.Principal("tester", ("super-admin",)), perms.Principal("nobody", ("user",))
        finally:
            tx.rollback()


@needs_db
def test_a_journey_from_the_starter_with_parts_emotions_and_history(db):
    c, pid, su, _nobody = db
    j = jy.create(c, pid, su, {"name": "Make a motor claim", "kind": "current", "template": "starter", "persona": "Thandi"})["id"]
    g = jy.get(c, pid, su, j)
    assert [s["name"] for s in g["stages"]] == [s for s, _n in jy.STARTER]
    s1 = g["stages"][0]["id"]
    step = jy.add_item(c, pid, su, j, {"stage": s1, "part": "step", "text": "Sees an advert", "score": 1})["id"]
    jy.add_item(c, pid, su, j, {"stage": s1, "part": "pain_point", "text": "Too much jargon", "score": 2})   # no emotion on a pain point
    jy.add_item(c, pid, su, j, {"part": "persona", "text": "Thandi, a policyholder"})
    with pytest.raises(EditError):
        jy.add_item(c, pid, su, j, {"stage": s1, "part": "step", "text": "x", "score": 5})
    with pytest.raises(EditError):
        jy.add_item(c, pid, su, j, {"stage": s1, "part": "nonsense", "text": "x"})
    g = jy.get(c, pid, su, j)
    assert g["curve"] == [{"stage": s1, "step": step, "text": "Sees an advert", "score": 1}]
    assert g["stages"][0]["parts"]["pain_point"][0]["score"] is None
    assert g["personas"][0]["text"] == "Thandi, a policyholder"
    jy.change(c, pid, su, j, {"status": "agreed"})
    msg = jy.change_item(c, pid, su, step, {"score": -2})["message"]
    assert "draft again" in msg and jy.get(c, pid, su, j)["status"] == "draft"     # a change to an agreed one
    assert [h["action"] for h in jy.get(c, pid, su, j)["history"]][:2] == ["made", "part added"]


@needs_db
def test_own_kinds_of_part_with_fields(db):
    c, pid, su, _nobody = db
    k = jy.set_part_kind(c, pid, su, {"label": "Systems used", "fields": ["Owner", "Channel"]})["code"]
    assert k == "x-systems-used"
    jy.set_part_kind(c, pid, su, {"code": "pain_point", "fields": ["Severity"]})
    j = jy.create(c, pid, su, {"name": "J", "template": "blank"})["id"]
    s = jy.add_stage(c, pid, su, j, {"name": "Report"})["id"]
    i = jy.add_item(c, pid, su, j, {"stage": s, "part": k, "text": "Claims system", "fields": {"Owner": "Claims IT"}})["id"]
    jy.add_item(c, pid, su, j, {"stage": s, "part": "pain_point", "text": "Lost forms", "fields": {"Severity": "High"}})
    with pytest.raises(EditError):
        jy.add_item(c, pid, su, j, {"stage": s, "part": k, "text": "x", "fields": {"Colour": "red"}})
    g = jy.get(c, pid, su, j)
    assert g["stages"][0]["parts"][k][0]["fields"] == {"Owner": "Claims IT"}
    assert g["stages"][0]["parts"]["pain_point"][0]["fields"] == {"Severity": "High"}
    with pytest.raises(EditError):
        jy.remove_part_kind(c, pid, su, k)                                  # in use
    jy.remove_item(c, pid, su, i)
    jy.remove_part_kind(c, pid, su, k)


@needs_db
def test_copies_keep_lineage_and_compare(db):
    c, pid, su, _nobody = db
    a = jy.create(c, pid, su, {"name": "Today", "template": "blank"})["id"]
    s = jy.add_stage(c, pid, su, a, {"name": "Report"})["id"]
    jy.add_item(c, pid, su, a, {"stage": s, "part": "step", "text": "Phone", "score": -1})
    b = jy.copy(c, pid, su, a, {"name": "Tomorrow", "kind": "target"})["id"]
    bs = jy.get(c, pid, su, b)["stages"][0]
    jy.change_item(c, pid, su, bs["parts"]["step"][0]["id"], {"text": "Claim in the app", "score": 2})
    jy.add_stage(c, pid, su, b, {"name": "Track"})
    d = jy.compare(c, pid, su, a, b)
    assert d["counts"]["changed"] == 1
    st = {x["name"]: x for x in d["stages"]}
    assert st["Track"]["state"] == "added"
    r = st["Report"]["parts"]["step"][0]
    assert (r["was_text"], r["was_score"], r["score"]) == ("Phone", -1, 2)
    for fmt in ("pdf", "pptx", "drawio"):
        data, name, _ct = jy.export(c, pid, su, a, fmt, b)
        assert data and name.endswith(fmt)


@needs_db
def test_links_to_the_projects_model_elements(db):
    c, pid, su, _nobody = db
    j = jy.create(c, pid, su, {"name": "Linked", "template": "starter"})["id"]
    s = jy.get(c, pid, su, j)["stages"][0]["id"]
    found = jy.elements(c, pid, su, "", ["all"])["elements"]
    if not found:
        pytest.skip("no model with elements in this database")
    e = found[0]
    jy.link(c, pid, su, j, {"stage": s, "entity": e["entity"]})
    assert "already" in jy.link(c, pid, su, j, {"stage": s, "entity": e["entity"]})["message"]
    links = jy.get(c, pid, su, j)["stages"][0]["links"]
    assert [x["name"] for x in links] == [e["name"]]
    with pytest.raises(EditError):
        jy.link(c, pid, su, j, {"stage": s, "entity": "00000000-0000-0000-0000-000000000000"})
    jy.unlink(c, pid, su, links[0]["id"])
    assert not jy.get(c, pid, su, j)["stages"][0]["links"]


@needs_db
def test_only_people_on_the_project_read_and_contributors_change(db):
    c, pid, su, nobody = db
    jy.create(c, pid, su, {"name": "Private", "template": "blank"})
    with pytest.raises(EditError):
        jy.listing(c, pid, nobody)
    with pytest.raises(EditError):
        jy.create(c, pid, nobody, {"name": "Mine"})

