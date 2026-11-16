"""The API container's part of the backup and restore test (R5.6-B1; owner, 16 Nov 2026, 15:21: "Create a project with some
models ... Create content in model in project and documents + custom reports and custom views invarious states, tags and
all other kind of content"; 15:36: "completly syncrhronous calling one comamnd after other within eax and calling the
require apis").

`eax test backup-restore` (eaxcli/backup_restore.py, on the host) runs these one after another, each waited for:
`docker compose exec -T api python -m eax.testing.backup_restore <command>`, the test's state as JSON on standard input,
one JSON line at the end of standard output (what happened is printed before it):

  start     the test's record (a self-test run in the tests database, so it shows in Self-test's history and its data is
            removed like any self-test data), its accounts (a Super Admin and an Architect, each with a one-day token:
            people and roles made between B1 and B2, S1), the models and the project as every self-test run makes them
            (self_test_<id>_1 with entities, relationships, a drawn view and a line attribute; self_test_<id>_2 its child;
            self_test_<id>_3 the project), then content of every other kind through the REST API and the MCP server as
            the test's Super Admin: a tag, an uncommitted change, the child model's own change, a KPI, a custom view,
            project steps, a key question, a stakeholder and a discussion, a Business Model Canvas, a document class with
            a document (its file), an ADR linked to an element and a dispensation, and a discovery project with a source
            and a whole run (Found in, a skipped item, a decision found) (S3)
  snapshot  what the test made, read from the databases: each kind's rows and a checksum over them (models and projects
            as the old restore suite fingerprinted them); used to say "gone" after B1 and "back, the same" after B2
  after     after B2 is back: the test's accounts sign in (S1); search finds the restored elements and the KPI counts them
            (S4); work goes on, numbering carried on (a new element, a commit, a tag, a document, a new ADR numbered after
            the last, S5); no job ran twice, none left running, the recurring ones run again (S6); every document of the
            project downloads with the checksum of the file uploaded (S7)
  idle      waits until the background has finished what it was doing (a project's repository being built in
            Documents, a template library loading, any job running or due that is not a recurring one skipping its turn),
            at most half an hour: taken before each backup, so a backup never catches work half done (the owner's run,
            16 Nov 2026, 23:09)
  finish    the results recorded on the test's record, the test's data removed (the self-test's purge: the models, the
            project, the accounts, the discovery project and the decision records named for the test; the custom view),
            the record closed

Nothing here is a background task: each command does its part and returns."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from . import fixtures, store
from .api_writes import call, upload
from .discovery_projects_check import ADR_FIELDS, DISP_FIELDS, mcp_call, mcp_url

API = __import__("os").environ.get("EAX_TEST_API_URL", "http://api:8000")
ROLES = ["super-admin", "architect"]


def doc_text(sid: str) -> bytes:
    """The test document's file (pure)."""
    return f"EA Explorer backup and restore test document {sid}\n".encode()


def say(msg: str) -> None:
    """A line of what is happening (standard error, so the JSON at the end stays alone on standard output)."""
    print(msg, file=sys.stderr, flush=True)


def digest(rows) -> str:
    """A checksum over rows (pure)."""
    h = hashlib.sha256()
    for r in rows:
        h.update(("\x1f".join("" if v is None else str(v) for v in r) + "\x1e").encode("utf-8"))
    return h.hexdigest()[:16]


def view_code(sid: str) -> str:
    """The custom view's code for the test: OVT-<number from its id> (pure)."""
    return f"OVT-{int(sid[:6], 16) % 100000}"


