"""Release 5.5 in the self-test (owner, 16 Nov 2026, 12:41: "Test enterprise dicovery by adding test cases which call the
api's for it ... Call the MCP apis and then save data using them"; "I assume Descision record will be tested").
eax/testing/discovery_projects_check.py runs in the API suite against the running installation: discovery through REST
and the MCP server over HTTP, decision records and dispensations through REST. Here: it is wired in, it reads MCP's
answers as an AI client gets them, it cleans up after itself, and a fake installation passes it end to end."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
API = Path(__file__).resolve().parents[1]


def test_it_runs_in_the_api_suite_after_discovery():
    run = (API / "eax/testing/run.py").read_text()
    assert "discovery_projects_check.run(API, tokens, ids, r.recorder(\"api\"))" in run
    assert run.index("discovery_check.run(") < run.index("discovery_projects_check.run(")


def test_where_mcp_answers():
    from eax.testing import discovery_projects_check as dc
    assert dc.mcp_url("http://api:8000") == "http://api:8001/mcp"
    assert dc.mcp_url("https://ea.example.com") == "https://ea.example.com/mcp"


def _fake_http(monkeypatch, body: str, status: int = 200):
    from eax.testing import discovery_projects_check as dc

    class R:
        def __init__(self):
            self.status = status

        def read(self):
            return body.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(dc.urllib.request, "urlopen", lambda *a, **k: R())


def test_mcp_answers_are_read_as_an_ai_client_gets_them(monkeypatch):
    from eax.testing import discovery_projects_check as dc
    _fake_http(monkeypatch, json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
        "content": [{"type": "text", "text": json.dumps({"count": 1, "items": [{"name": "p"}]})}], "isError": False}}))
    assert dc.mcp_call("http://mcp.test/mcp", "t", "discovery_projects", {})[1] == [{"name": "p"}]          # a list comes as count and items
    _fake_http(monkeypatch, "event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
        "content": [{"type": "text", "text": "{\"run\": \"r1\"}"}]}}))
    assert dc.mcp_call("http://mcp.test/mcp", "t", "run_discovery_project", {})[1] == {"run": "r1"}         # an event stream
    _fake_http(monkeypatch, json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
        "content": [{"type": "text", "text": "Error executing tool x"}], "isError": True}}))
    assert dc.mcp_call("http://mcp.test/mcp", "t", "x", {})[1] == {"error": "Error executing tool x"}


def test_the_run_purge_removes_what_the_check_leaves():
    fx = (API / "eax/testing/fixtures.py").read_text()
    assert "DELETE FROM core.discovery_projects WHERE name LIKE" in fx
    assert "DELETE FROM proj.gov_records WHERE project_id IS NULL AND title LIKE" in fx
    dec = (API / "eax/decisions.py").read_text()
    assert dec.count("g.title NOT LIKE 'self\\\\_test\\\\_%'") == 2                       # left out of the report and its feed


def test_the_message_says_an_architecture_decision_record():
    import pytest

    from eax import decisions as dec
    from eax.metamodel_edit import EditError
    with pytest.raises(EditError) as e:
        dec.check_required(dec.ADR, {"title": "x", "record_type": "Data", "owner": "o", "fields": {}})
    assert str(e.value).startswith("An architecture decision record needs")


def test_a_fake_installation_passes_every_check():
    """The check against an installation that answers as EA Explorer does: every result passes, none is skipped."""
    from eax.testing import discovery_projects_check as dc
    run_id, rid, did, new = "run-1", "adr-1", "disp-1", "adr-2"
    state = {"status": {rid: "Draft"}, "deleted": False}

    def send(base, method, path, token, raw):
        body = json.loads(raw) if raw else {}
        other = token == "other"
        if path == "/api/v1/discovery-projects" and method == "post":
            return (403, "{}") if other else (201, json.dumps({"id": "p1", "target_model": {"id": "m"}, "next_due_at": "x"}))
        if path.endswith("/sources"):
            return 201, json.dumps({"id": 7})
        if path.endswith("/test-link"):
            return 200, json.dumps({"ok": False, "note": "It did not answer"})
        if path == "/api/v1/discovery-projects/p1":
            if method == "delete":
                state["deleted"] = True
                return 200, "{}"
            return (404, "{}") if state["deleted"] else (200, json.dumps({"sources": [{"id": 7, "tested_at": "t", "test_ok": False}]}))
        if path.endswith("/found-in"):
            return 200, json.dumps({"found_in": [{"item": "README.md", "who": "AI agent on behalf of a"}]})
        if path == f"/api/v1/discovery-runs/{run_id}":
            return 200, json.dumps({"run": {"status": "finished"}, "may_be_same": [{"id": 3}]})
        if "/may-be-same/" in path:
            return 200, "{}"
        if path == "/api/v1/governance/templates":
            return 200, json.dumps({"Architecture Decision Record": {"fields": [{"name": "context"}]}, "Dispensation": {"fields": []}})
        if path == "/api/v1/governance" and method == "post":
            if other:
                return 403, "{}"
            if body["kind"] == "Dispensation" and not body.get("expires_on"):
                return 400, json.dumps({"message": "needs its expiry date"})
            i = did if body["kind"] == "Dispensation" else (rid if "newer" not in body["title"] else new)
            return 201, json.dumps({"id": i, "ref": f"ADR-{__import__('datetime').date.today().year}-001"})
        if path == "/api/v1/governance":
            return 200, json.dumps({"records": [{"id": k, "status": v} for k, v in state["status"].items()]})
        if path == f"/api/v1/governance/{rid}/decision":
            if not state.get("filled"):
                return 400, json.dumps({"message": "needs a record type"})
            state["status"][rid] = "Accepted"
            return 200, "{}"
        if path.endswith("/decision"):
            return 200, "{}"
        if path == f"/api/v1/governance/{rid}" and method == "put":
            state["filled"] = True
            return 200, "{}"
        if path == f"/api/v1/governance/records/{new}/links":
            state["status"][rid] = "Superseded"
            return 201, "{}"
        if path.endswith("/links") and method == "post":
            return 201, "{}"
        if path == f"/api/v1/governance/records/{rid}/links":
            return 200, json.dumps({"linked_from": [{"relation": "superseded-by", "id": new}]})
        if path.endswith("/decisions"):
            return 200, json.dumps({"records": [{"id": rid}]})
        if path.endswith("/ending-soon"):
            return 200, json.dumps({"dispensations": [{"id": did}]})
        if path.endswith("/history"):
            return 200, json.dumps({"history": [1, 2, 3]})
        if path.endswith("/report"):
            return 200, "{}"
        if "odata/governance" in path:
            return 200, json.dumps({"value": []})
        return 500, f"unexpected {method} {path}"

    def mcp(url, token, tool, args):
        answers = {
            "discovery_projects": [{"name": "self_test_s1_discovery"}],
            "run_discovery_project": ({"run": run_id, "sources": [1, 2], "tagged": "x run 1 (before)", "who": "AI agent on behalf of a"}
                                      if args.get("read") else {"ask": True, "read": {"default": "new"}, "gone": {"default": "mark"}}),
            "add_entities": {"saved": 1},
            "discovery_record_found": {"recorded": 1, "may_be_same": 1},
            "discovery_report_skipped": {"recorded": 1},
            "discovery_log_decision": {"ref": "ADR-2026-009", "note": "Logged as a Draft"},
            "discovery_finish_run": {"run": {"status": "finished", "counts": {"found": 1, "skipped": 1, "may_be_same": 1, "not_found": 1}},
                                     "compare": "#/compare?left=tag:m:a&right=tag:m:b"},
            "discovery_run_report": {"found": [{"element_id": "e1", "item": "README.md"}], "skipped": [{"title": "b.docx"}]},
            "discovery_projects_due": {"due": []}}
        return 200, answers[tool], ""

    seen = []
    out = dc.run("http://api:8000", {"super-admin": "admin", "architect": "other"}, {"model": "m", "sid": "s1", "entity": "e9"},
                 lambda name, outcome, detail, ms, **k: seen.append((name, outcome, detail)), send=send, mcp=mcp)
    assert out == {"passed": 28, "failed": 0, "skipped": 0}, [x for x in seen if x[1] != "passed"]
