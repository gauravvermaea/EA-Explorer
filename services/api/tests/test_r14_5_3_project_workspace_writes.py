"""Release 14.5, batch 1 (owner, 25 Nov 2026, 12:12: "Please build both API and screens"): the project workspace's writes
in the self-test's API suite (eax/testing/api_writes.project_workspace). Each area is made, changed, read back and removed
inside the run's own project, as its Architect; removals as the Super Admin; the same write refused for the Report Viewer,
the project's Stakeholder. These tests hold the plan to the API's own routes, so a step cannot call a path that is not
there, use an id no earlier step made, or leave behind what it made."""

import ast
import json
import re
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax.testing import api_writes  # noqa: E402

P = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SID = "e4fa1d33dfd8"
TAG = f"self_test_{SID}"
STEPS = api_writes.project_workspace(P, TAG)


def _routes() -> list[tuple[re.Pattern, set[str]]]:
    """Every route of the API (/api/v1 + the route), as a pattern, with the methods its class answers."""
    out = []
    files = sorted((API / "eax/api").glob("*.py"))
    # each file's blueprints and their prefixes (a route on a blueprint from another file, such as grids.py's
    # personal_blp from personal.py, takes that blueprint's prefix)
    own: dict[str, dict[str, str]] = {}
    for f in files:
        own[f.stem] = {n: px for n, px in re.findall(r'^(\w+) = (?:Flask)?Blueprint\([^)]*?url_prefix="([^"]+)"',
                                                     f.read_text(encoding="utf-8"), re.M | re.S)}
    for f in files:
        src = f.read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = dict(own[f.stem])
        for mod, name, alias in re.findall(r"^from \.(\w+) import (\w+) as (\w+)", src, re.M):
            if name in own.get(mod, {}):
                names[alias] = own[mod][name]
        first = re.search(r'url_prefix="([^"]+)"', src)
        default = first.group(1) if first else "/api/v1"
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for d in node.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "route" and d.args \
                        and isinstance(d.args[0], ast.Constant):
                    prefix = names.get(getattr(d.func.value, "id", ""), default)
                    pat = re.sub(r"<(?:[a-z]+(?:\([^)]*\))?:)?([a-z_]+)>", "[^/]+", re.escape(prefix + d.args[0].value)
                                 .replace(r"\<", "<").replace(r"\>", ">").replace(r"\(", "(").replace(r"\)", ")")
                                 .replace(r"\ ", " ").replace(r"\,", ","))
                    methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                    out.append((re.compile(f"^{pat}$"), methods))
    return out


ROUTES = _routes()


def test_every_step_calls_a_route_that_is_there_with_its_method():
    for s in STEPS:
        path = re.sub(r"\{[a-z0-9_]+\}", "x-id", s["path"].split("?", 1)[0])
        assert any(r.match(path) and s["method"] in m for r, m in ROUTES), f"no {s['method'].upper()} {s['path']}"


def test_every_id_a_step_uses_is_made_by_an_earlier_step():
    made: set[str] = set()
    for s in STEPS:
        for name in re.findall(r"\{([a-z0-9_]+)\}", json.dumps([s["path"], s.get("body")])):
            assert name in made, f"{s['what']}: {{{name}}} is made by no earlier step"
        if s.get("save"):
            made.add(s["save"])


def test_what_is_made_is_removed_again():
    """Every thing a step makes is deleted by a later step (background tasks aside: they end by themselves)."""
    for s in STEPS:
        key = s.get("save")
        if not key or s.get("save_at") == "task":
            continue
        assert any(t["method"] == "delete" and "{" + key + "}" in t["path"] for t in STEPS), f"{key} is never removed"
    for kind in ("task-statuses", "principle-areas"):            # the two made and removed by name
        assert sum(1 for t in STEPS if kind in t["path"]) == 2


def test_each_area_is_done_by_the_architect_removed_by_the_super_admin_and_refused_for_the_stakeholder():
    areas = {s["area"] for s in STEPS}
    assert len(areas) == 12
    for a in areas:
        mine = [s for s in STEPS if s["area"] == a]
        assert any(s["who"] == "architect" and not s.get("refused") for s in mine), a
        refused = [s for s in mine if s.get("refused")]
        assert len(refused) == 1 and refused[0]["who"] == "report-viewer" and refused[0]["method"] == "post", a
    assert all(s["who"] == "super-admin" for s in STEPS if s["method"] == "delete")


def test_the_background_work_is_followed_to_its_end():
    bg = [s for s in STEPS if s.get("save_at") == "task"]
    assert {s["what"] for s in bg} == {"bring the repository back to the tag (in the background)",
                                       "the documents' zip (in the background)"}
    for s in bg:
        assert s["until"]["path"] == "/api/v1/tasks/{" + s["save"] + "}" and s["until"]["status"] == ["done"]


def test_everything_named_is_the_runs_own_and_inside_its_project():
    for s in STEPS:
        for u in re.findall(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", json.dumps([s["path"], s.get("body")])):
            assert u == P, s
        body = s.get("body") or {}
        for k in ("name", "title", "topic", "question"):
            if isinstance(body.get(k), str):
                assert body[k].startswith(TAG), s


def test_the_plan_runs_them_with_the_project():
    plan = api_writes.plan({"project": P, "sid": SID}, SID)
    whats = [f"{w['area']}: {w['what']}" for w in plan]
    assert "project key questions: the Stakeholder accepts the answer" in whats
    assert not any(w["area"].startswith("project ") for w in api_writes.plan({"sid": SID}, SID))   # no project: none


def test_a_numbered_id_is_kept():
    """A principle's id is a number: kept as text for the steps after it."""
    assert api_writes.ident({"id": 42, "message": "x"}) == "42"
    assert api_writes.ident({"id": True}) is None
    assert api_writes.ident({"id": "g-1"}) == "g-1"