# ---------------------------------------------------------------- the models and projects (from the old restore suite, R3.8)
def fingerprint(engine, models: list[str], projects: list[str]) -> dict:
    """{model guid: {entities, relationships, attributes, sum}, "project:<guid>": {...}}: the content compared after
    each restore. Ids change when a model is made again, so the checksum is over guids, names and values only."""
    out: dict[str, dict] = {}
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
        for g in models:
            m = conn.execute(text("SELECT id, name FROM core.models WHERE guid = CAST(:g AS uuid) AND NOT is_deleted"),
                             {"g": g}).first()
            if not m:
                out[g] = {"missing": True}
                continue
            ents = conn.execute(text("""SELECT e.guid::text, e.name, coalesce(e.description, '') FROM core.entities e
                                         WHERE e.model_id = :m AND NOT e.is_deleted ORDER BY e.guid"""), {"m": m[0]}).all()
            rels = conn.execute(text("""SELECT r.guid::text, s.guid::text, t.guid::text, coalesce(r.name, '')
                                          FROM core.relationships r JOIN core.entities s ON s.id = r.source_entity_id
                                          JOIN core.entities t ON t.id = r.target_entity_id
                                         WHERE r.model_id = :m AND NOT r.is_deleted ORDER BY r.guid"""), {"m": m[0]}).all()
            vals = conn.execute(text("""SELECT v.guid::text, v.value_text, v.value_number, v.value_date, v.value_bool
                                          FROM core.attribute_values v WHERE v.model_id = :m AND NOT v.is_deleted
                                         ORDER BY v.guid"""), {"m": m[0]}).all()
            out[g] = {"name": m[1], "entities": len(ents), "relationships": len(rels), "attributes": len(vals),
                      "sum": digest([("m", m[1]), *ents, *rels, *vals])}
        for p in projects:
            try:
                row = conn.execute(text("SELECT id, name FROM proj.projects WHERE guid = CAST(:g AS uuid)"), {"g": p}).first()
            except Exception:  # noqa: BLE001 - the projects in a database of their own (R2.50): not fingerprinted here
                out[f"project:{p}"] = {"skipped": "the projects are in a database of their own"}
                continue
            if not row:
                out[f"project:{p}"] = {"missing": True}
                continue
            steps = conn.execute(text("SELECT phase, seq, name, coalesce(done_note, '') FROM proj.steps WHERE project_id = :p "
                                      "AND NOT removed ORDER BY phase, seq, name"), {"p": row[0]}).all()
            items = conn.execute(text("SELECT phase, name, kind FROM proj.items WHERE project_id = :p ORDER BY phase, name, kind"),
                                 {"p": row[0]}).all()
            people = conn.execute(text("SELECT lower(username), role FROM proj.members WHERE project_id = :p ORDER BY 1, 2"),
                                  {"p": row[0]}).all()
            out[f"project:{p}"] = {"name": row[1], "steps": len(steps), "items": len(items), "members": len(people),
                                   "sum": digest([("p", row[1]), *steps, *items, *people])}
    return out


def compare(before: dict, after: dict) -> list[str]:
    """What differs, in words (empty: the same)."""
    diffs = []
    for key, b in before.items():
        a = after.get(key) or {"missing": True}
        if b.get("skipped"):
            continue
        if a.get("missing") and not b.get("missing"):
            diffs.append(f"{b.get('name') or key} is missing")
            continue
        for k in ("name", "entities", "relationships", "attributes", "steps", "items", "members"):
            if k in b and a.get(k) != b.get(k):
                diffs.append(f"{b.get('name') or key}: {k} {b.get(k)} before, {a.get(k)} after")
        if b.get("sum") != a.get("sum") and not any(d.startswith(f"{b.get('name') or key}:") for d in diffs):
            diffs.append(f"{b.get('name') or key}: the content differs (same counts)")
    return diffs


