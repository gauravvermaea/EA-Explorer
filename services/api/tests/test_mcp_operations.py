"""R4.22 (owner, 14 Nov 2026: "we need mcp tools for ai to be able to do operational stuff like backup restore add more
servers find what is slwoing down things, move old and unduser projecs and models into arcive"): the operations tools
through MCP. No database or operations helper needed: both are faked."""

from __future__ import annotations

import inspect
import types

import anyio
import pytest

pytest.importorskip("mcp")

from test_mcp_ops import FakeEngine  # noqa: E402

from eax import mcp_operations as mo  # noqa: E402
from eax import mcp_ops as ops  # noqa: E402
from eax import mcp_server as ms  # noqa: E402
from eax import permissions as perms  # noqa: E402
from eax.metamodel_edit import EditError  # noqa: E402

READING = {"ops_status", "ops_resources", "ops_find_slow", "ops_logs", "ops_backups", "ops_unused", "ops_alerts"}
CHANGING = {"ops_backup", "ops_restore", "ops_scale", "ops_archive"}


def _tools() -> dict:
    return {t.name: t for t in ms.mcp._tool_manager.list_tools()}


def _as(name="user_it_admin", roles=("it-admin",)):
    return perms.current.set(perms.Principal(name, roles))


@pytest.fixture
def world(monkeypatch):
    """A fake database (the preview store) and a fake operations helper that records what it is asked."""
    eng = FakeEngine()
    monkeypatch.setattr(ops, "get_engine", lambda: eng)
    monkeypatch.setattr(ms, "get_engine", lambda: eng)
    audits = []                                     # mcp_ops and mcp_operations share eax.audit
    monkeypatch.setattr(mo.audit, "record", lambda conn, **k: audits.append(k))
    calls = []
    answers = {("GET", "/servers"): {"servers": [{"number": 1, "state": "running"}], "wanted": 1, "max": 16, "busy": False},
               ("GET", "/restores"): {"active": {"active": False}},
               ("GET", "/backups"): {"infrastructure": [{"name": "2026-11-14_0900_nightly", "tag": "nightly", "created": "x",
                                                         "version": "3.5.0"}], "restore_choices": {"databases": "Databases only"}},
               ("POST", "/servers"): {"started": True}, ("POST", "/backups/restore"): {"started": True}}

    def helper(method, path, body=None, timeout=20):
        calls.append((method, path, body))
        return answers[(method, path.split("?")[0])]
    monkeypatch.setattr(mo, "helper", helper)
    monkeypatch.setattr(mo, "test_run", lambda: None)
    return types.SimpleNamespace(engine=eng, calls=calls, audits=audits, answers=answers)


def _call(tool, **kw):
    return anyio.run(lambda: _tools()[tool].fn(**kw))


# ---------------------------------------------------------------- the tools, and what they never do
def test_r4_22_the_tools_are_there_and_every_changing_one_confirms():
    tools = _tools()
    assert READING | CHANGING <= set(tools) and set(mo.TOOLS) == READING | CHANGING
    for n in CHANGING:
        params = inspect.signature(tools[n].fn).parameters
        assert params["confirm"].default == "" and "why" in params, n
    for n in READING:
        assert "confirm" not in inspect.signature(tools[n].fn).parameters, n
    from eax import mcp_catalogue as mc
    by = {t["name"]: t for t in mc.tools()}
    assert all(by[n]["changes"] for n in CHANGING) and not any(by[n]["changes"] for n in READING)
    assert mc.AREAS["mcp_operations"] == "Running the installation"


def test_r4_22_nothing_is_deleted_through_mcp():
    src = inspect.getsource(mo)
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith(("#", '"')))
    assert '"state": "archived"' in code and '"deleted"' not in code and "purge" not in code.lower()
    # a TOGAF role (skills_by_togaf_role, R12) is a job in the TOGAF skills framework, not a sign-in role
    assert not any(w in n.replace("togaf_role", "togaf") for n in _tools() for w in ("delete", "purge", "credential", "role"))


def test_r4_22_for_super_and_it_admins_only(world):
    tok = _as("user_architect", ("user", "model-creator"))
    try:
        for tool, kw in (("ops_status", {}), ("ops_logs", {"service": "api"}), ("ops_unused", {}), ("ops_scale", {"count": 2})):
            assert "Super Admins and IT Admins" in _call(tool, **kw)["error"], tool
        assert not [c for c in world.calls if c[0] == "POST"]
    finally:
        perms.current.reset(tok)


