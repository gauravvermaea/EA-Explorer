"""Every MCP tool tried in the full test, as an AI calls it, with a card of its own (owner, 22 Nov 2026, 14:12: "Also in
full test build tests for all MCP then they should have there own cards, these MCP would respond to the api as called by
the LLM"; 14:13: "as they do now").

The MCP suite (eax/testing/mcp_check.py, JSON-RPC over HTTP, no language model) already called every tool that only
reads. Now every tool that changes something is called too: one that previews must answer with a preview and a confirm
token, or say in words why not, and must refuse a confirm token that is not one; one that changes at once is pointed at
something that does not exist and must refuse, so nothing changes. The self-test's summary keeps the MCP checks, and the
full test's summary page shows them as their own card."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from eax import mcp_catalogue
from eax.testing import mcp_check as mc
from eax.testing import run_summary as rs

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import fullreport as F  # noqa: E402

IDS = {"model": "m-1", "other_model": "m-2", "project": "p-1", "entity": "e-1", "sid": "42"}


def _server(behaviour):
    """A stand-in MCP server: tools/list gives the catalogue; tools/call answers as `behaviour` says."""
    calls = []

    def call(url, token, method, params, timeout=180):
        if method == "tools/list":
            if token in (None, "not-a-token"):
                return 401, None, "no"
            tools = [{"name": t["name"], "description": t["what"] or "x", "inputSchema": {}} for t in mcp_catalogue.tools()]
            return 200, {"result": {"tools": tools}}, ""
        calls.append((params["name"], params["arguments"], token))
        out = behaviour(params["name"], params["arguments"])
        return 200, {"result": {"content": [{"type": "text", "text": json.dumps(out)}]}}, json.dumps(out)
    return call, calls


def _run(behaviour):
    call, calls = _server(behaviour)
    got = []
    mc.run("http://x", {"super-admin": "t"}, IDS, lambda name, outcome, detail, ms, **k: got.append((name, outcome, detail)),
           call=call, send=lambda *a, **k: (200, "{}"))
    return {n: (o, d) for n, o, d in got}, calls


def _good(name, args):
    t = next(x for x in mcp_catalogue.tools() if x["name"] == name)
    ckey = next((p["name"] for p in t["params"] if p["name"] in ("confirm", "confirm_token")), "")
    if ckey and args.get(ckey):
        return {"error": "That confirm token is not for this call."}
    if ckey:
        return {"preview": {"will": ["something"]}, "confirm": "pv_1"}
    if t["changes"] and mc.MISSING in args.values():
        return {"error": "Not found."}
    return {"items": []}


def test_every_previewing_tool_is_called_without_changing_anything():
    res, calls = _run(_good)
    changing = [t for t in mcp_catalogue.tools() if t["changes"]]
    previewing = [t["name"] for t in changing if any(p["name"] in ("confirm", "confirm_token") for p in t["params"])]
    assert previewing and "sp_start" in previewing and "sp_save" in previewing
    for n in previewing:
        assert res[f"mcp: {n} (preview)"][0] == "passed", n
        assert res[f"mcp: {n} (a wrong confirm token)"][0] == "passed", n
    # a previewing tool is never called with a real confirm token, so nothing is ever done
    for name, args, _tok in calls:
        if name in previewing:
            assert not args.get("confirm") or args["confirm"] == "pv_self-test-not-a-token"


def test_a_tool_that_changes_at_once_is_pointed_at_nothing():
    res, calls = _run(_good)
    assert res["mcp: commit_my_changes (refuses what is not there)"][0] == "passed"
    args = next(a for n, a, _t in calls if n == "commit_my_changes")
    assert args["model"] == mc.MISSING
    assert res["mcp: create_model (refuses what is not there)"][0] == "skipped"     # nothing to point at: not called
    assert not any(n == "create_model" for n, _a, _t in calls)


def test_a_crash_or_a_change_without_a_preview_fails():
    def bad(name, args):
        if name == "sp_start":
            return {"version": 1, "status": "draft"}               # did it without a preview
        if name == "sp_save" and not args.get("confirm"):
            raise RuntimeError
        if name == "commit_my_changes":
            return {"committed": 3}                                 # took a model that is not there
        return _good(name, args)

    def behaviour(name, args):
        try:
            return bad(name, args)
        except RuntimeError:
            return None

    call, _calls = _server(behaviour)

    def crashing(url, token, method, params, timeout=180):
        if method == "tools/call" and params["name"] == "sp_save" and not params["arguments"].get("confirm"):
            return 200, {"result": {"isError": True, "content": [{"type": "text", "text": "Error executing tool"}]}}, "boom"
        return call(url, token, method, params, timeout)
    got = {}
    mc.run("http://x", {"super-admin": "t"}, IDS, lambda n, o, d, ms, **k: got.__setitem__(n, (o, d)), call=crashing,
           send=lambda *a, **k: (200, "{}"))
    assert got["mcp: sp_start (preview)"][0] == "failed" and "without a preview" in got["mcp: sp_start (preview)"][1]
    assert got["mcp: sp_save (preview)"][0] == "failed" and "server error" in got["mcp: sp_save (preview)"][1]
    assert got["mcp: commit_my_changes (refuses what is not there)"][0] == "failed"


def test_the_summary_keeps_the_mcp_checks_and_the_full_report_gives_them_a_card():
    results = [{"suite": "mcp", "name": "mcp: sp_start (preview)", "outcome": "passed", "detail": "a preview"},
               {"suite": "mcp", "name": "mcp: sp_save (preview)", "outcome": "failed", "detail": "a server error: boom"},
               {"suite": "api", "name": "GET /x", "outcome": "passed", "detail": ""}]
    m = rs.mcp(results)
    assert m["passed"] == 1 and m["failed"] == 1 and [c["name"] for c in m["checks"]] == ["sp_start (preview)", "sp_save (preview)"]
    assert rs.mcp([{"suite": "api"}]) is None
    s = rs.make({"run": {"id": 1}, "results": results}, None)
    assert s["mcp"]["failed"] == 1
    html = "".join(F.cards({"selftest": {"mcp": m}, "steps": []}))
    assert "MCP tools" in html and "sp_save (preview)" in html and "1 failed" in html
    ok = "".join(F.cards({"selftest": {"mcp": {"passed": 3, "failed": 0, "skipped": 1, "checks": []}}, "steps": []}))
    assert "Every tool answered as it should" in ok
