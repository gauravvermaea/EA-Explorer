"""Release 4's features (R4.19 to R4.22, R4.8 to R4.12): what each must do, tested."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WEB = REPO / "services" / "web" / "src"


# ---------------------------------------------------------------- R4.20 the AI (MCP) menu
def test_r4_20_ai_is_a_top_level_menu_for_everyone():
    """Owner, 14 Nov 2026: "move mcp server as a top level menu and available to all users"."""
    menu = (WEB / "menu.js").read_text(encoding="utf-8")
    area = menu[menu.index('{ key: "ai", label: "AI (MCP)"'):menu.index('{ key: "system"')]
    assert "ok:" not in area.split("items:", 1)[0]                                   # the area itself: everyone
    for label, href in (("Connect your AI assistant", "#/mcp"), ("What it can do", "#/mcp/tools"),
                        ("My AI activity", "#/mcp/activity?who=me"), ("Everyone's AI activity", "#/mcp/activity")):
        assert f'label: "{label}", href: "{href}"' in area, label
    assert '"Everyone\'s AI activity", href: "#/mcp/activity", ok: () => ops() || sup()' in area
    assert 'serviceOn("mcp") ? [' in area and "Switched off in this installation" in area   # off: said, with where
    # the two old, hidden entries are gone
    assert "Connect your AI assistant (MCP)" not in menu and "AI activity (MCP)" not in menu
    assert 'if (r.startsWith("#/mcp")) return "ai";' in menu


def test_r4_20_my_ai_activity_opens_as_mine():
    page = (WEB / "Mcp.jsx").read_text(encoding="utf-8")
    assert '.get("who") || ""' in page and "<h1>AI (MCP)</h1>" in page
    assert '!serviceOn("mcp") && <p className="status warn">MCP is switched off' in page


def test_r4_20_my_ai_activity_is_my_own_even_for_an_admin():
    from eax import mcp_activity as ma
    seen = {}

    class Conn:
        def execute(self, sql, p=None):
            seen.setdefault("sql", []).append((str(sql), dict(p or {})))

            class R:
                def mappings(self):
                    return self

                def all(self):
                    return []

                def scalar(self):
                    return 0
            return R()

    class U:
        username, roles = "Thandi", ["super-admin"]
    try:
        ma.listing(Conn(), U(), "me")
    except Exception:  # noqa: BLE001 - only the filter is checked here
        pass
    first = seen["sql"][0]
    assert first[1].get("w") == "thandi" or "thandi" in first[1].values(), first


# ---------------------------------------------------------------- R4.21 the order of the ADM steps
def test_r4_21_where_a_step_goes():
    """Checked on PostgreSQL on 14 Nov 2026 (a project's phase RM of 10 steps): the third moved up became the second, the
    first put after the third became the second, a new step put first became step 1 of 11, the move recorded on the
    step ("moved", "to place 2 of 10 in phase RM"), and the steps listed in their new order."""
    import pytest

    from eax.metamodel_edit import EditError
    from eax.projects import placed
    ids = [10, 11, 12, 13]
    assert placed(ids, 12, "up") == [10, 12, 11, 13] and placed(ids, 10, "up") == ids
    assert placed(ids, 11, "down") == [10, 12, 11, 13] and placed(ids, 13, "down") == ids
    assert placed(ids, 13, "start") == [13, 10, 11, 12] and placed(ids, 10, "end") == [11, 12, 13, 10]
    assert placed(ids, 10, 12) == [11, 12, 10, 13] and placed(ids, 13, "11") == [10, 11, 13, 12]
    assert placed(ids, 99, "start") == [99, 10, 11, 12, 13]                          # a new step: where it goes
    with pytest.raises(EditError):
        placed(ids, 10, 77)                                                            # not in this phase
    with pytest.raises(EditError):
        placed(ids, 10, "sideways")


def test_r4_21_wired_from_screen_to_database():
    api = (REPO / "services/api/eax/api/projects.py").read_text()
    assert '@blp.route("/projects/<string:project>/steps/<int:step>/move")' in api
    pj = (REPO / "services/api/eax/projects.py").read_text()
    assert "_iter.guard(conn, p, s[\"phase\"])" in pj.split("def move_step", 1)[1].split("def order_from_wizard", 1)[0]
    assert '_step_event(conn, step_id, user, "moved"' in pj
    assert "coalesce((SELECT t.seq FROM proj.steps t WHERE t.id = proj.steps.parent_step_id), seq)" in pj   # listed in order
    assert "order_from_wizard(conn, p, d.get(\"step_order\") or {}, own)" in pj
    sql = (REPO / "services/api/migrations/sql/0076_step_moved.sql").read_text()
    assert "CHECK (action IN ('opened', 'closed', 'reopened', 'moved'))" in sql
    web = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    assert "steps/${st.id}/move`, { to }" in web and 'Field label="Where it goes"' in web
    assert "step_order: editId ? undefined : orderToSend(d)" in web
    mcp = (REPO / "services/api/eax/mcp_build.py").read_text()
    assert "async def move_project_step(project: str, step: int, to: str)" in mcp and 'where: str = ""' in mcp


def test_r4_21_the_wizards_order_with_node():
    import json
    import shutil
    import subprocess

    import pytest
    node = shutil.which("node")
    if not node:
        pytest.skip("no node here")
    src = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    body = src[src.index("export function stepOrder"):src.index("function KindBtn")]
    js = body.replace("export function", "function") + """
const d = { step_order: { B: ["O1", "L5", "L4"] }, own_steps: [{ phase: "B", name: "" }, { phase: "B", name: "Mine" }] };
console.log(JSON.stringify([stepOrder(d, [{ id: 4 }, { id: 5 }], d.own_steps.filter((s) => s.phase === "B"), "B"),
  moved(["a", "b", "c"], 2, -1), moved(["a", "b"], 0, -1), orderToSend(d)]));"""
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got[0] == ["O1", "L5", "L4", "O0"] and got[1] == ["a", "c", "b"] and got[2] == ["a", "b"]
    assert got[3] == {"B": ["O0", "L5", "L4"]}                                       # the unnamed own step is not made
