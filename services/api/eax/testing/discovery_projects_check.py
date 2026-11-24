"""The self-test's black-box check of Release 5.5 (owner, 16 Nov 2026, 12:41: "Test enterprise dicovery by adding test
cases which call the api's for it. Dont test the LLM part assume LLM will be able to do it. Call the MCP apis and then
save data using them"; "I assume Descision record will be tested").

Enterprise discovery (R5.5), through the REST API and the MCP server over HTTP, as the run's own Super Admin account.
The LLM's part (reaching and reading the sources) is assumed: the check makes the calls an AI makes with what it
"found", and checks what EA Explorer keeps:

  discovery projects: a project is set up            POST /discovery-projects in the run's test model: 201
  ...refused without the Discovery Admin role       the same as an Architect: 403
  ...sources are added                              a Git repository and a SharePoint site: 201 each
  ...Test the link forgets the sign-in              a link that does not answer: said so; the password typed is in no
                                                    answer, and the source keeps only that it was tested
  ...MCP: the AI sees the project                   discovery_projects
  ...MCP: a run asks first                          run_discovery_project without read and gone: the defaults asked
  ...MCP: a run starts and tags the model           run_discovery_project read=all gone=mark: the run, its sources
  ...MCP: the AI saves what it found                add_entities: an application, as the AI's uncommitted change
  ...MCP: Found in and may be the same              discovery_record_found
  ...MCP: NOT FOR AI items listed by title          discovery_report_skipped
  ...MCP: a decision found is logged as a Draft     discovery_log_decision: an ADR in the Governance Log
  ...MCP: the run finishes                          discovery_finish_run: committed as the AI agent on behalf of the
                                                    person who set it up, tagged again, one marked not found
  ...MCP: the run's report                          discovery_run_report: the element found, with its guid
  ...MCP: projects due answers                      discovery_projects_due
  ...Found in on the element                        GET /models/<m>/entities/<e>/found-in
  ...the run's report and a flag dealt with          GET /discovery-runs/<r>; POST .../may-be-same/<f>
  ...the project is deleted                         DELETE, then GET: 404

Decision records and dispensations (R5.5.1), through the REST API:

  decision records: the templates                   GET /governance/templates
  ...an ADR is logged, numbered per year             POST /governance: ADR-<year>-<n>
  ...refused without the Architecture Board          the same as an Architect: 403
  ...accepting needs the template                    accept before its fields: refused, naming what is missing
  ...filled in, then accepted                        PUT the fields, accept: Accepted
  ...linked to an element, shown on it               POST links; GET the element's decisions
  ...a dispensation needs its expiry date            refused without one
  ...a dispensation ending soon is listed            accepted, ending in 10 days: on ending-soon
  ...superseding marks the older                     a newer ADR supersedes it: Superseded, linked back
  ...a record's history                              GET /governance/<r>/history
  ...the report and its OData feed                   GET /governance/report, /odata/governance/GovernanceDecisions

Everything is named self_test_<run>_...; the discovery project is deleted here, and the run's purge removes what is
left (the Governance Log's records, the model's tags and content go with the test model). One result each.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date, timedelta

from .. import httpopen
from .negative import send as _send

ADR_FIELDS = {"context": "Self-test context", "options": "Self-test options", "decision": "Self-test decision",
              "rationale": "Self-test rationale", "consequences": "Self-test consequences"}
DISP_FIELDS = {"waived": "Self-test standard", "systems": "Self-test system", "justification": "Self-test reason",
               "risks": "Self-test risk", "remediation": "Self-test plan"}


def _whole(base: str, method: str, path: str, token: str, raw: bytes | None) -> tuple[int, str]:
    return _send(base, method, path, token, raw, limit=None)


def mcp_url(base: str) -> str:
    """Where the MCP server answers: EAX_TEST_MCP_URL, else beside the API in its container (port 8001) when the run
    calls the API directly, else /mcp at the same address (the front door routes it)."""
    if os.environ.get("EAX_TEST_MCP_URL"):
        return os.environ["EAX_TEST_MCP_URL"].rstrip("/")
    b = base.rstrip("/")
    return b[:-5] + ":8001/mcp" if b.endswith(":8000") else f"{b}/mcp"


def mcp_call(url: str, token: str, tool: str, arguments: dict, timeout: int = 120) -> tuple[int, dict | list | None, str]:
    """One MCP tool call over HTTP (JSON-RPC tools/call, as an AI client sends it). Returns the HTTP status, the tool's
    answer (parsed) and the raw text. A tool's own refusal comes back as {"error": ...}."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
    req = urllib.request.Request(url, data=body.encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                                          "Authorization": f"Bearer {token}"})
    try:
        with httpopen.urlopen(req, timeout=timeout) as r:      # noqa: S310 - the installation's own MCP server
            status, raw = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, None, exc.read().decode("utf-8", "replace")[:2000]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, None, f"no answer: {exc}"
    if raw.startswith("event:") or raw.startswith("data:"):                # an event stream: its data line
        raw = next((ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")), "")
    try:
        msg = json.loads(raw)
    except ValueError:
        return status, None, raw[:2000]
    if "error" in msg:
        return status, {"error": msg["error"].get("message", str(msg["error"]))}, raw[:2000]
    res = msg.get("result") or {}
    text = "".join(c.get("text", "") for c in res.get("content") or [] if c.get("type") == "text")
    try:
        out = json.loads(text)
    except ValueError:
        out = {"error": text} if res.get("isError") else {"text": text}
    if res.get("isError") and not (isinstance(out, dict) and out.get("error")):
        out = {"error": text}
    if isinstance(out, dict) and set(out) == {"count", "items"}:          # a list, as the server sends one
        out = out["items"]
    return status, out, raw[:2000]


def run(base: str, tokens: dict[str, str], ids: dict[str, str], record: Callable[..., None], send=_whole,
        mcp=mcp_call, mcp_at: str | None = None) -> dict[str, int]:
    """Enterprise discovery (REST and MCP) and decision records (REST), black-box, in the run's own test model."""
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    admin, model, sid = tokens.get("super-admin", ""), ids.get("model", ""), ids.get("sid", "")
    other = next((tokens[r] for r in ("architect", "report-viewer", "committer", "model-creator") if tokens.get(r)), "")
    url = mcp_at or mcp_url(base)

    def rec(group: str, name: str, ok: bool | None, detail: str, ms: int, req: str = "", resp: str = "") -> None:
        outcome = "skipped" if ok is None else "passed" if ok else "failed"
        counts[outcome] += 1
        record(f"{group}: {name}", outcome, str(detail)[:900], ms, request=req if outcome == "failed" else "",
               response=str(resp)[:2000] if outcome == "failed" else "")

    def call(method: str, path: str, body: dict | None, token: str = "") -> tuple[int, dict, str, int]:
        t0 = time.time()
        status, text = send(base, method, path, token or admin, json.dumps(body).encode() if body is not None else None)
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = {}
        return status, data if isinstance(data, dict) else {"items": data}, text, int((time.time() - t0) * 1000)

    def tool(name: str, args: dict) -> tuple[int, dict | list | None, str, int]:
        t0 = time.time()
        s, out, raw = mcp(url, admin, name, args)
        return s, out, raw, int((time.time() - t0) * 1000)

    if not admin or not model:
        rec("discovery projects", "a project is set up", None, "no Super Admin test account or test model", 0)
    else:
        _discovery(rec, call, tool, model, sid, other, ids)
        _decisions(rec, call, model, sid, other, ids)
    return counts                     # one way out (SonarQube S3516): the counts the checks filled in


# ---------------------------------------------------------------- enterprise discovery
def _discovery(rec, call, tool, model: str, sid: str, other: str, ids: dict) -> None:
    G = "discovery projects"
    name = f"self_test_{sid}_discovery"
    s, d, raw, ms = call("post", "/api/v1/discovery-projects",
                         {"name": name, "target_model": model, "purpose": "Self-test", "read_default": "new",
                          "gone_default": "mark", "schedule": "daily", "schedule_time": "02:00"})
    ok = s == 201 and bool(d.get("id")) and d.get("target_model", {}).get("id") == model and bool(d.get("next_due_at"))
    rec(G, "a project is set up", ok, f"{s}: {d.get('id') or raw[:200]}", ms, "POST /api/v1/discovery-projects", raw)
    if not ok:
        return
    pid = d["id"]
    if other:
        s, _d, raw, ms = call("post", "/api/v1/discovery-projects", {"name": f"{name}_refused", "target_model": model}, other)
        rec(G, "refused without the Discovery Admin role", s == 403, f"{s}", ms, "POST as a non-admin", raw)
    else:
        rec(G, "refused without the Discovery Admin role", None, "no other test account", 0)
    src_ok, sources = True, []
    for body in ({"kind": "git", "name": "Self-test repository", "location": "https://git.example.com/self-test.git",
                  "include": "README files", "sign_in": "key"},
                 {"kind": "sharepoint", "name": "Self-test site", "location": "https://example.sharepoint.com/sites/self-test",
                  "sign_in": "sso", "attachments": False}):
        s, d, raw, ms = call("post", f"/api/v1/discovery-projects/{pid}/sources", body)
        src_ok = src_ok and s == 201 and bool(d.get("id"))
        sources.append(d.get("id"))
    rec(G, "sources are added", src_ok, f"{len([x for x in sources if x])} of 2 added", ms, "POST sources", raw)
    secret = f"self-test-not-a-real-password-{sid}"
    s, d, raw, ms = call("post", "/api/v1/discovery-projects/test-link",
                         {"kind": "sftp", "location": "sftp://127.0.0.1:1/self-test", "sign_in": "basic",
                          "secret": {"username": "self-test", "password": secret}, "project": pid, "source": sources[0] or ""})
    s2, d2, raw2, _ = call("get", f"/api/v1/discovery-projects/{pid}", None)
    tested = next((x for x in d2.get("sources", []) if x.get("id") == sources[0]), {})
    ok = (s == 200 and d.get("ok") is False and secret not in raw and secret not in raw2 and tested.get("tested_at")
          and tested.get("test_ok") is False)
    rec(G, "Test the link forgets the sign-in", bool(ok), f"{s}: {d.get('note', '')[:150]}; kept: test_ok={tested.get('test_ok')}",
        ms, "POST test-link", raw + raw2)

    # ---- the AI's part, through MCP
    s, out, raw, ms = tool("discovery_projects", {})
    if s in (404, 503, 599) or out is None:
        for n in ("the AI sees the project", "a run asks first", "a run starts and tags the model", "the AI saves what it found",
                  "Found in and may be the same", "NOT FOR AI items listed by title", "a decision found is logged as a Draft",
                  "the run finishes", "the run's report", "projects due answers"):
            rec(G, f"MCP: {n}", None, f"the MCP server did not answer ({s}): is MCP switched on? {raw[:120]}", 0)
        _delete(rec, call, G, pid)
        return
    rec(G, "MCP: the AI sees the project", isinstance(out, list) and any(p.get("name") == name for p in out),
        f"{len(out) if isinstance(out, list) else out}", ms, "discovery_projects", raw)
    s, out, raw, ms = tool("run_discovery_project", {"project": name})
    ok = isinstance(out, dict) and out.get("ask") is True and out.get("read", {}).get("default") == "new" \
        and out.get("gone", {}).get("default") == "mark"
    rec(G, "MCP: a run asks first", ok, f"{(out or {}).get('question', raw[:150]) if isinstance(out, dict) else raw[:150]}", ms,
        "run_discovery_project (no read, gone)", raw)
    s, out, raw, ms = tool("run_discovery_project", {"project": name, "read": "all", "gone": "mark", "ai_client": "EA Explorer self-test"})
    ok = isinstance(out, dict) and bool(out.get("run")) and len(out.get("sources") or []) == 2 and "(before)" in (out.get("tagged") or "") \
        and (out.get("who") or "").startswith("AI agent on behalf of")
    rec(G, "MCP: a run starts and tags the model", ok, f"{(out or {}).get('tagged') or raw[:200]}", ms, "run_discovery_project", raw)
    if not ok:
        _delete(rec, call, G, pid, abandon=True)
        return
    run_id = out["run"]
    found = f"Self-test discovered app {sid}"
    s, out, raw, ms = tool("add_entities", {"model": model, "entity_type": "ApplicationComponent",
                                            "rows": [{"name": found, "description": "Found by the self-test's pretend AI"}]})
    ok = isinstance(out, dict) and not out.get("error") and out.get("saved", 0) >= 1
    rec(G, "MCP: the AI saves what it found", ok, f"{(out or {}).get('saved')} saved" if ok else raw[:300], ms, "add_entities", raw)
    s, out, raw, ms = tool("discovery_record_found", {"run": run_id, "items": [
        {"element": found, "kind": "entity", "source": "Self-test repository", "item": "README.md", "place": "line 1",
         "link": "https://git.example.com/self-test/README.md", "may_be_same": "Self-test application 1",
         "note": "the same purpose"}]})
    ok = isinstance(out, dict) and out.get("recorded") == 1 and out.get("may_be_same") == 1
    rec(G, "MCP: Found in and may be the same", ok, json.dumps(out)[:200], ms, "discovery_record_found", raw)
    s, out, raw, ms = tool("discovery_report_skipped", {"run": run_id, "items": [
        {"source": "Self-test site", "title": f"self_test_{sid} board pack.docx", "place": "Shared Documents", "date": "2026-11-01"}]})
    rec(G, "MCP: NOT FOR AI items listed by title", isinstance(out, dict) and out.get("recorded") == 1, json.dumps(out)[:200], ms,
        "discovery_report_skipped", raw)
    s, out, raw, ms = tool("discovery_log_decision", {"run": run_id, "kind": "ADR", "title": f"self_test_{sid} ADR found by discovery",
                                                      "fields": ADR_FIELDS, "source": "Self-test repository",
                                                      "item": "docs/adr/0001.md", "place": "the whole file"})
    ok = isinstance(out, dict) and (out.get("ref") or "").startswith("ADR-") and "Draft" in (out.get("note") or "")
    if isinstance(out, dict) and "switched off" in str(out.get("error", "")):
        rec(G, "MCP: a decision found is logged as a Draft", None, out["error"], ms)
    else:
        rec(G, "MCP: a decision found is logged as a Draft", ok, (out or {}).get("ref") or raw[:200], ms, "discovery_log_decision", raw)
    s, out, raw, ms = tool("discovery_finish_run", {"run": run_id, "positions": {"Self-test repository": "commit self-test-1"},
                                                    "gone": [{"element": "Self-test application 2", "source": "Self-test repository"}],
                                                    "summary": "Self-test: one application found, one not found."})
    c = (out or {}).get("run", {}).get("counts", {}) if isinstance(out, dict) else {}
    ok = isinstance(out, dict) and out.get("run", {}).get("status") == "finished" and c.get("found") == 1 \
        and c.get("skipped") == 1 and c.get("may_be_same") == 1 and c.get("not_found") == 1 and "&right=tag:" in (out.get("compare") or "")
    rec(G, "MCP: the run finishes", ok, f"{c}; {(out or {}).get('committing', '') if isinstance(out, dict) else raw[:200]}", ms,
        "discovery_finish_run", raw)
    s, out, raw, ms = tool("discovery_run_report", {"run": run_id})
    f0 = ((out or {}).get("found") or [{}])[0] if isinstance(out, dict) else {}
    ok = bool(f0.get("element_id")) and f0.get("item") == "README.md" and (out.get("skipped") or [{}])[0].get("title", "").endswith(".docx")
    rec(G, "MCP: the run's report", ok, f"found {f0.get('element_name')} ({f0.get('element_id')})", ms, "discovery_run_report", raw)
    s, out, raw, ms = tool("discovery_projects_due", {})
    rec(G, "MCP: projects due answers", isinstance(out, dict) and isinstance(out.get("due"), list), json.dumps(out)[:200], ms,
        "discovery_projects_due", raw)

    # ---- what a person sees, through REST
    if f0.get("element_id"):
        s, d, raw, ms = call("get", f"/api/v1/models/{model}/entities/{f0['element_id']}/found-in", None)
        fi = (d.get("found_in") or [{}])[0]
        rec(G, "Found in on the element", s == 200 and fi.get("item") == "README.md" and fi.get("who", "").startswith("AI agent on behalf of"),
            f"{s}: {fi.get('source')} / {fi.get('item')} / {fi.get('who')}", ms, "GET found-in", raw)
    else:
        rec(G, "Found in on the element", False, "the run's report gave no element", 0)
    s, d, raw, ms = call("get", f"/api/v1/discovery-runs/{run_id}", None)
    flag = (d.get("may_be_same") or [{}])[0].get("id")
    s2, _d2, raw2, _ = call("post", f"/api/v1/discovery-runs/{run_id}/may-be-same/{flag}", None) if flag else (0, {}, "", 0)
    rec(G, "the run's report and a flag dealt with", s == 200 and s2 == 200 and d.get("run", {}).get("status") == "finished",
        f"report {s}, flag {s2}", ms, "GET discovery-runs; POST may-be-same", raw + raw2)
    _delete(rec, call, G, pid)


def _delete(rec, call, G: str, pid: str, abandon: bool = False) -> None:
    s, d, raw, ms = call("delete", f"/api/v1/discovery-projects/{pid}", None)
    if s == 409 and abandon:
        rec(G, "the project is deleted", None, "a run was left under way: the run's purge removes it", ms)
        return
    s2, _d, _r, _ = call("get", f"/api/v1/discovery-projects/{pid}", None)
    rec(G, "the project is deleted", s == 200 and s2 == 404, f"delete {s}, then get {s2}", ms, "DELETE discovery project", raw)


# ---------------------------------------------------------------- decision records and dispensations
def _decisions(rec, call, model: str, sid: str, other: str, ids: dict) -> None:
    G = "decision records"
    s, d, raw, ms = call("get", "/api/v1/governance/templates", None)
    if s in (404, 503):
        rec(G, "the templates", None, f"{s}: projects are switched off", ms)
        return
    adr, disp = "Architecture Decision Record", "Dispensation"
    ok = s == 200 and adr in d and disp in d and any(f.get("name") == "context" for f in d[adr].get("fields", []))
    rec(G, "the templates", ok, f"{s}: {', '.join(k for k in d if k in (adr, disp))}", ms, "GET templates", raw)
    s, d, raw, ms = call("post", "/api/v1/governance", {"kind": adr, "title": f"self_test_{sid} decision", "owner": "Self-test"})
    year = date.today().year
    ok = s == 201 and (d.get("ref") or "").startswith(f"ADR-{year}-")
    rec(G, "an ADR is logged, numbered per year", ok, f"{s}: {d.get('ref') or raw[:200]}", ms, "POST governance", raw)
    if not ok:
        return
    rid = d["id"]
    if other:
        s, _d, raw, ms = call("post", "/api/v1/governance", {"kind": adr, "title": f"self_test_{sid} refused"}, other)
        rec(G, "refused without the Architecture Board", s == 403, f"{s}", ms, "POST as a non-board account", raw)
    else:
        rec(G, "refused without the Architecture Board", None, "no other test account", 0)
    s, d, raw, ms = call("post", f"/api/v1/governance/{rid}/decision", {"action": "accept", "comment": "self-test"})
    rec(G, "accepting needs the template", s in (400, 409) and "record type" in raw, f"{s}: {d.get('message', raw)[:200]}", ms,
        "accept before the fields", raw)
    s, d, raw, ms = call("put", f"/api/v1/governance/{rid}", {"record_type": "Architecture", "fields": ADR_FIELDS})
    s2, d2, raw2, _ = call("post", f"/api/v1/governance/{rid}/decision", {"action": "accept", "comment": "self-test"})
    rec(G, "filled in, then accepted", s == 200 and s2 == 200 and _status(call, rid) == "Accepted", f"put {s}, accept {s2}", ms,
        "PUT fields; accept", raw + raw2)
    entity = ids.get("entity", "")
    if entity:
        s, d, raw, ms = call("post", f"/api/v1/governance/records/{rid}/links",
                             {"kind": "element", "relation": "affects", "target": entity, "model": model})
        s2, d2, raw2, _ = call("get", f"/api/v1/models/{model}/entities/{entity}/decisions", None)
        on = any(r.get("id") == rid for r in d2.get("records", []))
        rec(G, "linked to an element, shown on it", s == 201 and s2 == 200 and on, f"link {s}, element {s2}, shown {on}", ms,
            "POST links; GET element decisions", raw + raw2)
    else:
        rec(G, "linked to an element, shown on it", None, "no test entity", 0)
    s, d, raw, ms = call("post", "/api/v1/governance", {"kind": disp, "title": f"self_test_{sid} no end date", "status": "Accepted"})
    rec(G, "a dispensation needs its expiry date", s == 400 and "expiry" in raw, f"{s}: {d.get('message', '')[:150]}", ms,
        "POST a dispensation without expiry", raw)
    s, d, raw, ms = call("post", "/api/v1/governance", {"kind": disp, "title": f"self_test_{sid} waiver", "owner": "Self-test",
                                                        "sponsor": "Self-test sponsor", "fields": DISP_FIELDS,
                                                        "expires_on": str(date.today() + timedelta(days=10))})
    did = d.get("id")
    s2, _d2, raw2, _ = call("post", f"/api/v1/governance/{did}/decision", {"action": "accept", "comment": "self-test"}) if did else (0, {}, "", 0)
    s3, d3, raw3, _ = call("get", "/api/v1/governance/ending-soon", None)
    listed = any(x.get("id") == did for x in d3.get("dispensations", []))
    rec(G, "a dispensation ending soon is listed", s == 201 and s2 == 200 and listed,
        f"logged {s} ({d.get('ref')}), accepted {s2}, ending soon {listed}", ms, "dispensation; ending-soon", raw + raw2 + raw3)
    s, d, raw, ms = call("post", "/api/v1/governance", {"kind": adr, "title": f"self_test_{sid} newer decision"})
    new = d.get("id")
    s2, _d2, raw2, _ = call("post", f"/api/v1/governance/records/{new}/links",
                            {"kind": "record", "relation": "supersedes", "target": rid}) if new else (0, {}, "", 0)
    s3, d3, raw3, _ = call("get", f"/api/v1/governance/records/{rid}/links", None)
    back = any(x.get("relation") == "superseded-by" and x.get("id") == new for x in d3.get("linked_from", []))
    rec(G, "superseding marks the older", s2 == 201 and _status(call, rid) == "Superseded" and back,
        f"link {s2}, older {_status(call, rid)}, linked back {back}", ms, "supersedes", raw2 + raw3)
    s, d, raw, ms = call("get", f"/api/v1/governance/{rid}/history", None)
    hist = d.get("history") if isinstance(d.get("history"), list) else d.get("items", [])
    rec(G, "a record's history", s == 200 and len(hist or []) >= 2, f"{s}: {len(hist or [])} entries", ms, "GET history", raw)
    s, d, raw, ms = call("get", "/api/v1/governance/report", None)
    s2, d2, raw2, _ = call("get", "/api/v1/odata/governance/GovernanceDecisions", None)
    rec(G, "the report and its OData feed", s == 200 and s2 == 200 and isinstance(d2.get("value"), list),
        f"report {s}, OData {s2} ({len(d2.get('value') or [])} rows)", ms, "GET report; OData", raw[:500] + raw2[:500])


def _status(call, rid: str) -> str:
    s, d, _raw, _ms = call("get", "/api/v1/governance", None)
    return next((r.get("status", "") for r in d.get("records", []) if r.get("id") == rid), "")