# ---------------------------------------------------------------- preview, then confirm: adding servers
def test_r4_22_add_servers_previews_then_changes_once_confirmed(world):
    tok = _as()
    try:
        first = _call("ops_scale", count=3, why="it is slow")
        assert "1 run now, so add 2" in first["preview"]["will"] and first["confirm"].startswith("pv_")
        assert not [c for c in world.calls if c[0] == "POST"]                          # nothing changed yet
        done = _call("ops_scale", count=3, confirm=first["confirm"], why="it is slow")
        assert done["done"] and ("POST", "/servers", {"count": 3, "by": "user_it_admin"}) in world.calls
        acts = {a["action"]: a for a in world.audits}                                  # the screens' line and MCP's own
        assert acts["system.servers"]["source"] == "mcp" and acts["mcp.ops_scale"]["source"] == "mcp"
        assert "between 1 and 16" in _call("ops_scale", count=40)["error"].lower()
    finally:
        perms.current.reset(tok)


def test_r4_22_a_read_only_credential_changes_nothing(world):
    tok = _as("user_super_admin", ("super-admin",))
    mach = ms._machine.set(types.SimpleNamespace(name="Reader", scopes={"mcp": "read"}))
    try:
        assert "may only read" in _call("ops_scale", count=2)["error"] and not world.calls
    finally:
        ms._machine.reset(mach)
        perms.current.reset(tok)


# ---------------------------------------------------------------- nothing changes while the self-test or a restore runs
def test_r4_22_refused_while_a_self_test_or_restore_runs(world, monkeypatch):
    tok = _as()
    try:
        monkeypatch.setattr(mo, "test_run", lambda: {"id": 42, "state": "running", "by": "owner"})
        assert "Self-test run 42 is running" in _call("ops_scale", count=2)["error"]
        monkeypatch.setattr(mo, "test_run", lambda: None)
        world.answers[("GET", "/restores")] = {"active": {"active": True, "by": "owner", "since": "09:00"}}
        assert "A restore is running" in _call("ops_restore", backup="2026-11-14_0900_nightly")["error"]
        assert not [c for c in world.calls if c[0] == "POST"]
    finally:
        perms.current.reset(tok)


# ---------------------------------------------------------------- restore
def test_r4_22_restore_names_a_backup_that_is_there(world):
    tok = _as()
    try:
        assert "No infrastructure backup 'nope'" in _call("ops_restore", backup="nope")["error"]
        assert "what is one of: databases" in _call("ops_restore", backup="2026-11-14_0900_nightly", what="all")["error"]
        first = _call("ops_restore", backup="2026-11-14_0900_nightly", what="databases")
        assert "Databases only" in first["preview"]["will"] and "read-only" in first["preview"]["while_it_runs"]
        done = _call("ops_restore", backup="2026-11-14_0900_nightly", what="databases", confirm=first["confirm"])
        assert done["done"] and ("POST", "/backups/restore", {"name": "2026-11-14_0900_nightly", "what": "databases",
                                                             "by": "user_it_admin", "version": mo.__version__}) in world.calls
        assert {"backup.restore.start", "mcp.ops_restore"} <= {a["action"] for a in world.audits}
        # a whole application backup: Super Admins only, as on the Backups page
        assert "needs the Super Admin role" in _call("ops_restore", backup="x", kind="application")["error"]
    finally:
        perms.current.reset(tok)


# ---------------------------------------------------------------- archive: blocked when something depends on it
def test_r4_22_archive_says_what_stops_it(world, monkeypatch):
    from eax import archive as ar
    monkeypatch.setattr(mo.repo, "get_model", lambda conn, ref: {"id": "m1", "name": "Old model", "kind": "project", "_id": 1})
    monkeypatch.setattr(ar, "_may_move", lambda conn, user, m, state: None)
    monkeypatch.setattr(ar, "references", lambda conn, ref: {"blocking": ["model Child derives from it"], "copies": [],
                                                              "open_merge_requests": 0})
    tok = _as()
    try:
        assert "cannot move while model Child derives from it" in _call("ops_archive", model="Old model")["error"]
        assert "one of them" in _call("ops_archive", model="a", project="b")["error"]
        monkeypatch.setattr(ar, "references", lambda conn, ref: {"blocking": [], "copies": [], "open_merge_requests": 0})
        started = []
        monkeypatch.setattr(mo, "_start_task", lambda kind, label, params, link, user: started.append((kind, params)) or {"task": 7})
        first = _call("ops_archive", model="Old model")
        assert "Archive model Old model" in first["preview"]["will"] and not started
        done = _call("ops_archive", model="Old model", confirm=first["confirm"])
        assert done["done"] and started == [("archive.move", {"model": "m1", "state": "archived", "note": ""})]
    finally:
        perms.current.reset(tok)


