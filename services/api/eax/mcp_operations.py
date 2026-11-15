"""MCP: running the installation (Release 4, R4.22; owner, 14 Nov 2026: "we need mcp tools for ai to be able to do
operational stuff like backup restore add more servers find what is slwoing down things, move old and unduser projecs
and models into arcive").

An assistant can look at the installation the way System Admin does and, with the person's agreement, act on it:

* reading (Super Admins and IT Admins): ops_status (containers, services' health, servers, what is running),
  ops_resources (the resource history, R3.5-M8), ops_find_slow (what slows things down, in plain findings), ops_logs (a
  container's last log lines), ops_backups (every backup, and whether the web's backups are proven), ops_unused (models
  and projects nobody has used or changed for a while);
* changing, each with a preview first and confirm=<token> after (D458, mcp_ops.operate): ops_backup, ops_restore,
  ops_scale (the number of API and job servers) and ops_archive (archive a model or a project; never delete).

The same rules as the screens: the same functions and checks (the person's own roles; archiving needs the Model Admin
or Project Admin role on it as on the Archive page), every change audited with source "mcp", a machine credential needs
read-write on MCP to change anything (no new level: owner, 14 Nov 2026, "no new UI"). Nothing changes while the
self-test or a restore runs. Deleting, purging, users, roles and credentials are never done through MCP."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from . import __version__, audit, mcp_ops, permissions
from . import repository as repo
from .db import get_engine
from .mcp_server import _run, mcp
from .metamodel_edit import EditError

SLOW_CHECK_MS = 1000        # a service whose health check takes longer is listed as slow
LONG_TASK_MINUTES = 15      # a background task running longer is listed
QUEUED_MINUTES = 5          # a task waiting longer than this for the job runner is listed
MEMORY_SHARE = 0.85         # a container above this share of its memory limit is listed
UNUSED_DAYS = 180           # ops_unused's default: not used or changed for half a year (as the usage page, D371)
LOG_LINES = 2000


# ---------------------------------------------------------------- who, and whether now
def _operator(user=None):
    """Super Admins and IT Admins only (system.operate), as System Admin."""
    user = user or permissions.current.get()
    if not user or not (permissions.allowed(user.roles, "system.operate") or permissions.SUPER_ADMIN in (user.roles or ())):
        raise EditError("Running the installation through MCP is for Super Admins and IT Admins.", 403)
    return user


def helper(method: str, path: str, body: dict | None = None, timeout: int = 20) -> dict:
    """The operations helper's answer; its refusal or absence as an EditError (never a server error)."""
    url, token = os.environ.get("EAX_OPS_URL", "http://ops:8090"), os.environ.get("EAX_OPS_TOKEN", "")
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    req = urllib.request.Request(f"{url}{path}", method=method, data=data,
                                 headers={"X-Ops-Token": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            msg = json.load(exc).get("message")
        except Exception:  # noqa: BLE001
            msg = exc.reason
        raise EditError(f"The operations helper refused: {msg}", exc.code if exc.code in (400, 403, 404, 409) else 409) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EditError(f"The operations helper is not reachable ({getattr(exc, 'reason', exc)}): check that the ops "
                        "container runs.", 503) from exc


def busy(conn) -> str | None:
    """Why nothing may change now (a self-test or a restore running), or None."""
    run = test_run()
    if run:
        return (f"Self-test run {run['id']} is {run['state']} (started by {run['by']}): nothing is changed through MCP "
                "until it ends.")
    try:
        restore = helper("GET", "/restores").get("active") or {}
    except EditError:
        restore = {}
    if restore.get("active"):
        return f"A restore is running (by {restore.get('by') or 'someone'}, since {restore.get('since') or '-'}): wait for it to end."
    return None


def test_run() -> dict | None:
    """The self-test run in progress, read in the tests database (R2.28), or None."""
    from . import test_lock
    from .testing import store
    try:
        with store.engine().connect() as tc:
            return test_lock.active(tc)
    except Exception:  # noqa: BLE001 - no test tables yet: no run
        return None


def _mb(v) -> float | None:
    return round(v / 1048576, 1) if v else None


def _not_busy(conn) -> None:
    if why := busy(conn):
        raise EditError(why, 423)


def _start_task(kind: str, label: str, params: dict, link: str, user) -> dict:
    """Queues the screens' own background task (the job runner does it; without one, it is done now)."""
    from . import tasks as tk
    with get_engine().begin() as conn:
        task = tk.create(conn, kind, None, user, label, params, link)
    try:
        from .jobs import app as jobs_app
        from .jobs import run_task
        with jobs_app.open():
            job = run_task.defer(task_id=task["id"], actor=user.username, roles=list(user.roles))
        with get_engine().begin() as conn:
            tk.set_job(conn, task["id"], job)
    except Exception:  # noqa: BLE001 - no job runner: done in this call
        tk.run(task["id"], user.username, list(user.roles))
    with get_engine().connect() as conn:
        t = tk.get(conn, user, task["id"])
    return {"task": t.get("id"), "status": t.get("status"), "label": t.get("label"), "message": t.get("message") or ""}


# ---------------------------------------------------------------- reading
def _iso(v) -> Any:
    return v.isoformat(timespec="seconds") if hasattr(v, "isoformat") else v


def status_of(health: dict, servers: dict, restores: dict, test_run: dict | None) -> dict:
    """The installation now, short: each service's health, each container's state and use, what needs attention."""
    checks = health.get("checks") or {}
    containers = [{"container": c.get("name") or c.get("service"), "state": c.get("state"), "health": c.get("health"),
                   "memory_mb": _mb(c.get("memory_bytes")), "cpu_percent": c.get("cpu_percent"), "restarts": c.get("restarts")}
                  for c in health.get("containers") or []]
    attention = [f"{c.get('name') or k}: {c.get('status')} ({c.get('detail') or ''})".strip()
                 for k, c in checks.items() if (c or {}).get("status") not in ("up", "off", "ok", None)]
    attention += [str(p.get("message") if isinstance(p, dict) else p) for p in health.get("problems") or []]
    attention += [f"{c['container']} is {c['state']}" for c in containers if c["state"] not in ("running", None)]
    attention += [f"File system {f.get('label') or f.get('path')} is {f.get('used_percent')}% full"
                  for f in health.get("filesystems") or [] if (f.get("used_percent") or 0) >= 80]
    return {"version": __version__,
            "services": {k: {"status": (c or {}).get("status"), "response_ms": (c or {}).get("response_ms")} for k, c in checks.items()},
            "containers": containers,
            "servers": {"running": sum(1 for s in servers.get("servers") or [] if s.get("state") == "running"),
                        "wanted": servers.get("wanted"), "max": servers.get("max")},
            "restore": restores.get("active") if (restores.get("active") or {}).get("active") else None,
            "self_test": test_run, "attention": attention or ["Nothing needs attention."]}


@mcp.tool()
async def ops_status() -> Any:
    """The installation now (Super Admins and IT Admins): each service's health check and response time, every
    container's state, memory and CPU, the API and job servers, a restore or self-test running, and what needs
    attention. Read only."""
    def go(conn):
        from .admin_check import health_now
        _operator()
        health = health_now()
        try:
            servers = helper("GET", "/servers")
        except EditError as exc:
            servers = {"error": str(exc)}
        try:
            restores = helper("GET", "/restores")
        except EditError:
            restores = {}
        run = test_run()
        return status_of(health, servers, restores, {k: _iso(v) for k, v in run.items()} if run else None)
    return await _run(go)


@mcp.tool()
async def ops_resources(days: float = 1, start: str = "", end: str = "") -> Any:
    """The resource history (Super Admins and IT Admins): the whole installation's memory and CPU, the host's memory
    left and paging, the database's cache, each container's average and peak, over the last `days` (default 1) or
    from `start` to `end` (UTC times, e.g. 2026-11-14T09:00). What was happening (self-test, backup, restore, start-up)
    is said for each stretch. Read only."""
    def go(conn):
        from . import resources as rs
        _operator()
        a, b = rs.period(start or None, end or None, days or 1)
        h = rs.history(rs.rows_between(conn, a, b), most=48)
        per = {name: {"average_mb": round(sum(p["memory_mb"] or 0 for p in pts) / len(pts), 1) if pts else None,
                      "peak_mb": max((p["memory_peak_mb"] or 0 for p in pts), default=None),
                      "cpu_peak_percent": max((p["cpu_percent"] or 0 for p in pts), default=None)}
               for name, pts in (h.get("containers") or {}).items()}
        return {"from": a.isoformat(timespec="seconds"), "to": b.isoformat(timespec="seconds"),
                "summary": h.get("summary") or {"samples": 0, "note": "No samples in this period: is the resource history "
                                                                      "switched on (System Admin > Footprint)?"},
                "containers": per, "disks": h.get("disks"),
                "points": [{k: p.get(k) for k in ("at", "memory_mb", "memory_peak_mb", "cpu_percent", "available_mb", "paged",
                                                  "cache_hit_percent", "activity")} for p in h.get("points") or []]}
    return await _run(go)


def findings(db: dict, health: dict, tasks: list[dict], res: dict) -> list[dict]:
    """What slows things down, each a finding in words with what to look at or do; the worst first."""
    out: list[dict] = []
    for q in (db.get("slow_queries") or [])[:5]:
        if q.get("mean_ms") is not None and float(q["mean_ms"]) >= 500:
            out.append({"weight": float(q["mean_ms"]), "area": "database",
                        "finding": f"A query takes {q['mean_ms']} ms on average ({q.get('calls')} calls, at most {q.get('max_ms')} ms).",
                        "query": q.get("query"), "look_at": "System Admin > Operations > Database"})
        elif q.get("running_s") is not None:
            out.append({"weight": float(q["running_s"]) * 1000, "area": "database",
                        "finding": f"A query has been running for {q['running_s']} s.", "query": q.get("query"),
                        "look_at": "System Admin > Operations > Database"})
    for t in (db.get("tables") or []):
        dead, rows = int(t.get("dead_rows") or 0), int(t.get("rows") or 0)
        if dead > 10000 and dead > rows * 0.2:
            out.append({"weight": 400, "area": "database",
                        "finding": f"Table {t['schema']}.{t['name']} has {dead:,} dead rows beside {rows:,} live ones "
                                   f"(last tidied {t.get('last_tidied') or 'never'}).",
                        "look_at": "the database's own tidying (autovacuum) or System Admin > Operations > Housekeeping"})
    for k, c in (health.get("checks") or {}).items():
        ms = (c or {}).get("response_ms")
        if ms is not None and ms >= SLOW_CHECK_MS and (c or {}).get("status") != "off":
            out.append({"weight": ms, "area": "service",
                        "finding": f"{(c or {}).get('name') or k} answered its health check in {ms} ms.",
                        "look_at": f"ops_logs {k}"})
    for c in health.get("containers") or []:
        limit, mem = _mb(c.get("memory_limit_bytes")), _mb(c.get("memory_bytes"))
        if limit and mem and mem >= limit * MEMORY_SHARE:
            out.append({"weight": 800, "area": "memory",
                        "finding": f"{c.get('name')} uses {mem} MB of its {limit} MB limit.",
                        "look_at": "System Admin > Footprint"})
        if (c.get("cpu_percent") or 0) >= 90:
            out.append({"weight": 600, "area": "cpu", "finding": f"{c.get('name')} uses {c['cpu_percent']}% CPU now.",
                        "look_at": f"ops_logs {c.get('service') or c.get('name')}"})
    for t in tasks:
        if t["status"] == "running":
            out.append({"weight": 300 + t["minutes"], "area": "jobs",
                        "finding": f"Background task '{t['label']}' ({t['kind']}) has been running for {t['minutes']} minutes.",
                        "look_at": "System Admin > Jobs"})
        else:
            out.append({"weight": 700, "area": "jobs",
                        "finding": f"Background task '{t['label']}' has waited {t['minutes']} minutes for the job runner.",
                        "look_at": "ops_status (the api servers), System Admin > Jobs"})
    s = res.get("summary") or {}
    if s.get("paged"):
        out.append({"weight": 900, "area": "memory",
                    "finding": "The Docker host paged (its swap grew) in the last day: everything slows when it does.",
                    "look_at": "ops_resources; give Docker more memory or switch off a service not needed"})
    if s.get("least_available_mb") is not None and s["least_available_mb"] < 512:
        out.append({"weight": 850, "area": "memory",
                    "finding": f"The host had only {s['least_available_mb']} MB memory left at {s.get('least_available_at')}.",
                    "look_at": "ops_resources"})
    if (s.get("cpu_peak_percent") or 0) >= 90:
        out.append({"weight": 500, "area": "cpu",
                    "finding": f"CPU reached {s['cpu_peak_percent']}% of the host at {s.get('cpu_peak_at')}.",
                    "look_at": "ops_resources (what was running then)"})
    cache = [p.get("cache_hit_percent") for p in res.get("points") or [] if p.get("cache_hit_percent") is not None]
    if cache and min(cache) < 90:
        out.append({"weight": 450, "area": "database",
                    "finding": f"The database's cache hit rate fell to {min(cache)}% (reads went to disk).",
                    "look_at": "the database's memory (shared_buffers) or the queries above"})
    out.sort(key=lambda f: -f["weight"])
    return [{k: v for k, v in f.items() if k != "weight"} for f in out]


def long_tasks(conn) -> list[dict]:
    """Background tasks running or waiting for long, with how many minutes."""
    rows = conn.execute(text(f"""
        SELECT kind, label, status, requested_by,
               round(extract(epoch FROM now() - coalesce(started_at, requested_at)) / 60)::int AS minutes
          FROM core.tasks
         WHERE (status = 'running' AND started_at < now() - interval '{LONG_TASK_MINUTES} minutes')
            OR (status = 'queued' AND requested_at < now() - interval '{QUEUED_MINUTES} minutes'
                AND requested_at > now() - interval '1 day')
         ORDER BY coalesce(started_at, requested_at) LIMIT 20""")).mappings()
    return [dict(r) for r in rows]


@mcp.tool()
async def ops_find_slow() -> Any:
    """What is slowing things down (Super Admins and IT Admins), as findings in words, the worst first: slow and long
    running database queries, tables needing tidying, services slow to answer, containers near their memory limit or
    busy, background tasks running long or waiting, the host paging or short of memory and the database's cache in the
    last day. Each finding says what to look at next. Read only."""
    def go(conn):
        from . import operations as ops
        from . import resources as rs
        from .admin_check import health_now
        _operator()
        db = ops.db_health(conn)
        health = health_now()
        a, b = rs.period(days=1)
        res = rs.history(rs.rows_between(conn, a, b), most=48)
        found = findings(db, health, long_tasks(conn), res)
        return {"findings": found or [{"area": "-", "finding": "Nothing stands out now: queries, services, memory, CPU and "
                                                                 "background tasks look normal."}],
                "slow_queries_note": db.get("slow_note") or "", "checked_at": datetime.now(UTC).isoformat(timespec="seconds")}
    return await _run(go)


@mcp.tool()
async def ops_logs(service: str, tail: int = 200, contains: str = "") -> Any:
    """A container's last log lines (Super Admins and IT Admins): service is its name as ops_status lists it (api,
    web, db, reports, documents, keycloak, ...); tail at most 2,000; contains keeps only the lines with that text (case
    ignored), e.g. "error". Read only."""
    def go(conn):
        _operator()
        name = "".join(ch for ch in service if ch.isalnum() or ch in "-_.")
        if not name:
            raise EditError("Say which container: its name as ops_status lists it.", 400)
        got = helper("GET", f"/containers/{name}/logs?tail={max(1, min(int(tail or 200), LOG_LINES))}", timeout=60)
        lines = got.get("lines") or []
        if contains:
            lines = [ln for ln in lines if contains.lower() in ln.lower()]
        return {"service": name, "lines": lines, "count": len(lines)}
    return await _run(go)


@mcp.tool()
async def ops_backups() -> Any:
    """Every backup (Super Admins and IT Admins): the infrastructure backups (every database, the files, the config)
    with their tag, size and whether pinned; the application backups (models); the one running; and whether backups
    from the web are proven by the self-test. Read only."""
    def go(conn):
        from . import backups as bk
        from .api.backups import web_proven
        _operator()
        infra = helper("GET", "/backups")
        return {"infrastructure": [{k: b.get(k) for k in ("name", "tag", "kind", "created", "version", "size", "bytes",
                                                           "pinned", "status") if k in b} for b in infra.get("infrastructure") or []],
                "running": infra.get("state") or {}, "restore_choices": infra.get("restore_choices") or {},
                "application": application(bk.list_application()), "web": web_proven(conn)}
    return await _run(go)


def application(listing: dict) -> list[dict]:
    """The application backups, short: each with how many models it holds and how many failed."""
    return [{"name": r.get("name"), "tag": r.get("tag"), "created": r.get("created"), "by": r.get("by"),
             "bytes": r.get("bytes"), "pinned": r.get("pinned"), "models": len(r.get("models") or []),
             "failed": sum(1 for m in r.get("models") or [] if m.get("status") not in ("ok", None))}
            for r in listing.get("runs") or []]


def unused(conn, days: int) -> dict:
    """Working models nobody has used for `days` (the usage record, D371) and projects nobody has changed for `days`,
    with what would stop each moving to the archive."""
    from . import archive as ar
    from . import operations as ops
    since = (datetime.now(UTC) - timedelta(days=days)).date().isoformat()
    models = []
    first = ops._scalar(conn, "SELECT min(day) FROM core.usage_daily")
    known_long = first is not None and str(first) <= since
    for m in ops.model_use(conn, since):
        if m["kind"] != "project" or m["archived"]:
            continue
        if (m["last_used"] is not None and m["last_used"] < since) or (m["last_used"] is None and known_long):
            try:
                refs = ar.references(conn, m["guid"])
            except Exception:  # noqa: BLE001 - not readable now: listed without
                refs = {"blocking": []}
            models.append({"id": m["guid"], "name": m["name"], "kind": "project", "last_used": m["last_used"],
                           "last_changed": m["last_changed"], "entities": m["entities"], "blocking": refs["blocking"]})
    projects = []
    try:
        from . import projects as pj
        with pj.connections(write=False) as pc:
            for r in pc.execute(text("""SELECT guid::text AS guid, name, status, modified_at,
                                               greatest(modified_at, coalesce((SELECT max(d.modified_at) FROM proj.documents d
                                                                                 WHERE d.project_id = p.id), modified_at)) AS last_changed
                                          FROM proj.projects p ORDER BY name""")).mappings():
                last = r["last_changed"]
                if last is not None and last.date().isoformat() < since:
                    projects.append({"id": r["guid"], "name": r["name"], "status": r["status"], "last_changed": _iso(last)})
    except Exception:  # noqa: BLE001 - projects switched off: none
        projects = []
    return {"days": days, "since": since, "models": models, "projects": projects,
            "note": ("A model counts as unused once the usage record goes back that far." if not known_long else "")
            + " Archiving keeps everything (its admins can bring it back); nothing is deleted through MCP."}


@mcp.tool()
async def ops_unused(days: int = UNUSED_DAYS) -> Any:
    """Working models nobody has used and projects nobody has changed for `days` (default 180), with what would stop
    each moving to the archive (models derived from it, projects using it). Super Admins and IT Admins. Read only:
    ops_archive moves one."""
    def go(conn):
        _operator()
        return unused(conn, max(7, min(int(days or UNUSED_DAYS), 3650)))
    return await _run(go)


# ---------------------------------------------------------------- changing (preview, then confirm)
@mcp.tool()
async def ops_backup(kind: str = "infrastructure", tag: str = "", confirm: str = "", why: str = "") -> Any:
    """Take a backup now (Super Admins and IT Admins): kind "infrastructure" (every database, the files, the config
    file and the versions; people keep working) or "application" (every model as a model backup file). tag: a short
    name for it. First call: a preview and a confirm token; call again with confirm=<token> to start it. It runs in
    the background: follow it with ops_backups. Pass why: the person's request in a line."""
    if kind not in ("infrastructure", "application"):
        return {"error": "kind is infrastructure or application."}
    name = (tag or "").strip()[:60] or ("mcp" if kind == "infrastructure" else "application")
    args = {"kind": kind, "tag": name}

    def preview(conn, user):
        from . import backup_folder
        from .api.backups import services_on
        _operator(user)
        _not_busy(conn)
        if not services_on():
            raise EditError("Backups are switched off (Administration > Services > Backups).", 409)
        ok, why_not = backup_folder.ready()
        if not ok:
            raise EditError(why_not, 409)
        return {"will": f"Take an {kind} backup tagged '{name}' now, in the background; people keep working."
                        + (" It holds every database, the files, the config file and the versions." if kind == "infrastructure"
                           else " It holds every model as a model backup file.")}

    def apply(conn, user):
        from . import backup_schedule as bs
        _operator(user)
        _not_busy(conn)
        if kind == "infrastructure":
            out = _start_task("backup.infrastructure", f"Infrastructure backup '{name}' (through MCP)",
                              {"tag": name, "version": __version__, "keep": bs.keep(conn, "infrastructure")}, "#/admin/backups", user)
        else:
            out = _start_task("backup.application", f"Application backup '{name}' (through MCP)", {"tag": name, "models": []},
                              "#/admin/backups", user)
        return {**out, "message": f"The {kind} backup '{name}' has started: follow it with ops_backups.", "link": "/#/admin/backups"}
    return await mcp_ops.operate("ops_backup", args, confirm, preview, apply, label=f"{kind} backup")


@mcp.tool()
async def ops_restore(backup: str, what: str = "", kind: str = "infrastructure", confirm: str = "", why: str = "") -> Any:
    """Restore a backup (Super Admins and IT Admins; a whole application backup: Super Admins). kind "infrastructure":
    backup is its name from ops_backups, what one of its restore choices (empty: everything); the installation is
    read-only while it runs, a backup of the current state is taken first, everyone signs in again afterwards and this
    MCP connection drops. kind "application": every model of that application backup put back over itself. First call:
    a preview and a confirm token; call again with confirm=<token> to start. Pass why: the person's request in a line."""
    if kind not in ("infrastructure", "application"):
        return {"error": "kind is infrastructure or application."}
    args = {"backup": backup, "what": what, "kind": kind}

    def found(user):
        _operator(user)
        if kind == "application":
            from . import backups as bk
            if permissions.SUPER_ADMIN not in (user.roles or ()):
                raise EditError("Restoring a whole application backup needs the Super Admin role.", 403)
            _, manifest = bk._run(backup)
            return {"name": backup, "tag": manifest.get("tag"), "models": len(manifest.get("models") or [])}, {}
        infra = helper("GET", "/backups")
        b = next((x for x in infra.get("infrastructure") or [] if x.get("name") == backup), None)
        if not b:
            raise EditError(f"No infrastructure backup '{backup}': ops_backups lists them.", 404)
        choices = infra.get("restore_choices") or {}
        if what and what not in choices:
            raise EditError(f"what is one of: {', '.join(choices) or 'nothing (everything)'}.", 400)
        return b, choices

    def preview(conn, user):
        _not_busy(conn)
        b, choices = found(user)
        if kind == "application":
            return {"will": f"Put every model of application backup '{backup}' back over itself ({b['models']} models); models "
                            "no longer there are made again; models made since stay as they are.", "backup": b}
        return {"will": f"Restore {choices.get(what, 'everything') if what else 'everything'} from backup '{backup}' "
                        f"(tagged '{b.get('tag') or '-'}', made {b.get('created') or '-'}, version {b.get('version') or '-'}).",
                "while_it_runs": "The installation is read-only; a backup of the current state is taken first; everyone signs "
                                 "in again afterwards; this MCP connection drops until it is back.",
                "backup": {k: b.get(k) for k in ("name", "tag", "created", "version", "pinned")}}

    def apply(conn, user):
        _not_busy(conn)
        b, _ = found(user)
        audit.record(conn, actor=user.username, action="backup.restore.start", object_type="backup", object_id=backup,
                     details={"what": what or ("every model" if kind == "application" else ""), "via": "mcp"}, source="mcp")
        if kind == "application":
            out = _start_task("backup.restore_all", f"Restore every model of '{b.get('tag') or backup}' (through MCP)",
                              {"name": backup}, "#/admin/backups", user)
            return {**out, "message": f"Restoring every model of '{backup}' in the background."}
        helper("POST", "/backups/restore", {"name": backup, "what": what, "by": user.username, "version": __version__})
        return {"message": f"The restore of '{backup}' has started: the installation is read-only until it ends; sign in again "
                           "afterwards.", "link": "/#/admin/backups"}
    return await mcp_ops.operate("ops_restore", args, confirm, preview, apply, label=f"{kind} restore")


@mcp.tool()
async def ops_scale(count: int, confirm: str = "", why: str = "") -> Any:
    """Run this many API and job servers (1 to 16; Super Admins and IT Admins), at once and without a restart: copies
    of the first are added, or the highest-numbered stop (their running jobs finish first). The number is kept in the
    config file so `eax up` keeps it. First call: a preview (how many run now) and a confirm token; call again with
    confirm=<token>. Pass why: the person's request in a line."""
    args = {"count": count}

    def preview(conn, user):
        _operator(user)
        _not_busy(conn)
        now = helper("GET", "/servers")
        top = int(now.get("max") or 16)
        if not 1 <= int(count) <= top:
            raise EditError(f"Between 1 and {top} servers.", 400)
        running = sum(1 for s in now.get("servers") or [] if s.get("state") == "running")
        if now.get("busy"):
            raise EditError("The servers are being changed already: wait for that to end.", 409)
        change = ("no change" if int(count) == running else
                  f"add {int(count) - running}" if int(count) > running else f"stop and remove {running - int(count)}")
        return {"will": f"Run {count} API and job server(s): {running} run now, so {change}.", "running": running,
                "wanted_now": now.get("wanted")}

    def apply(conn, user):
        _operator(user)
        _not_busy(conn)
        audit.record(conn, actor=user.username, action="system.servers", object_type="system", object_id="api",
                     details={"count": int(count), "via": "mcp"}, source="mcp")
        out = helper("POST", "/servers", {"count": int(count), "by": user.username}, timeout=30)
        return {**out, "message": f"Changing to {count} API and job server(s): ops_status shows them.", "link": "/#/admin/scaling"}
    return await mcp_ops.operate("ops_scale", args, confirm, preview, apply, label="API and job servers")


@mcp.tool()
async def ops_archive(model: str = "", project: str = "", note: str = "", confirm: str = "", why: str = "") -> Any:
    """Move one unused model or project to the archive (Super Admins and IT Admins, with the Model Admin role on the
    model or the Project Admin role on the project, as on the Archive page; a Super Admin may move any). Give model
    (name or id) or project (name or id). A project takes its documents and the models only it uses; nothing derived
    from a model may remain. Kept in the archive, its admins can bring it back; never deleted through MCP. First call:
    a preview and a confirm token; call again with confirm=<token>. Pass why: the person's request in a line."""
    if bool(model) == bool(project):
        return {"error": "Give a model or a project (one of them)."}
    args = {"model": model, "project": project, "note": note}

    def check(conn, user):
        from . import archive as ar
        _operator(user)
        _not_busy(conn)
        if model:
            m = repo.get_model(conn, model)
            ar._may_move(conn, user, m, "archived")
            refs = ar.references(conn, model)
            if refs["blocking"]:
                raise EditError(f"{m['name']} cannot move while " + "; ".join(refs["blocking"]) + ".", 409)
            return m, refs
        from . import project_backup as pb
        from . import projects as pj
        with pj.connections(write=False) as pc:
            p = pj.project_row(pc, project)
            pb.need_manage(pc, p, user)
            return p, ar.project_references(pc, project)

    def preview(conn, user):
        it, refs = check(conn, user)
        if model:
            return {"will": f"Archive model {it['name']}: its backup file into the archive, then out of the working database. "
                            "Its admins can bring it back.", "copies": refs["copies"],
                    "open_merge_requests": refs["open_merge_requests"], "model": {"id": str(it["id"]), "name": it["name"]}}
        return {"will": f"Archive project {it['name']} with its documents and {len(refs['moving'])} model(s) of its own.",
                "moving": [m["name"] for m in refs["moving"]],
                "staying": [{"name": m["name"], "why": m["why"]} for m in refs["staying"]],
                "project": {"id": str(it["guid"]), "name": it["name"]}}

    def apply(conn, user):
        it, _ = check(conn, user)
        if model:
            out = _start_task("archive.move", f"Archive {it['name']} (through MCP)",
                              {"model": str(it["id"]), "state": "archived", "note": note[:2000]}, "#/archive", user)
        else:
            out = _start_task("archive.project_move", f"Archive {it['name']} (through MCP)",
                              {"project": str(it["guid"]), "state": "archived", "note": note[:2000]}, "#/archive", user)
        return {**out, "name": it["name"], "message": f"{it['name']} is moving to the archive in the background.", "link": "/#/archive"}
    return await mcp_ops.operate("ops_archive", args, confirm, preview, apply, label="archive")


@mcp.tool()
async def ops_alerts() -> Any:
    """The alerts (R5.9; Super Admins and IT Admins): every check with its state (OK, WARNING, CRITICAL, UNKNOWN),
    since when, what it measured, whether acknowledged; the open alerts first; the silences. Read only."""
    def go(conn):
        from . import alerts
        _operator()
        o = alerts.overview(conn)
        keep = ("check_key", "what", "state", "since", "value", "message", "acked_by", "ack_note", "flapping")
        return {"open": o["open"], "critical": o["critical"], "unacknowledged": o["unacknowledged"],
                "checks": [{k: c.get(k) for k in keep} for c in o["checks"]], "silences": o["silences"]}
    return await _run(go)


TOOLS = ("ops_status", "ops_resources", "ops_find_slow", "ops_logs", "ops_backups", "ops_unused",
         "ops_backup", "ops_restore", "ops_scale", "ops_archive", "ops_alerts")
