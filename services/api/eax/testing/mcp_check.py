"""The MCP suite of the self-test (owner, 16 Nov 2026, 12:45: "add a story for MCP test, where MCP api is tested";
12:58: "It should go now, its just test using api, not really with a LLM").

The MCP server called over HTTP exactly as an AI client calls it (JSON-RPC tools/list and tools/call on /mcp), with
the run's own accounts and test data; no language model is involved:

  mcp: the server lists every tool              tools/list has every tool of the code (eax/mcp_catalogue.py), each
                                                with what it does and its parameters
  mcp: no token is refused                      401 without a token, and with a token that is not one
  mcp: <tool>                                   every tool that only reads, called with the run's model, entity,
                                                project and the like: it answers, never a server error; a tool whose
                                                arguments the run cannot know (a survey, a merge request...) is called
                                                with one that does not exist and must say so, not fail
  mcp: a change is the person's uncommitted one add_entities in the run's second model, then list_my_changes shows it
  mcp: a read-only token changes nothing        a read-only token for the run's Super Admin account: reads answer,
                                                add_entities is refused and nothing is added
  mcp: the wrong role is refused                an account without the role asks for the installation's status
                                                (Super Admins and IT Admins only) and the EA maturity (Super Admins)
  mcp: every call is in the AI activity log     GET /api/v1/mcp/activity: the suite's calls are there, as its account

The tools that change things are tried in the API suite's flows (discovery runs through MCP, R5.5) and the fixtures
(models made through the MCP build tools). One result per check; nothing is left outside the run's own test data.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime

from .discovery_projects_check import _whole, mcp_url

Record = Callable[..., None]
MISSING = "00000000-0000-0000-0000-00000000beef"        # a guid nothing has: "not found" must be said, not crash
# tools that only read but whose arguments the run cannot know: called with one that does not exist
GUESSED = {"survey", "request", "draft", "analysis", "run", "scenario"}
# tools whose answer depends on what the installation has now: their own "there is none yet" is an answer
MAY_SAY_NONE = {"what_changed", "list_drawn_views", "get_drawn_view", "ops_backups", "ops_logs"}


def names_in(out: object) -> set[str]:
    """Every "name" in an answer, however deep (to see whether an element came back)."""
    found: set[str] = set()
    if isinstance(out, dict):
        for k, v in out.items():
            if k == "name" and isinstance(v, str):
                found.add(v)
            else:
                found |= names_in(v)
    elif isinstance(out, list):
        for v in out:
            found |= names_in(v)
    return found


def rpc(url: str, token: str | None, method: str, params: dict, timeout: int = 180) -> tuple[int, dict | None, str]:
    """One JSON-RPC call to the MCP server, as an AI client sends it: (HTTP status, the message, the raw text)."""
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:              # noqa: S310 - the installation's own MCP server
            status, raw = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, None, exc.read().decode("utf-8", "replace")[:2000]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, None, f"no answer: {exc}"
    if raw.startswith(("event:", "data:")):
        raw = next((ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")), "")
    try:
        return status, json.loads(raw), raw[:2000]
    except ValueError:
        return status, None, raw[:2000]


def answer(msg: dict | None) -> tuple[str, object]:
    """What a tools/call answered: ("ok", the tool's answer), ("refused", its own message) or ("crashed", why)."""
    if not msg:
        return "crashed", "no JSON-RPC answer"
    if "error" in msg:
        return "crashed", msg["error"].get("message", str(msg["error"])) if isinstance(msg["error"], dict) else str(msg["error"])
    res = msg.get("result") or {}
    text = "".join(c.get("text", "") for c in res.get("content") or [] if c.get("type") == "text")
    if res.get("isError"):
        return "crashed", text[:500]                          # the tool raised: "Error executing tool ..."
    try:
        out = json.loads(text)
    except ValueError:
        out = text
    if isinstance(out, dict) and out.get("error"):
        return "refused", str(out["error"])[:500]
    return "ok", out


def arguments(tool: dict, ids: dict, found: dict) -> tuple[dict | None, bool]:
    """The arguments to call a reading tool with, from the run's test data: (arguments, guessed). None: the run has
    nothing to give one it needs."""
    model, other = ids.get("model", ""), ids.get("other_model", "")
    known = {"model": model, "entity": ids.get("entity", ""), "project": ids.get("project", ""), "entity_type": "ApplicationComponent",
             "text": "Self-test", "left": model, "right": other, "source": "Self-test application 1",
             "target": "Self-test capability 1", "source_type": "ApplicationComponent", "target_type": "Capability",
             "entities": found.get("entities") or ["Self-test duplicate app", "Self-test duplicate ap"], "from_version": 1, "service": "api",
             "view": found.get("view") or "VP-01", "relationship": found.get("relationship", ""), "attribute": "name",
             "code": "self_test_rule", "name": "Self-test rule", "kind": "relationship", "spec": {},
             "words": "backup restore", "key": "readme", "guide": "01-overview"}   # the documentation tools (R9.3)
    args, guessed = {}, False
    for p in tool["params"]:
        if not p["required"]:
            continue
        n = p["name"]
        if n in GUESSED:
            args[n], guessed = MISSING, True
        elif known.get(n) not in (None, ""):
            args[n] = known[n]
            guessed = guessed or n in ("attribute", "code", "name", "kind", "spec")
        else:
            return None, False
    if tool["name"] == "compare_duplicates" and not found.get("entities"):
        guessed = True
    if tool["name"] == "get_drawn_view" and not ids.get("view"):
        args["view"], guessed = MISSING, True
    if tool["name"] == "model_through_view":
        args["view"] = found.get("view") or "VP-01"
        guessed = guessed or not found.get("view")         # no views listed in this installation
    if tool["name"] == "screen_help":                     # the start page's on-screen help (R9.3)
        args["key"] = "page:#/"
    if tool["name"] == "get_entity_as_of":
        args["at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return args, guessed or tool["name"] in MAY_SAY_NONE


def run(base: str, tokens: dict[str, str], ids: dict[str, str], record: Record, read_only_token: Callable[[], str] | None = None,
        url: str | None = None, call=rpc, send=_whole, catalogue: list[dict] | None = None) -> dict[str, int]:
    """Every check of the MCP suite; read_only_token makes the run's read-only token (recorded with its fixtures)."""
    url = url or mcp_url(base)
    admin = tokens.get("super-admin", "")
    other = next((tokens[r] for r in ("architect", "no-role", "report-viewer", "committer") if tokens.get(r)), "")
    counts = {"passed": 0, "failed": 0, "skipped": 0}

    def rec(name: str, ok: bool | None, detail: str, ms: int = 0, req: str = "", resp: str = "") -> None:
        outcome = "skipped" if ok is None else "passed" if ok else "failed"
        counts[outcome] += 1
        record(f"mcp: {name}", outcome, str(detail)[:900], ms, request=req if outcome == "failed" else "",
               response=str(resp)[:2000] if outcome == "failed" else "")

    def tool(name: str, args: dict, token: str | None = None) -> tuple[str, object, str, int]:
        t0 = time.time()
        s, msg, raw = call(url, token or admin, "tools/call", {"name": name, "arguments": args})
        kind, out = answer(msg) if s == 200 else ("crashed", f"HTTP {s}: {raw[:300]}")
        return kind, out, raw, int((time.time() - t0) * 1000)

    if catalogue is None:
        from .. import mcp_catalogue
        catalogue = mcp_catalogue.tools()
    if not admin:
        rec("the server lists every tool", None, "no Super Admin test account")
        return counts
    t0 = time.time()
    s, msg, raw = call(url, admin, "tools/list", {})
    ms = int((time.time() - t0) * 1000)
    if s in (404, 502, 503, 599) or msg is None:
        rec("the server lists every tool", None, f"the MCP server did not answer ({s}): is MCP switched on? {raw[:150]}", ms)
        return counts
    listed = {t["name"]: t for t in (msg.get("result") or {}).get("tools", [])}
    want = {t["name"] for t in catalogue}
    bare = [n for n, t in listed.items() if not (t.get("description") or "").strip() or "inputSchema" not in t]
    ok = want <= set(listed) and not bare
    rec("the server lists every tool", ok, f"{len(listed)} listed, {len(want)} in the code"
        + (f"; missing: {', '.join(sorted(want - set(listed)))}" if want - set(listed) else "")
        + (f"; without a description: {', '.join(bare)}" if bare else ""), ms, "tools/list", raw)
    s1, _m, raw1 = call(url, None, "tools/list", {})
    s2, _m, raw2 = call(url, "not-a-token", "tools/list", {})
    rec("no token is refused", s1 == 401 and s2 == 401, f"no token {s1}, a wrong one {s2}", 0, "tools/list without a token", raw1 + raw2)

    found: dict[str, str] = {}                               # what the reads give the next ones
    kind, out, _raw, _ms = tool("list_relationships", {"model": ids.get("model", "")})
    if kind == "ok":
        rows = out if isinstance(out, list) else (out or {}).get("items") or (out or {}).get("relationships") or []
        if rows and isinstance(rows[0], dict):
            found["relationship"] = str(rows[0].get("id") or rows[0].get("guid") or "")
    kind, out, _raw, _ms = tool("list_views", {})
    if kind == "ok":
        rows = out if isinstance(out, list) else (out or {}).get("items") or (out or {}).get("views") or []
        if rows and isinstance(rows[0], dict):
            found["view"] = str(rows[0].get("code") or rows[0].get("id") or "")

    kind, out, _raw, _ms = tool("find_duplicates", {"model": ids.get("model", "")})
    if kind == "ok" and isinstance(out, dict) and out.get("groups"):
        found["entities"] = [e["id"] for e in out["groups"][0].get("entities", []) if e.get("id")]

    for t in sorted((x for x in catalogue if not x["changes"]), key=lambda x: (x["area"], x["name"])):
        args, guessed = arguments(t, ids, found)
        if args is None:
            need = [p["name"] for p in t["params"] if p["required"]]
            rec(t["name"], None, f"needs {', '.join(need)}, which this run has none of")
            continue
        kind, out, raw, ms = tool(t["name"], args)
        if kind == "crashed":
            rec(t["name"], False, f"a server error: {out}", ms, f"tools/call {t['name']} {json.dumps(args)[:300]}", raw)
        elif kind == "refused" and not guessed:
            rec(t["name"], False, f"refused with the run's own data: {out}", ms, f"tools/call {t['name']} {json.dumps(args)[:300]}", raw)
        else:
            rec(t["name"], True, f"said: {out}"[:300] if kind == "refused" else f"answered ({len(json.dumps(out, default=str))} bytes)", ms)

    # a change through MCP is the person's own uncommitted change (in the run's second model)
    m2, name = ids.get("other_model") or ids.get("model", ""), f"Self-test MCP application {ids.get('sid', '')}"
    kind, out, raw, ms = tool("add_entities", {"model": m2, "entity_type": "ApplicationComponent", "rows": [{"name": name}]})
    kind2, out2, raw2, _ = tool("list_my_changes", {"model": m2})
    mine = name in json.dumps(out2, default=str)
    rec("a change is the person's uncommitted one", kind == "ok" and kind2 == "ok" and mine,
        f"added: {kind}; in list_my_changes: {mine}", ms, "add_entities; list_my_changes", raw + raw2)

    # a read-only token reads, and changes nothing
    ro = ""
    if read_only_token:
        try:
            ro = read_only_token()
        except Exception as exc:  # noqa: BLE001 - said, the check is skipped
            rec("a read-only token changes nothing", None, f"no read-only token could be made: {exc}")
    if ro:
        k1, _o1, r1, ms = tool("list_models", {}, ro)
        ro_name = f"Self-test read-only {ids.get('sid', '')}"
        k2, o2, r2, _ = tool("add_entities", {"model": m2, "entity_type": "ApplicationComponent", "rows": [{"name": ro_name}]}, ro)
        k3, o3, _r3, _ = tool("search_entities", {"text": ro_name, "model": m2})
        added = ro_name in names_in(o3)
        rec("a read-only token changes nothing", k1 == "ok" and k2 == "refused" and not added,
            f"read: {k1}; add: {k2} ({str(o2)[:120]}); added: {added}", ms, "list_models; add_entities as read-only", r1 + r2)
    elif not read_only_token:
        rec("a read-only token changes nothing", None, "no way to make a read-only token here")

    # the wrong role is refused
    if other:
        k1, o1, r1, ms = tool("ops_status", {}, other)
        k2, o2, r2, _ = tool("maturity_overview", {}, other)
        rec("the wrong role is refused", k1 == "refused" and k2 == "refused", f"ops_status: {k1} ({str(o1)[:100]}); "
            f"maturity_overview: {k2} ({str(o2)[:100]})", ms, "ops_status, maturity_overview without the role", r1 + r2)
    else:
        rec("the wrong role is refused", None, "no account without the role")

    # every call is in the AI activity log
    t0 = time.time()
    s, text = send(base, "get", "/api/v1/mcp/activity?days=1&limit=1000&tool=add_entities", admin, None)
    try:
        log = json.loads(text) if text else {}
    except ValueError:
        log = {}
    rows = log.get("calls") or log.get("items") or log.get("rows") or []
    seen = name in text or any("add_entities" in json.dumps(r) for r in rows)
    rec("every call is in the AI activity log", s == 200 and seen, f"{s}: {len(rows)} add_entities call(s) today", int((time.time() - t0) * 1000),
        "GET /api/v1/mcp/activity", text[:1000])
    return counts