# ---------------------------------------------------------------- talking to the API and MCP
class Api:
    """REST and MCP calls as one account; every call kept as (what, status) for the report (no token, no answer body)."""

    def __init__(self, token: str, base: str = API):
        self.token, self.base, self.calls = token, base, []

    def rest(self, method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
        """One REST call as the account: its status and its answer."""
        s, d = call(self.base, method, path, self.token, body)
        self.calls.append([f"{method.upper()} {path}", s])
        return s, d if isinstance(d, (dict, list)) else {"text": str(d)[:500]}

    def tool(self, name: str, args: dict) -> tuple[int, Any]:
        """One MCP tool call over HTTP as the account: its status and its answer."""
        s, out, _raw = mcp_call(mcp_url(self.base), self.token, name, args)
        self.calls.append([f"MCP {name}", s])
        return s, out

    def tool_confirmed(self, name: str, args: dict) -> tuple[int, Any]:
        """A tool that previews first (it answers a confirm token): called again with the token, as an AI does once the
        person agrees (the owner's run, 16 Nov 2026: the KPI was only previewed, never added)."""
        s, out = self.tool(name, args)
        if s == 200 and isinstance(out, dict) and out.get("confirm") and not out.get("error"):
            s, out = self.tool(name, {**args, "confirm": out["confirm"]})
        return s, out

    def upload(self, path: str, name: str, content: bytes) -> tuple[int, Any]:
        """One file upload as the account: its status and its answer."""
        s, d = upload(self.base, path, self.token, name, content)
        self.calls.append([f"POST {path} (file)", s])
        return s, d

    def download(self, path: str) -> tuple[int, bytes]:
        """One file downloaded as the account: its status and its bytes."""
        from ..service_split import route
        req = urllib.request.Request(route(self.base, path) + path, headers={"Authorization": f"Bearer {self.token}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:     # noqa: S310 - the installation's own API
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, b""
        except (urllib.error.URLError, TimeoutError, OSError):
            return 599, b""


def _ok(made: list, what: str, good: bool, detail: str = "") -> bool:
    made.append({"what": what, "ok": bool(good), "detail": str(detail)[:300]})
    say(f"  {'made' if good else 'NOT MADE'}: {what}{' - ' + str(detail)[:200] if detail and not good else ''}")
    return bool(good)


def _err(out: Any) -> str:
    """A tool's refusal ({"error": ...}); its "message" is what it did, not an error (the owner's run, 16 Nov 2026,
    21:11: "Step added to phase A" was taken for a failure)."""
    return str(out.get("error") or "") if isinstance(out, dict) else ("" if out is None else str(out)[:200])


def _why(out: Any) -> str:
    """What a call said, for the report: its error, else its message."""
    return str(out.get("error") or out.get("message") or "") if isinstance(out, dict) else ("" if out is None else str(out)[:200])


# ---------------------------------------------------------------- start: the content
def start(state: dict) -> dict:
    """The test's record, accounts, models, project and the content of every other kind (see the module)."""
    from ..db import get_engine
    engine, repo = store.engine(), get_engine()
    by = state.get("by") or "eax test backup-restore"
    with engine.begin() as conn:
        run_id = store.create_run(conn, by, "eax", ["restore"], state.get("folder", ""), state.get("version", ""), "detailed")
        store.set_state(conn, run_id, state="running", step="backup and restore test")
        run = dict(conn.execute(text("SELECT id, run_guid::text AS run_guid, started_by FROM tests.test_runs WHERE id = :id"),
                                {"id": run_id}).mappings().first())
    sid = store.short(run["run_guid"])
    say(f"the test's record: self-test run {run_id} ({sid})")
    with repo.begin() as conn:
        tokens = fixtures.accounts(conn, run, by, ROLES, say)
    ids = fixtures.models_and_project(repo, run, by, ROLES, say)
    with engine.begin() as conn:
        store.set_fixture_ids(conn, run_id, ids)
    a = Api(tokens["super-admin"])
    made: list[dict] = []
    m1, m2, proj = ids.get("model", ""), ids.get("other_model", ""), ids.get("project", "")
    extra: dict[str, str] = {}

    s, out = a.tool("tag_model", {"model": m1, "name": f"self_test_{sid} tag", "description": "backup and restore test"})
    _ok(made, "a tag on the model", s == 200 and not _err(out), _why(out))
    s, out = a.tool("add_entities", {"model": m1, "entity_type": "ApplicationComponent",
                                     "rows": [{"name": f"Self-test uncommitted app {sid}"}]})
    _ok(made, "an uncommitted change in the model", s == 200 and isinstance(out, dict) and out.get("saved", 0) >= 1, _why(out))
    s, out = a.tool("add_entities", {"model": m2, "entity_type": "Capability", "rows": [{"name": f"Self-test child capability {sid}"}]})
    s2, out2 = a.tool("commit_my_changes", {"model": m2, "message": f"self_test_{sid} child change"})
    _ok(made, "the child model's own committed change", s == 200 and not _err(out) and not _err(out2),
        _err(out) or _err(out2) or _why(out2))
    s, out = a.tool_confirmed("add_own_kpi", {"model": m1, "name": f"Self-test applications {sid}", "kind": "count",
                                    "entity_type": "ApplicationComponent"})
    _ok(made, "a KPI (a custom report figure)", s == 200 and not _err(out), _why(out))
    code = view_code(sid)
    s, out = a.rest("post", "/api/v1/views", {"code": code, "name": f"self_test_{sid} view", "category": "Organisation",
                                              "purpose": "backup and restore test", "element_types": ["ApplicationComponent", "Capability"]})
    if _ok(made, "a custom view", s in (200, 201), _why(out)):
        extra["view_code"] = code
    if proj:
        s, out = a.tool("add_project_step", {"project": proj, "phase": "A", "name": f"self_test_{sid} step"})
        _ok(made, "a project step", s == 200 and not _err(out), _why(out))
        s, out = a.tool("save_key_question", {"project": proj, "question": f"Self-test key question {sid}?", "asked_by": "Self-test"})
        _ok(made, "a key question", s == 200 and not _err(out), _why(out))
        s, out = a.tool("save_stakeholder", {"project": proj, "name": f"Self-test stakeholder {sid}"})
        sh = (out or {}).get("id") if isinstance(out, dict) else None        # a discussion is noted by the stakeholder's id
        s2, out2 = a.tool("note_stakeholder_discussion", {"project": proj, "stakeholder": sh or "",
                                                           "html": "<p>Backup and restore test discussion.</p>", "title": "Self-test"})
        _ok(made, "a stakeholder and a discussion", s == 200 and bool(sh) and s2 == 200 and not _err(out2),
            _err(out) or _err(out2) or _why(out2))
        s, out = a.tool("change_business_model_canvas", {"project": proj, "action": "new", "name": f"self_test_{sid} canvas"})
        _ok(made, "a Business Model Canvas", s == 200 and not _err(out), _why(out))
        s, out = a.tool("add_document_class", {"project": proj, "phase": "A", "name": f"self_test_{sid} documents"})
        item = (out or {}).get("id") or (out or {}).get("item") if isinstance(out, dict) else None
        if _ok(made, "a document class", s == 200 and bool(item), _why(out)):
            content = doc_text(sid)
            extra["item"] = str(item)
            s, d = _upload_waiting(a, f"/api/v1/projects/{proj}/items/{item}/documents", f"self_test_{sid}.txt", content)
            doc = (d or {}).get("id") if isinstance(d, dict) else None
            if _ok(made, "a document with its file", s in (200, 201) and bool(doc), _why(d)):
                extra.update(document=str(doc), document_sha=hashlib.sha256(content).hexdigest())
    s, out = a.rest("post", "/api/v1/governance", {"kind": "Architecture Decision Record", "title": f"self_test_{sid} decision",
                                                   "owner": "Self-test", "record_type": "Architecture", "fields": ADR_FIELDS})
    if _ok(made, "an ADR", s == 201 and bool((out or {}).get("ref")), _why(out)):
        extra.update(adr=out["id"], adr_ref=out["ref"])
        if ids.get("entity"):
            s, o2 = a.rest("post", f"/api/v1/governance/records/{out['id']}/links",
                           {"kind": "element", "relation": "affects", "target": ids["entity"], "model": m1})
            _ok(made, "the ADR linked to an element", s == 201, _why(o2))
    s, out = a.rest("post", "/api/v1/governance", {"kind": "Dispensation", "title": f"self_test_{sid} waiver", "owner": "Self-test",
                                                   "sponsor": "Self-test sponsor", "fields": DISP_FIELDS,
                                                   "expires_on": str(date.today() + timedelta(days=30))})
    _ok(made, "a dispensation", s == 201, _why(out))
    _discovery(a, made, m1, sid)
    out = {"run_id": run_id, "sid": sid, "ids": {**ids, **extra}}
    _read_back(made, out, bool(proj))
    return {"run_id": run_id, "sid": sid, "token": tokens["super-admin"], "architect": tokens.get("architect", ""),
            "ids": {**ids, **extra}, "made": made, "calls": a.calls}


def _upload_waiting(a: Api, path: str, name: str, content: bytes, seconds: int = 300) -> tuple[int, Any]:
    """An upload, tried again for up to five minutes while the document class's folder is still being made in Documents."""
    end = time.time() + seconds
    while True:
        s, d = a.upload(path, name, content)
        if s in (200, 201) or time.time() > end or s in (401, 403):
            return s, d
        time.sleep(10)


# what each kind of content is called in the snapshot, and what the report calls it
READ_BACK = {"tags": "the tags", "kpis": "the KPI", "views": "the custom view", "accounts": "the test's accounts",
             "discovery": "the discovery project", "found_in": "Found in", "gov_records": "the ADR and the dispensation"}
READ_BACK_PROJECT = {"documents": "the document", "key_questions": "the key question", "stakeholders": "the stakeholder",
                     "canvases": "the Business Model Canvas"}


def _read_back(made: list, state: dict, project: bool) -> None:
    """Everything the test made, read back from the databases: a call that answered well but kept nothing (a preview
    never confirmed, a message mistaken for a result) fails here, not after the restores."""
    snap = snapshot(state)
    want = {**READ_BACK, **(READ_BACK_PROJECT if project else {})}
    for k, label in want.items():
        v = snap.get(k) or {}
        _ok(made, f"read back: {label}", bool(v.get("rows")), v.get("error") or ("" if v.get("rows") else "not in the database"))
    for g, v in (snap.get("models") or {}).items():
        _ok(made, f"read back: {v.get('name') or g}", not v.get("missing") and not v.get("skipped"), "missing" if v.get("missing") else "")


def _discovery(a: Api, made: list, model: str, sid: str) -> None:
    name = f"self_test_{sid}_discovery"
    s, d = a.rest("post", "/api/v1/discovery-projects", {"name": name, "target_model": model, "purpose": "Backup and restore test",
                                                         "read_default": "new", "gone_default": "mark", "schedule": "none"})
    if not _ok(made, "a discovery project", s == 201 and bool((d or {}).get("id")), _why(d)):
        return
    s, d2 = a.rest("post", f"/api/v1/discovery-projects/{d['id']}/sources",
                   {"kind": "git", "name": "Self-test repository", "location": "https://git.example.com/self-test.git", "sign_in": "key"})
    _ok(made, "a discovery source", s == 201, _why(d2))
    s, out = a.tool("run_discovery_project", {"project": name, "read": "all", "gone": "mark", "ai_client": "EA Explorer backup and restore test"})
    run = (out or {}).get("run") if isinstance(out, dict) else None
    if not _ok(made, "a discovery run (the model tagged before it)", bool(run), _why(out)):
        return
    found = f"Self-test discovered app {sid}"
    a.tool("add_entities", {"model": model, "entity_type": "ApplicationComponent", "rows": [{"name": found}]})
    s, out = a.tool("discovery_record_found", {"run": run, "items": [{"element": found, "kind": "entity", "source": "Self-test repository",
                                                                      "item": "README.md", "place": "line 1"}]})
    _ok(made, "Found in kept for an element", isinstance(out, dict) and out.get("recorded") == 1, _why(out))
    s, out = a.tool("discovery_report_skipped", {"run": run, "items": [{"source": "Self-test repository",
                                                                        "title": f"self_test_{sid} board pack.docx"}]})
    _ok(made, "an item skipped (NOT FOR AI), by title", isinstance(out, dict) and out.get("recorded") == 1, _why(out))
    s, out = a.tool("discovery_finish_run", {"run": run, "summary": "Backup and restore test run."})
    _ok(made, "the discovery run finished (committed, tagged after)",
        isinstance(out, dict) and (out.get("run") or {}).get("status") == "finished", _why(out))


# ---------------------------------------------------------------- snapshot: what the test made, as it is now
def snapshot(state: dict) -> dict:
    """Each kind of what the test made: rows and a checksum (an empty dict for a kind with nothing: gone)."""
    from .. import projects as pj
    from ..db import get_engine
    repo = get_engine()
    sid, ids = state["sid"], state.get("ids", {})
    like = f"self\\_test\\_{sid}%"
    models = [g for g in (ids.get("model"), ids.get("other_model")) if g]
    projects = [g for g in (ids.get("project"),) if g]
    out: dict[str, Any] = {"models": fingerprint(repo, models, projects)}
    core = {
        "tags": ("SELECT t.name, t.description FROM core.model_tags t JOIN core.models m ON m.id = t.model_id "
                 "WHERE m.name LIKE :like ORDER BY 1, 2"),
        "kpis": "SELECT name, kind FROM core.kpi_definitions WHERE name LIKE :kpi ORDER BY 1",
        "views": "SELECT code, name FROM core.viewpoints WHERE code = :code",
        "accounts": "SELECT username, name FROM core.service_accounts WHERE username LIKE :svc ORDER BY 1",
        "discovery": ("SELECT p.name, (SELECT count(*) FROM core.discovery_resources r WHERE r.project_id = p.id), "
                      "(SELECT count(*) FROM core.discovery_runs r WHERE r.project_id = p.id) FROM core.discovery_projects p "
                      "WHERE p.name LIKE :like ORDER BY 1"),
        "found_in": ("SELECT f.item, f.place FROM core.discovery_found_in f JOIN core.discovery_runs r ON r.id = f.run_id "
                     "JOIN core.discovery_projects p ON p.id = r.project_id WHERE p.name LIKE :like ORDER BY 1, 2"),
    }
    params = {"like": like, "kpi": f"Self-test applications {sid}", "code": view_code(sid), "svc": f"svc-self-test-{sid}-%"}
    with repo.begin() as conn:
        conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
        for k, q in core.items():
            out[k] = _rows(conn, q, params)
    proj = {
        "gov_records": "SELECT ref, kind, title, status FROM proj.gov_records WHERE title LIKE :like ORDER BY 1",
        "documents": ("SELECT d.folder, d.mayan_document_id FROM proj.documents d JOIN proj.projects p ON p.id = d.project_id "
                      "WHERE p.name LIKE :like ORDER BY 1, 2"),
        "key_questions": ("SELECT q.question FROM proj.key_questions q JOIN proj.projects p ON p.id = q.project_id "
                          "WHERE p.name LIKE :like ORDER BY 1"),
        "stakeholders": ("SELECT s.name FROM proj.stakeholders s JOIN proj.projects p ON p.id = s.project_id "
                         "WHERE p.name LIKE :like ORDER BY 1"),
        "canvases": ("SELECT c.name, c.kind FROM proj.canvases c JOIN proj.projects p ON p.id = c.project_id "
                     "WHERE p.name LIKE :like ORDER BY 1"),
    }
    try:
        with pj.connections() as pc:
            for k, q in proj.items():
                out[k] = _rows(pc, q, params)
    except Exception as exc:  # noqa: BLE001 - projects switched off: said, not compared
        out["projects_note"] = f"the projects could not be read: {exc}"[:300]
    return out


def _rows(conn, q: str, params: dict) -> dict:
    try:
        rows = [tuple(r) for r in conn.execute(text(q), params).all()]
    except Exception as exc:  # noqa: BLE001 - a part switched off or not migrated: said in the snapshot
        return {"error": str(exc).splitlines()[0][:200]}
    return {"rows": len(rows), "sum": digest(rows)} if rows else {}


def present(snap: dict) -> list[str]:
    """What of the test's content is there (pure): every kind with rows, every model or project not missing."""
    out = [k for k, v in snap.items() if isinstance(v, dict) and v.get("rows")]
    out += [v.get("name") or k for k, v in (snap.get("models") or {}).items() if isinstance(v, dict) and not v.get("missing")
            and not v.get("skipped")]
    return out


def differences(before: dict, after: dict) -> list[str]:
    """What differs between two snapshots, in words (pure)."""
    diffs = compare(before.get("models") or {}, after.get("models") or {})
    for k, b in before.items():
        if k == "models" or not isinstance(b, dict) or b.get("error"):
            continue
        a = after.get(k) or {}
        if b != a:
            diffs.append(f"{k}: {b.get('rows', 0)} row(s) before, {a.get('rows', 0)} after" if b.get("rows") != a.get("rows")
                         else f"{k}: the same rows, different content")
    return diffs


# ---------------------------------------------------------------- after B2 is back
def after(state: dict) -> dict:
    """S1, S4, S5, S6, S7 (see the module): [{scenario, check, ok, detail}]."""
    checks: list[dict] = []

    def rec(scn: str, name: str, ok: bool | None, detail: str = "") -> None:
        checks.append({"scenario": scn, "check": name, "ok": ok, "detail": str(detail)[:400]})
        say(f"  {'ok  ' if ok else 'skip' if ok is None else 'FAIL'} {scn} {name}{': ' + str(detail)[:160] if detail else ''}")

    sid, ids = state["sid"], state.get("ids", {})
    a = Api(state["token"])
    m1 = ids.get("model", "")
    # S1: the test's accounts sign in again (their tokens were made between B1 and B2)
    s, _ = a.rest("get", "/api/v1/search?q=self&limit=1")
    rec("S1", "the test's Super Admin account signs in", s == 200, f"{s}")
    if state.get("architect"):
        s, _ = Api(state["architect"]).rest("get", "/api/v1/search?q=self&limit=1")
        rec("S1", "the test's Architect account signs in", s == 200, f"{s}")
    # S4: what is worked out from the data
    s, d = a.rest("get", f"/api/v1/search?q={urllib.request.quote('Self-test application 1')}&model={m1}")
    hits = d.get("results") or d.get("items") or d.get("entities") or [] if isinstance(d, dict) else []
    rec("S4", "search finds a restored element", s == 200 and bool(hits), f"{s}, {len(hits)} found")
    s, out = a.tool("kpi_trend", {"model": m1, "kpi": f"Self-test applications {sid}"})
    rec("S4", "the KPI is read from the restored model", s == 200 and not _err(out), _why(out) or "read")
    # S5: work goes on, the numbering carried on
    s, out = a.tool("add_entities", {"model": m1, "entity_type": "ApplicationComponent", "rows": [{"name": f"Self-test after restore {sid}"}]})
    rec("S5", "a new element", s == 200 and isinstance(out, dict) and out.get("saved", 0) >= 1, _why(out))
    s, out = a.tool("commit_my_changes", {"model": m1, "message": f"self_test_{sid} after the restore"})
    rec("S5", "a commit", s == 200 and "duplicate key" not in _err(out), _why(out) or "committed")
    s, out = a.tool("tag_model", {"model": m1, "name": f"self_test_{sid} tag after"})
    rec("S5", "a tag", s == 200 and not _err(out), _why(out))
    s, out = a.rest("post", "/api/v1/governance", {"kind": "Architecture Decision Record", "title": f"self_test_{sid} decision after",
                                                   "owner": "Self-test"})
    before_n, now_n = _ref_number(ids.get("adr_ref", "")), _ref_number((out or {}).get("ref", "") if isinstance(out, dict) else "")
    rec("S5", "a new ADR, numbered after the last", s == 201 and now_n > before_n, f"{ids.get('adr_ref')} then {(out or {}).get('ref')}")
    if ids.get("document") and ids.get("project"):
        # S7: the document's record and its file came back together (Documents may still be starting: waited for)
        end, s, body = time.time() + 300, 0, b""
        while time.time() < end:
            s, body = a.download(f"/api/v1/projects/{ids['project']}/documents/{ids['document']}")
            if s == 200:
                break
            time.sleep(10)
        same = hashlib.sha256(body).hexdigest() == ids.get("document_sha")
        rec("S7", "the document's file downloads with the checksum it was uploaded with", s == 200 and same, f"{s}, same={same}")
        s, d = _upload_waiting(a, f"/api/v1/projects/{ids['project']}/items/{ids.get('item')}/documents",
                               f"self_test_{sid}_after.txt", b"EA Explorer backup and restore test, after the restore\n")
        rec("S5", "a document uploaded", s in (200, 201), f"{s} {_why(d)}")
    else:
        rec("S7", "the document's file downloads with its checksum", None, "no document was made")
    # S6: the jobs after a restore
    rec(*_jobs())
    return {"checks": checks, "calls": a.calls}


def _ref_number(ref: str) -> int:
    try:
        return int(str(ref).rsplit("-", 1)[-1])
    except ValueError:
        return 0


def _jobs() -> tuple[str, str, bool, str]:
    """S6: no recurring job deferred twice for one time, none left running for over half an hour."""
    from ..db import get_engine
    try:
        with get_engine().begin() as conn:
            if not conn.execute(text("SELECT to_regclass('jobs.procrastinate_jobs')")).scalar():
                return "S6", "the jobs after the restore", None, "no job queue in this database"
            conn.execute(text("SET LOCAL search_path TO jobs, public"))
            twice = conn.execute(text("""SELECT task_name, args->>'timestamp' FROM jobs.procrastinate_jobs WHERE args ? 'timestamp'
                                          GROUP BY 1, 2 HAVING count(*) > 1 LIMIT 5""")).all()
            stuck = conn.execute(text("""SELECT j.task_name FROM jobs.procrastinate_jobs j WHERE j.status = 'doing' AND EXISTS (
                                           SELECT 1 FROM jobs.procrastinate_events e WHERE e.job_id = j.id AND e.type = 'started'
                                              AND e.at < now() - interval '30 minutes') LIMIT 5""")).all()
    except Exception as exc:  # noqa: BLE001 - said
        return "S6", "the jobs after the restore", False, f"not read: {exc}"[:300]
    ok = not twice and not stuck
    return ("S6", "no job ran twice and none is left running", ok,
            "none" if ok else f"twice: {[tuple(r) for r in twice]}; running over 30 minutes: {[r[0] for r in stuck]}")


# ---------------------------------------------------------------- finish
def finish(state: dict) -> dict:
    """The results on the test's record, the test's data removed, the record closed."""
    from ..db import get_engine
    engine, repo = store.engine(), get_engine()
    run_id = int(state["run_id"])
    with engine.begin() as conn:
        for r in state.get("results") or []:
            store.add_result(conn, run_id, "restore", f"backup and restore: {r['name']}",
                             "passed" if r.get("ok") else "skipped" if r.get("ok") is None else "failed", r.get("detail", ""),
                             int(r.get("ms") or 0))
        store.finish(conn, run_id, error=state.get("error", ""))
    removed: dict[str, Any] = {}
    if state.get("ids", {}).get("view_code") and state.get("token"):
        s, _ = Api(state["token"]).rest("delete", f"/api/v1/views/{state['ids']['view_code']}")
        removed["view"] = s
    if state.get("keep"):
        return {"removed": removed, "kept": True}
    try:
        with repo.begin() as conn:
            out = fixtures.purge(conn, run_id, "eax test backup-restore")
        removed.update({k: v for k, v in out.items() if isinstance(v, int)})
    except Exception as exc:  # noqa: BLE001 - said; the next self-test run removes what is left
        removed["error"] = str(exc)[:300]
    return {"removed": removed}


# ---------------------------------------------------------------- the background finished before a backup
IDLE_WAIT = 1800          # seconds the test waits at most for the background to finish
IDLE_EVERY = 5


def busy() -> list[str]:
    """What the background is still doing that would change the data under a backup (empty when idle): a project's
    repository being built or waiting to be (its folders and template copies in Documents), a template library waiting
    to load, and any job running or due within 15 minutes that is not a recurring one skipping its turn while quiet
    (after a restore, a job waiting in the restored queue runs and changes the data the backup held).

    The owner's run, 16 Nov 2026, 23:09: B2 was taken while the test's new project's repository was still being built
    (45 of its documents); restored, the build carried on (128), so B2 never came back as it was taken."""
    from .. import projects
    from ..db import get_engine, get_projects_engine
    from ..quiet import QUIET_RUNS
    out = []
    with get_projects_engine().begin() as conn:
        for r in conn.execute(text(f"""SELECT name, repo_state FROM proj.projects
                                         WHERE repo_state = 'building' OR (repo_state = 'pending' AND repo_tries < {projects.MAX_TRIES})
                                         ORDER BY name""")).all():
            out.append(f"the documents of project {r[0]} ({r[1]})")
        n = conn.execute(text("SELECT count(*) FROM proj.template_library_uploads")).scalar()
        if n:
            out.append(f"{n} template librar{'y' if n == 1 else 'ies'} loading")
    with get_engine().begin() as conn:
        if conn.execute(text("SELECT to_regclass('jobs.procrastinate_jobs')")).scalar():
            for name, status in conn.execute(text("""SELECT task_name, status::text FROM jobs.procrastinate_jobs
                     WHERE (status = 'doing' OR (status = 'todo' AND (scheduled_at IS NULL
                                                                     OR scheduled_at <= now() + interval '15 minutes')))
                       AND (NOT args ? 'timestamp' OR task_name = ANY(:runs)) ORDER BY id LIMIT 20"""),
                                                  {"runs": sorted(QUIET_RUNS)}).all():
                out.append(f"the job {name} ({'running' if status == 'doing' else 'waiting'})")
    return out


def idle(state: dict) -> dict:
    """Waits until the background is idle (busy() empty twice in a row, IDLE_EVERY seconds apart), at most state["wait"]
    seconds (IDLE_WAIT): {"waited": s} or an error naming what is still going."""
    wait = int(state["wait"]) if state.get("wait") is not None else IDLE_WAIT
    t0 = time.time()
    calm = 0
    last: list[str] = []
    while True:
        last = busy()
        calm = calm + 1 if not last else 0
        if calm >= 2:
            return {"idle": True, "waited": round(time.time() - t0)}
        if time.time() - t0 > wait:
            return {"idle": False, "waited": round(time.time() - t0),
                    "error": f"the background did not finish within {wait // 60} minutes: " + "; ".join(last[:10])}
        time.sleep(IDLE_EVERY)


COMMANDS = {"start": start, "snapshot": snapshot, "after": after, "finish": finish, "idle": idle}


def main(argv: list[str]) -> int:
    """python -m eax.testing.backup_restore <start|snapshot|after|finish|idle> (the state as JSON on standard input)."""
    cmd = argv[0] if argv else ""
    if cmd not in COMMANDS:
        print(json.dumps({"error": f"one of {', '.join(COMMANDS)}"}))
        return 2
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        state = json.loads(raw) if raw.strip() else {}
        out = COMMANDS[cmd](state)
    except Exception as exc:  # noqa: BLE001 - said to the test, which stops there
        out = {"error": f"{type(exc).__name__}: {exc}"[:1000]}
    out["at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(json.dumps(out, default=str), flush=True)
    return 1 if out.get("error") else 0


if __name__ == "__main__":
    t0 = time.time()
    sys.exit(main(sys.argv[1:]))
