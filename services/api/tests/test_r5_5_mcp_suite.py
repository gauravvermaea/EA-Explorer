"""The MCP suite of the self-test (owner, 16 Nov 2026, 12:45: "add a story for MCP test, where MCP api is tested";
12:58: "It should go now, its just test using api, not really with a LLM"): the MCP server called over HTTP as an AI
client calls it. Here: it is a suite everywhere, it reads answers right, fills arguments from the run's data, and a
fake installation passes it end to end (it ran against the real API and MCP servers on a migrated database: 83
passed, 8 skipped for want of a project)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]


def test_it_is_a_suite_everywhere_and_part_of_the_full_test():
    from eax import testing
    assert "mcp" in testing.SUITES and "mcp" in testing.FULL_SUITES and "mcp" in testing.WEB_FULL_SUITES
    assert '"mcp", "security"' in (REPO / "services/ops/testruns.py").read_text()
    assert '"mcp", "security"' in (REPO / "services/web/src/selfTestDriver.js").read_text()
    assert '["mcp", "MCP",' in (REPO / "services/web/src/TestRuns.jsx").read_text()
    run = (API / "eax/testing/run.py").read_text()
    assert run.count("mcp_check.run(") == 2 and "fixtures.read_only_mcp_token(repo, run, by)" in run
    from eax.testing import store
    assert store.PHASE_NAMES["mcp"] == "MCP"
    assert "mcp" in (REPO / "eaxcli/help.txt").read_text().split("### test [")[1].split("]")[0]


def test_answers_are_judged_as_ok_refused_or_crashed():
    from eax.testing import mcp_check as mc
    ok = {"result": {"content": [{"type": "text", "text": json.dumps({"count": 0, "items": []})}]}}
    assert mc.answer(ok)[0] == "ok"
    assert mc.answer({"result": {"content": [{"type": "text", "text": '{"error": "No model x"}'}]}}) == ("refused", "No model x")
    assert mc.answer({"result": {"content": [{"type": "text", "text": "Error executing tool x"}], "isError": True}})[0] == "crashed"
    assert mc.answer({"error": {"message": "Method not found"}})[0] == "crashed" and mc.answer(None)[0] == "crashed"


def test_arguments_come_from_the_runs_data():
    from eax.testing import mcp_check as mc
    ids = {"model": "m1", "other_model": "m2", "entity": "e1", "project": "p1"}
    t = lambda name, *req: {"name": name, "params": [{"name": n, "required": True} for n in req]}   # noqa: E731
    assert mc.arguments(t("get_entity", "model", "entity"), ids, {}) == ({"model": "m1", "entity": "e1"}, False)
    assert mc.arguments(t("compare_models", "left", "right"), ids, {}) == ({"left": "m1", "right": "m2"}, False)
    args, guessed = mc.arguments(t("survey_results", "survey"), ids, {})
    assert args == {"survey": mc.MISSING} and guessed                     # a missing one must be said, not crash
    assert mc.arguments(t("get_project", "project"), {"model": "m1"}, {}) == (None, False)   # skipped, with why
    assert mc.arguments(t("what_changed", "model"), ids, {})[1] is True   # "no tag yet" is an answer
    assert "at" in mc.arguments(t("get_entity_as_of", "model", "entity"), ids, {})[0]
    assert mc.names_in({"items": [{"name": "a", "x": {"name": "b"}}], "query": "c"}) == {"a", "b"}


def test_a_fake_installation_passes_every_check():
    from eax.testing import mcp_check as mc
    cat = [{"name": "list_models", "area": "r", "changes": False, "params": []},
           {"name": "get_entity", "area": "r", "changes": False, "params": [{"name": "model", "required": True},
                                                                              {"name": "entity", "required": True}]},
           {"name": "survey_results", "area": "r", "changes": False, "params": [{"name": "survey", "required": True}]},
           {"name": "add_entities", "area": "b", "changes": True, "params": []}]
    added: list[str] = []

    def text(v):
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(v)}]}}

    def call(url, token, method, params):
        if token in (None, "not-a-token"):
            return 401, None, "{}"
        if method == "tools/list":
            return 200, {"result": {"tools": [{"name": t["name"], "description": "d", "inputSchema": {}} for t in cat]}}, ""
        n, a = params["name"], params["arguments"]
        if n == "add_entities":
            if token == "ro":
                return 200, text({"error": "This credential may only read through MCP"}), ""
            added.append(a["rows"][0]["name"])
            return 200, text({"saved": 1}), ""
        if n == "list_my_changes":
            return 200, text({"changes": [{"label": x} for x in added]}), ""
        if n == "survey_results":
            return 200, text({"error": "No survey"}), ""
        if n in ("ops_status", "maturity_overview"):
            return 200, text({"error": "Super Admins only"}), ""
        if n == "search_entities":
            return 200, text({"query": a["text"], "items": []}), ""
        return 200, text({"count": 0, "items": []}), ""

    def send(base, method, path, token, raw):
        return 200, json.dumps({"calls": [{"tool": "add_entities"}]})

    seen = []
    out = mc.run("http://api:8000", {"super-admin": "admin", "architect": "other"}, {"model": "m", "other_model": "m2", "entity": "e", "sid": "s"},
                 lambda name, outcome, detail, ms, **k: seen.append((name, outcome, detail)), read_only_token=lambda: "ro",
                 call=call, send=send, catalogue=cat)
    assert out == {"passed": 9, "failed": 0, "skipped": 0}, [x for x in seen if x[1] != "passed"]


def test_a_tool_that_crashes_fails_the_check():
    from eax.testing import mcp_check as mc
    cat = [{"name": "list_models", "area": "r", "changes": False, "params": []}]

    def call(url, token, method, params):
        if method == "tools/list":
            return 200, {"result": {"tools": [{"name": "list_models", "description": "d", "inputSchema": {}}]}}, ""
        return 200, {"result": {"content": [{"type": "text", "text": "Error executing tool list_models"}], "isError": True}}, ""
    seen = []
    mc.run("http://api:8000", {"super-admin": "a"}, {"model": "m"}, lambda n, o, d, ms, **k: seen.append((n, o)),
           call=call, send=lambda *a: (200, "{}"), catalogue=cat)
    assert ("mcp: list_models", "failed") in seen


def test_the_drawn_views_service_down_is_said_not_a_server_error():
    src = (API / "eax/mcp_server.py").read_text()
    assert "isinstance(exc, ViewsDown)" in src and "The drawn views' service does not answer" in src