# ---------------------------------------------------------------- what slows things down
def test_r4_22_findings_worst_first_in_words():
    db = {"slow_queries": [{"query": "SELECT big", "calls": 10, "mean_ms": 2500, "max_ms": 9000},
                           {"query": "SELECT ok", "calls": 1, "mean_ms": 3, "max_ms": 3}],
          "tables": [{"schema": "core", "name": "entities", "rows": 1000, "dead_rows": 50000, "last_tidied": None}]}
    health = {"checks": {"reports": {"name": "Reports", "status": "up", "response_ms": 4000},
                         "web": {"name": "Web", "status": "up", "response_ms": 20}},
              "containers": [{"name": "eax-api-1", "memory_bytes": 950 * 1048576, "memory_limit_bytes": 1024 * 1048576,
                              "cpu_percent": 12}]}
    tasks = [{"kind": "backup.infrastructure", "label": "Nightly", "status": "running", "minutes": 40},
             {"kind": "load.add", "label": "Load", "status": "queued", "minutes": 9}]
    res = {"summary": {"paged": True, "least_available_mb": 300, "least_available_at": "t"},
           "points": [{"cache_hit_percent": 99.5}, {"cache_hit_percent": 82.0}]}
    found = mo.findings(db, health, tasks, res)
    words = [f["finding"] for f in found]
    assert words[0] == "Reports answered its health check in 4000 ms."
    assert "A query takes 2500 ms on average (10 calls, at most 9000 ms)." in words
    assert not any("SELECT ok" in str(f.get("query")) for f in found)
    assert any("core.entities has 50,000 dead rows" in w for w in words)
    assert any("eax-api-1 uses 950.0 MB of its 1024.0 MB limit" in w for w in words)
    assert any("has been running for 40 minutes" in w for w in words) and any("waited 9 minutes" in w for w in words)
    assert any("paged" in w for w in words) and any("only 300 MB" in w for w in words) and any("82.0%" in w for w in words)
    assert all("look_at" in f and "weight" not in f for f in found)
    assert mo.findings({}, {}, [], {}) == []


def test_r4_22_status_says_what_needs_attention():
    health = {"checks": {"api": {"status": "up", "response_ms": 5}, "reports": {"name": "Reports", "status": "down", "detail": "502"}},
              "containers": [{"name": "eax-reports-1", "state": "exited", "memory_bytes": None},
                             {"name": "eax-api-1", "state": "running", "memory_bytes": 300 * 1048576}],
              "filesystems": [{"label": "Work folder", "used_percent": 91}]}
    s = mo.status_of(health, {"servers": [{"state": "running"}], "wanted": 1, "max": 16}, {"active": {"active": False}}, None)
    assert "Reports: down (502)" in s["attention"] and "eax-reports-1 is exited" in s["attention"]
    assert "File system Work folder is 91% full" in s["attention"]
    assert s["servers"] == {"running": 1, "wanted": 1, "max": 16} and s["restore"] is None
    assert s["containers"][1]["memory_mb"] == 300.0
    calm = mo.status_of({"checks": {}}, {}, {}, None)
    assert calm["attention"] == ["Nothing needs attention."]


def test_r4_22_application_backups_short():
    rows = mo.application({"runs": [{"name": "a", "tag": "t", "models": [{"status": "ok"}, {"status": "failed"}], "bytes": 5}]})
    assert rows == [{"name": "a", "tag": "t", "created": None, "by": None, "bytes": 5, "pinned": None, "models": 2, "failed": 1}]


def test_r4_22_the_helper_away_is_said_not_a_server_error(monkeypatch):
    monkeypatch.setenv("EAX_OPS_URL", "http://127.0.0.1:9")
    with pytest.raises(EditError) as e:
        mo.helper("GET", "/servers", timeout=2)
    assert e.value.status == 503 and "not reachable" in str(e.value)


def test_r4_22_logs_filtered_and_the_name_kept_clean(world):
    world.answers[("GET", "/containers/api/logs")] = {"lines": ["a ERROR one", "b fine", "c error two"]}
    tok = _as()
    try:
        got = _call("ops_logs", service="api", contains="error")
        assert got == {"service": "api", "lines": ["a ERROR one", "c error two"], "count": 2}
        assert world.calls[-1][1] == "/containers/api/logs?tail=200"
        world.answers[("GET", "/containers/api....etcpasswd/logs")] = {"lines": []}
        _call("ops_logs", service="api/../../etc/passwd", tail=99999)                  # no path out of /containers/<name>
        assert world.calls[-1][1] == "/containers/api....etcpasswd/logs?tail=2000"
    finally:
        perms.current.reset(tok)
