"""Phase 10 (D183): the administration console's API: settings, start-up settings, licences, the containers and a
restart of the whole system through the operations helper."""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path

from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy import text

from .. import audit
from .. import services as sv
from .. import settings as st
from ..auth import require_auth
from ..db import get_engine
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("admin", __name__, url_prefix="/api/v1", description="Administration console (phase 10)")
SECURITY = [{"bearerAuth": []}]


def _ops_raw(method: str, path: str, body: dict | None = None, timeout: int = 10) -> dict:
    """The operations helper's answer, raising on any failure (no HTTP error for the caller)."""
    url, token = os.environ.get("EAX_OPS_URL", "http://ops:8090"), os.environ.get("EAX_OPS_TOKEN", "")
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    req = urllib.request.Request(f"{url}{path}", method=method, data=data,
                                 headers={"X-Ops-Token": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _ops(method: str, path: str, body: dict | None = None, timeout: int = 10) -> dict:
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
        abort(exc.code, message=f"The operations helper refused: {msg}")
    except (urllib.error.URLError, TimeoutError) as exc:
        abort(503, message=f"The operations helper is not reachable ({exc.reason if hasattr(exc, 'reason') else exc}). "
                           "Check that the ops container runs.")
    return {}


@blp.route("/settings")
class PublicSettings(MethodView):
    """/api/v1/settings: GET the application settings every screen follows: currency, time zone, date and number
    formats, week, financial year."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The application settings every screen follows: currency, time zone, date and number formats, week, financial year"""
        v = st.values()
        out = {k: v[k] for k, spec in st.REGISTRY.items() if spec[0] == "application"}
        out["services"] = sv.switches()   # which optional services are on (D191): screens hide the others
        return out


@blp.route("/admin/databases")
class Databases(MethodView):
    """/api/v1/admin/databases: GET every database EA Explorer uses (R2.50, D611): what it holds, its setting, where
    it lives (the shared server or its own) and, for EA Explorer's own, whether it answers."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Every database EA Explorer uses (R2.50, D611): what it holds, its setting, where it lives (the shared server or
        its own) and, for EA Explorer's own, whether it answers. Passwords are never shown"""
        from .. import databases as dbs
        return {"databases": dbs.status(), "guide": "docs/databases.md"}


@blp.route("/admin/secrets")
class Secrets(MethodView):
    """/api/v1/admin/secrets (R6-S1, D743): GET every password, key and certificate by name (never a value): how it is
    rotated, when it last changed, when it is next due, and what needs a person. Super Admins and IT Admins."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Every password, key and certificate by name (never a value): how it is rotated, when it last changed, when it
        is next due, and what needs a person (R6-S1)"""
        return _ops("GET", "/secrets", timeout=30)


@blp.route("/admin/secrets/rotate")
class SecretsRotate(MethodView):
    """/api/v1/admin/secrets/rotate (R6-R1, D743): POST {key} (a password or key, "--due" for every one that is due, or "--all" for every one eax can rotate):
    rotated now in the Command centre's runner, which changes it in the database or Keycloak too and makes the
    services that use it again (a few seconds each). In the audit trail."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(202, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Rotate a password or key now, or every one that is due (key "--due"); in the audit trail (R6-R1)"""
        key = str((data or {}).get("key") or "")
        if key == "--all":
            from .maintenance_gate import needs_yes
            needs_yes(data, "Rotate all")
        if not key:
            abort(400, message="Which one? key: its setting's name, --due or --all.")
        out = _ops("POST", "/secrets/rotate", {"key": key, "by": g.user.username}, timeout=30)
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="secrets.rotate", object_type="secret", object_id=key,
                         details={"run": out.get("run")})
        return out


@blp.route("/admin/front-certificate")
class FrontCertificate(MethodView):
    """/api/v1/admin/front-certificate (R6.6.3, D750): GET the certificate the front door presents (names, issuer, end);
    POST upload a new one {certificate, chain, key}: checked (names, dates, key, chain), then put in place and the front
    door reloaded with no restart, the one in use kept to undo (Super Admins and IT Admins); DELETE put the one in use
    before back. The key is never shown again or kept in the audit trail."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The certificate the front door presents now: names, issuer, when it ends (R6.6.3)"""
        from .. import frontcert
        from ..config import get_settings
        return {"presented": frontcert.presented(), "needs": frontcert.names_needed(get_settings().hostname)}

    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Upload the front door's certificate {certificate, chain, key}: checked, put in place, reloaded with no
        restart; the one in use kept to undo (R6.6.3)"""
        from .. import frontcert
        from ..config import get_settings
        d = data or {}
        try:
            info = frontcert.check(str(d.get("certificate") or ""), str(d.get("chain") or ""), str(d.get("key") or ""),
                                   get_settings().hostname)
        except EditError as exc:
            abort(exc.status, message=str(exc))
        out = _ops("POST", "/tls/install", {"certificate": frontcert.full_chain(str(d.get("certificate") or ""),
                                                                                  str(d.get("chain") or "")),
                                             "key": str(d.get("key") or ""), "by": g.user.username}, timeout=120)
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="tls.upload", object_type="certificate", object_id="front-door",
                         details={k: info[k] for k in ("subject", "issuer", "names", "not_after")})
        return {**info, **out}

    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def delete(self):
        """Put back the certificate in use before the last upload (R6.6.3)"""
        out = _ops("POST", "/tls/undo", {"by": g.user.username}, timeout=120)
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="tls.undo", object_type="certificate", object_id="front-door",
                         details={})
        return out


@blp.route("/admin/logs/files")
class LogFiles(MethodView):
    """/api/v1/admin/logs/files: GET the containers' logs kept on disk, one file a day (R2.32): ?service= for one
    container."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The containers' logs kept on disk, one file a day (R2.32): ?service= for one container"""
        from urllib.parse import quote
        return _ops("GET", f"/logs/files?service={quote(request.args.get('service', ''))}", timeout=30)


@blp.route("/admin/logs/read")
class LogRead(MethodView):
    """/api/v1/admin/logs/read: GET a day of one or several containers' logs, merged by time (R2.31):
    ?services=api,db&day=YYYY-MM-DD&level= (debug|info|warning|error: that and…"""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """A day of one or several containers' logs, merged by time (R2.31): ?services=api,db&day=YYYY-MM-DD&level=
        (debug|info|warning|error: that and worse)&q=&since=HH:MM&until=HH:MM&page=N (1,000 lines a page); secrets masked"""
        from urllib.parse import urlencode
        keep = {k: request.args.get(k, "") for k in ("services", "day", "level", "q", "since", "until", "page")}
        return _ops("GET", "/logs/read?" + urlencode(keep), timeout=60)


@blp.route("/admin/logs/own")
class LogOwn(MethodView):
    """/api/v1/admin/logs/own: GET eax's own logs (work/logs) and the log backups (R2.31): listed; ?name= reads one
    of eax's logs, ?backup= lists a backup's files and &member= reads one; &q= words…"""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """eax's own logs (work/logs) and the log backups (R2.31): listed; ?name= reads one of eax's logs, ?backup= lists a
        backup's files and &member= reads one; &q= words, &page=N (1,000 lines a page); secrets masked"""
        from urllib.parse import urlencode
        keep = {k: request.args.get(k, "") for k in ("name", "backup", "member", "q", "page") if request.args.get(k)}
        return _ops("GET", "/logs/own" + (f"?{urlencode(keep)}" if keep else ""), timeout=60)


@blp.route("/admin/logs/<any(backup, clean):what>")
class LogKeep(MethodView):
    """/api/v1/admin/logs/{what}: POST backup {tag}: the containers' logs and eax's own in one zip in
    work/backups/logs; clean {days}: those and the log backups older than `days` deleted for good (R2.30)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data, what):
        """backup {tag}: the containers' logs and eax's own in one zip in work/backups/logs; clean {days}: those and the
        log backups older than `days` deleted for good (R2.30). In the audit trail"""
        data = data or {}
        if what == "clean":
            try:
                days = int(data.get("days") or 0)
            except (TypeError, ValueError):
                abort(400, message="days is a whole number of days.")
            if days < 1:
                abort(400, message="Clean the logs older than 1 day or more.")
            out = _ops("POST", "/logs/clean", {"days": days, "by": g.user.username}, timeout=120)
        else:
            out = _ops("POST", "/logs/backup", {"tag": str(data.get("tag") or "")[:40], "by": g.user.username}, timeout=300)
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action=f"logs.{what}", object_type="logs", object_id=what,
                         details={k: v for k, v in out.items() if k != "deleted"} | {"deleted": len(out.get("deleted") or [])})
        return out


@blp.route("/admin/logs/rolling")
class LogRolling(MethodView):
    """/api/v1/admin/logs/rolling: GET the sizes the logs roll at and the days they are kept {file_kb, docker_kb,
    docker_kb_running, keep_days}; PUT changes them (Super Admin; R5.26, owner, 15 Nov 2026: "The logs in the entire
    system should be configurable form a log page. Default being rolling with 100kb size")."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The sizes the logs roll at and the days they are kept"""
        from .. import settings as st
        out = _ops("GET", "/logs/rolling", timeout=30)
        return {**out, "keep_days": int(st.values().get("logs_keep_days") or 0)}

    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def put(self, data):
        """{file_kb, docker_kb, keep_days}: our log files roll at file_kb at once; Docker's copy at docker_kb from the next
        eax up; files older than keep_days deleted every night (0 keeps them). In the audit trail"""
        from .. import settings as st
        data = data or {}
        if "keep_days" in data:
            try:
                st.check("logs_keep_days", data.get("keep_days"))         # wrong days change nothing
            except st.EditError as exc:
                abort(getattr(exc, "status", 400), message=str(exc))
        out = _ops("POST", "/logs/rolling", {"file_kb": data.get("file_kb"), "docker_kb": data.get("docker_kb"),
                                             "by": g.user.username}, timeout=30)
        with get_engine().begin() as conn:
            if "keep_days" in data:
                try:
                    st.update(conn, g.user, {"logs_keep_days": data.get("keep_days")})
                except st.EditError as exc:
                    abort(getattr(exc, "status", 400), message=str(exc))
            audit.record(conn, actor=g.user.username, action="logs.rolling", object_type="logs", object_id="rolling",
                         details={k: data.get(k) for k in ("file_kb", "docker_kb", "keep_days")})
        return {**out, "keep_days": int(st.values().get("logs_keep_days") or 0)}


@blp.route("/admin/footprint")
class Footprint(MethodView):
    """/api/v1/admin/footprint: GET how much each container takes (R2.22): the newest measurement and the one before
    (image, own disk, volumes, memory, CPU, start-up seconds), as `eax footprint` keeps them…; POST measures now
    {label}; kept beside the ones before."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """How much each container takes (R2.22): the newest measurement and the one before (image, own disk, volumes,
        memory, CPU, start-up seconds), as `eax footprint` keeps them in work/footprint"""
        return _ops("GET", "/footprint", timeout=30)

    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Measures now {label}; kept beside the ones before"""
        return _ops("POST", "/footprint", {"label": str((data or {}).get("label") or "")[:60]}, timeout=180)


@blp.route("/admin/resources")
class Resources(MethodView):
    """/api/v1/admin/resources: GET the resource history over a period (R3.5-M8): ?from=&to= (UTC times) or ?days= (1
    unless given): the whole installation's memory and CPU, the host's memory left and…; DELETE deletes the resource
    history (Super Admin, audited): ?from=&to= a period, ?to= everything before, neither: all."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The resource history over a period (R3.5-M8): ?from=&to= (UTC times) or ?days= (1 unless given): the whole
        installation's memory and CPU, the host's memory left and paging, the database's cache, each container's memory
        and CPU, the peaks; and the settings (how often, how long kept, a shorter interval for a while)"""
        from .. import resources as rs
        try:
            days = float(request.args.get("days") or 1)
            if not (math.isfinite(days) and days > 0):   # nan, inf or not a period (Semgrep's nan-injection, R8.2, D823)
                raise ValueError("days: a number of days greater than 0.")
            start, end = rs.period(request.args.get("from"), request.args.get("to"), days)
        except (ValueError, EditError) as exc:
            abort(400, message=str(exc))
        with get_engine().connect() as conn:
            out = rs.history(rs.rows_between(conn, start, end))
            last = rs.last_sample(conn)
            out["settings"] = rs.settings_of(st.values(conn))
        out.update({"from": start.isoformat(timespec="seconds"), "to": end.isoformat(timespec="seconds"),
                    "last_sample": last.isoformat(timespec="seconds") if last else None,
                    "may_delete": _is_super(g.user)})
        return out

    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def delete(self):
        """Deletes the resource history (Super Admin, audited): ?from=&to= a period, ?to= everything before, neither: all"""
        from .. import resources as rs
        if not _is_super(g.user):
            abort(403, message="Only a Super Admin deletes the resource history.")
        a, b = request.args.get("from") or None, request.args.get("to") or None
        try:
            with get_engine().begin() as conn:
                n = rs.delete(conn, a, b)
                audit.record(conn, actor=g.user.username, action="resources.delete", object_type="resource_history",
                             object_id="", details={"from": a, "to": b, "deleted": n})
        except EditError as exc:
            abort(exc.status, message=str(exc))
        what = f"from {a} to {b}" if a and b else f"before {b}" if b else f"from {a}" if a else "all of it"
        return {"deleted": n, "message": f"{n} samples deleted ({what})."}


@blp.route("/admin/resources/csv")
class ResourcesCsv(MethodView):
    """/api/v1/admin/resources/csv: GET the resource history over a period as CSV (?from=&to= or ?days=): one line
    per container per sample."""
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def get(self):
        """The resource history over a period as CSV (?from=&to= or ?days=): one line per container per sample"""
        from flask import Response

        from .. import resources as rs
        try:
            start, end = rs.period(request.args.get("from"), request.args.get("to"), float(request.args.get("days") or 1))
        except (ValueError, EditError) as exc:
            abort(400, message=str(exc))
        with get_engine().connect() as conn:
            body = rs.csv_text(rs.rows_between(conn, start, end))
        name = f"eaexplorer-resources-{start:%Y%m%dT%H%M}-{end:%Y%m%dT%H%M}.csv"
        return Response(body, mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@blp.route("/admin/resources/sample")
class ResourcesSample(MethodView):
    """/api/v1/admin/resources/sample: POST a sample of the resource history now (as the job takes every few
    minutes)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self):
        """A sample of the resource history now (as the job takes every few minutes)"""
        from .. import resources as rs
        with get_engine().begin() as conn:
            return rs.take(conn, _ops)


@blp.route("/admin/resources/settings")
class ResourcesSettings(MethodView):
    """/api/v1/admin/resources/settings: PUT how often a sample is taken and how long kept {every_minutes,
    detail_days, keep_days}, and a shorter interval for a while {boost_every, boost_hours} (0 ends it); applied…"""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def put(self, data):
        """How often a sample is taken and how long kept {every_minutes, detail_days, keep_days}, and a shorter interval
        for a while {boost_every, boost_hours} (0 ends it); applied at once, audited"""
        from .. import resources as rs
        try:
            with get_engine().begin() as conn:
                out = rs.change_settings(conn, data or {})
                audit.record(conn, actor=g.user.username, action="resources.settings", object_type="resource_history",
                             object_id="", details=dict(data or {}))
        except EditError as exc:
            abort(exc.status, message=str(exc))
        return out


def _is_super(user) -> bool:
    from .. import permissions as perms
    return perms.SUPER_ADMIN in (user.roles or [])


@blp.route("/admin/estate")
class Estate(MethodView):
    """/api/v1/admin/estate: GET EA Explorer's own estate (R2.33): the logical diagram (components and who calls
    whom) and the physical one of this installation as it runs (containers, images, networks…"""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """EA Explorer's own estate (R2.33): the logical diagram (components and who calls whom) and the physical one of
        this installation as it runs (containers, images, networks, published ports, volumes and folders), as nodes and
        edges"""
        return _ops("GET", "/estate", timeout=60)


@blp.route("/admin/persist")
class Persist(MethodView):
    """/api/v1/admin/persist: GET what persist/ holds (R2.26): the settings that survive every reset (schedules,
    banner, Self-test settings), the safety backups and the reset-survival results; name…"""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """What persist/ holds (R2.26): the settings that survive every reset (schedules, banner, Self-test settings),
        the safety backups and the reset-survival results; name, size, when changed, what each is"""
        return _ops("GET", "/persist", timeout=30)


@blp.route("/admin/persist/delete")
class PersistDelete(MethodView):
    """/api/v1/admin/persist/delete: POST deletes an item of persist/ for good {item} or everything {all: true,
    confirm: "DELETE"} (R2.26); a deleted settings file falls back to its default."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Deletes an item of persist/ for good {item} or everything {all: true, confirm: "DELETE"} (R2.26); a deleted
        settings file falls back to its default. In the audit trail"""
        data = data or {}
        if data.get("confirm") != "DELETE":
            abort(400, message="Type DELETE to confirm: what is deleted from persist/ cannot be brought back.")
        body = {"all": True} if data.get("all") else {"item": str(data.get("item") or "")}
        out = _ops("POST", "/persist/delete", {**body, "by": g.user.username}, timeout=60)
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="persist.deleted", object_type="persist",
                         object_id="all" if body.get("all") else body["item"][:200], details={"deleted": out.get("deleted")})
        return out


@blp.route("/admin/first-run")
class FirstRun(MethodView):
    """/api/v1/admin/first-run: GET the first-run setup (UI-009): its steps, which are done, and whether to show it
    (a Super Admin, not finished); POST {step, done} marks a step; {finished: true} puts the setup away, {finished:
    false} opens it again (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The first-run setup (UI-009): its steps, which are done, and whether to show it (a Super Admin, not finished)"""
        from .. import first_run as fr
        with get_engine().connect() as conn:
            return fr.status(conn, g.user)

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data):
        """{step, done} marks a step; {finished: true} puts the setup away, {finished: false} opens it again (Super Admins)"""
        from .. import first_run as fr
        try:
            with get_engine().connect() as conn, conn.begin():
                out = fr.mark(conn, g.user, data or {})
                audit.record(conn, actor=g.user.username, action="first-run.mark", object_type="settings", object_id="first_run",
                             details=data or {})
                return out
        except EditError as exc:
            abort(exc.status, message=str(exc))


@blp.route("/admin/settings")
class AdminSettings(MethodView):
    """/api/v1/admin/settings: GET every runtime setting with its label, type, choices and help; the start-up
    settings (in clear text) for IT and Super Admins; PUT changes settings (Super Admin) and applies them at once:
    {key: value, ...}."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """Every runtime setting with its label, type, choices and help; the start-up settings (in clear text) for IT and Super Admins"""
        with get_engine().connect() as conn:
            out = st.describe(conn)
        out["may_change"] = g.user.can("settings.manage")
        if g.user.can("system.operate"):
            out["startup"] = st.startup()
        return out

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def put(self, data):
        """Changes settings (Super Admin) and applies them at once: {key: value, ...}"""
        data = dict(data or {})
        if data.get("integrity_fixes") is True:
            from .maintenance_gate import LATER, needs_yes
            needs_yes(data, "Database safe fixes by themselves", LATER)
        data.pop("accept_maintenance", None)
        try:
            with get_engine().connect() as conn, conn.begin():
                out = st.update(conn, g.user, data)
                audit.record(conn, actor=g.user.username, action="settings.change", object_type="settings", object_id="",
                             details={k: data[k] for k in out["changed"]})
                return out
        except EditError as exc:
            abort(exc.status, message=str(exc))


@blp.route("/admin/licences")
class Licences(MethodView):
    """/api/v1/admin/licences: GET the products and libraries EA Explorer runs and their licences."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The products and libraries EA Explorer runs and their licences"""
        return json.loads((Path(__file__).resolve().parent.parent / "licences.json").read_text(encoding="utf-8"))


@blp.route("/admin/containers")
class Containers(MethodView):
    """/api/v1/admin/containers: GET this installation's containers, their state and health, and a running restart
    (from the operations helper)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """This installation's containers, their state and health, and a running restart (from the operations helper)"""
        return _ops("GET", "/status")


@blp.route("/admin/restart")
class Restart(MethodView):
    """/api/v1/admin/restart: POST restarts the whole system, or one service ({service}), through the operations
    helper (Super Admin)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(202, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """Restarts the whole system, or one service ({service}), through the operations helper (Super Admin)"""
        service = (data or {}).get("service") or ""
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="system.restart", object_type="system", object_id=service or "all",
                         details={"service": service or "every service"})
        return _ops("POST", f"/restart/{service}" if service else "/restart")


# ---------------------------------------------------------------- optional services and copies of the config file (D191)
@blp.route("/admin/services")
class Services(MethodView):
    """/api/v1/admin/services: GET the optional services (reports, documents, draw.io, MCP, change log, backups): on
    or off, what stops while off, and (IT and Super Admins) their containers' state."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The optional services (reports, documents, draw.io, MCP, change log, backups): on or off, what stops while off,
        and (IT and Super Admins) their containers' state"""
        out = {"services": sv.describe(), "core": sv.describe_core(), "may_change": g.user.can("settings.manage")}
        if g.user.can("system.operate"):
            try:
                st_ = _ops("GET", "/services")
                states = {c["service"]: c["state"] for c in st_.get("containers", [])}
                out["switching"] = st_.get("switching")
                for s_ in out["services"] + out["core"]:
                    s_["state"] = {c: states.get(c, "not created") for c in s_["containers"]}
            except Exception:  # noqa: BLE001 - the switches still show without the helper
                out["helper"] = "The operations helper is not reachable: the switches show, their containers do not."
        return out


@blp.route("/admin/services/health")
class ServicesHealth(MethodView):
    """/api/v1/admin/services/health: GET each service's health now (IT and Super Admins): its health check with the
    response time, and per container CPU, memory, disk, Docker health, restarts and uptime from…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Each service's health now (IT and Super Admins): its health check with the response time, and per container
        CPU, memory, disk, Docker health, restarts and uptime from the operations helper. Checked afresh each call"""
        from ..admin_check import health_now
        return health_now()


@blp.route("/admin/sign-in-check")
class SignInCheck(MethodView):
    """/api/v1/admin/sign-in-check: POST the sign-in check (IT and Super Admins, D215): the screens call it once when
    an admin signs in; it runs in the background and, when containers, services, backups, the…"""
    @blp.doc(security=SECURITY)
    @blp.response(202, Free)
    @require_auth("system.operate")
    def post(self):
        """The sign-in check (IT and Super Admins, D215): the screens call it once when an admin signs in; it runs in the
        background and, when containers, services, backups, the certificate, versions or default passwords need
        attention, makes one notification for this admin listing them (and tells the webhooks when the list changed)"""
        from ..jobs import admin_sign_in_check
        try:
            admin_sign_in_check.configure(queueing_lock=f"sign_in_check:{g.user.username.lower()}").defer(
                username=g.user.username)
        except Exception as exc:  # noqa: BLE001 - one already waiting for this admin: that one will do
            return {"queued": False, "message": f"A check is already waiting ({exc.__class__.__name__})."}
        return {"queued": True, "message": "Checking in the background: a notification follows if anything needs attention."}


# ---------------------------------------------------------------- the container console (owner, 6 Nov 2026)
@blp.route("/admin/containers/<service>")
class Container(MethodView):
    """/api/v1/admin/containers/{service}: GET one container: state, health and its last checks, image, mounts,
    ports, networks, environment (clear text), restart policy, limits and what it uses now (IT and Super…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, service):
        """One container: state, health and its last checks, image, mounts, ports, networks, environment (clear text),
        restart policy, limits and what it uses now (IT and Super Admins)"""
        return _ops("GET", f"/containers/{service}", timeout=90)


@blp.route("/admin/containers/<service>/logs")
class ContainerLogs(MethodView):
    """/api/v1/admin/containers/{service}/logs: GET the container's last log lines (?tail=, at most 5,000)."""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "tail", "schema": {"type": "integer"}}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, service):
        """The container's last log lines (?tail=, at most 5,000)"""
        return _ops("GET", f"/containers/{service}/logs?tail={int(request.args.get('tail', 300))}", timeout=60)


@blp.route("/admin/containers/<service>/terminal")
class ContainerTerminal(MethodView):
    """/api/v1/admin/containers/{service}/terminal: POST open an interactive terminal in a container (IT and Super
    Admins, D214; off when EAX_CONTAINER_CONSOLE=off): answers a one-time address (good for 30 seconds) for the…"""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data, service):
        """Open an interactive terminal in a container (IT and Super Admins, D214; off when EAX_CONTAINER_CONSOLE=off):
        answers a one-time address (good for 30 seconds) for the browser's WebSocket, {cols, rows} the screen size.
        The start is in the audit trail now, the end when the session ends"""
        out = _ops("POST", "/terminal/ticket", {"service": service, "user": g.user.username,
                                                "cols": int((data or {}).get("cols") or 120),
                                                "rows": int((data or {}).get("rows") or 32)})
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="container.terminal.open", object_type="container",
                         object_id=service, details={"session": out.get("session")},
                         request_id=getattr(g, "request_id", None))
        return {"url": f"/ops-terminal/{out['ticket']}", "session": out.get("session"),
                "idle_minutes": out.get("idle_minutes")}


def record_terminal_ends() -> int:
    """The job runner, every minute: terminal sessions that have ended go into the audit trail (who, which container,
    how long, why it ended), then the operations helper forgets them."""
    try:
        sessions = _ops_raw("GET", "/terminal/sessions").get("sessions", [])
    except Exception:  # noqa: BLE001 - the helper is down or switched off: try again next minute
        return record_command_ends()
    done = [x for x in sessions if x.get("ended")]
    if not done:
        return record_command_ends()
    with get_engine().begin() as conn:
        for x in done:
            if x.get("kind") == "ssh":         # an SSH session to a remote instance's host (R2.2): its row completed
                from .. import databases
                databases.on("operations", conn).execute(text(
                    """UPDATE operations.ssh_sessions SET ended_at = to_timestamp(:e), reason = :r, bytes = :b
                        WHERE session = :s"""), {"e": x.get("ended") or 0, "r": str(x.get("reason") or "")[:300],
                                                 "b": int(x.get("bytes") or 0), "s": x.get("id")})
                audit.record(conn, actor=x.get("user") or "?", action="remote.ssh.close", object_type="remote_instance",
                             object_id=x.get("service") or "", details={"session": x.get("id"), "reason": x.get("reason")})
                continue
            audit.record(conn, actor=x.get("user") or "?", action="container.terminal.close", object_type="container",
                         object_id=x.get("service") or "", details={"session": x.get("id"), "reason": x.get("reason"),
                         "minutes": round(((x.get("ended") or 0) - (x.get("started") or 0)) / 60, 1),
                         "exit_code": x.get("exit_code")})
    _ops_raw("POST", "/terminal/sessions/ack", {"ids": [x["id"] for x in done]})
    return len(done) + record_command_ends()


def record_command_ends() -> int:
    """With the terminal ends: Command centre runs and Console sessions that have ended go into the audit trail with
    their exit code (D554), each once."""
    try:
        runs = _ops_raw("GET", "/commands/runs").get("runs", [])
    except Exception:  # noqa: BLE001
        return 0
    done = [r for r in runs if r.get("ended") and not r.get("logged")]
    if not done:
        return 0
    with get_engine().begin() as conn:
        for r in done:
            audit.record(conn, actor=r.get("by") or "?", action="command.end", object_type="eax command",
                         object_id=r.get("id") or "", details={"command": r.get("command"), "exit_code": r.get("exit_code"),
                                                               "state": r.get("state"), "source": r.get("source")})
    _ops_raw("POST", "/commands/ack", {"ids": [r["id"] for r in done]})
    return len(done)


@blp.route("/admin/services/<key>")
class Service(MethodView):
    """/api/v1/admin/services/{key}: PUT switches an optional service on or off ({on: true|false}, Super Admin): a
    dated copy of the config file is kept, the switch written to it, then the service's containers…"""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def put(self, data, key):
        """Switches an optional service on or off ({on: true|false}, Super Admin): a dated copy of the config file is kept,
        the switch written to it, then the service's containers started or stopped by the operations helper"""
        if key not in sv.SERVICES:
            abort(404, message=f"No optional service {key!r}.")
        on = bool((data or {}).get("on"))
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="system.service", object_type="system", object_id=key,
                         details={"name": sv.SERVICES[key][1], "on": on})
        return _ops("POST", "/services", {"service": key, "on": on, "by": g.user.username}, timeout=30)


@blp.route("/admin/servers")
class Servers(MethodView):
    """/api/v1/admin/servers: GET the API and job servers (copies of the api container: each answers API calls, which
    nginx spreads across them, and runs background jobs), and how many are wanted (D249…; PUT run this many API and
    job servers {count: 1 to 16}, at once and without a restart: copies of the first are added, or the
    highest-numbered stop (the jobs they run finish…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The API and job servers (copies of the api container: each answers API calls, which nginx spreads across them,
        and runs background jobs), and how many are wanted (D249; Super and IT Admins)"""
        return _ops("GET", "/servers")

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def put(self, data):
        """Run this many API and job servers {count: 1 to 16}, at once and without a restart: copies of the first are added,
        or the highest-numbered stop (the jobs they run finish first) and are removed; the number is kept in the config
        file (a dated copy first) so eax up keeps it (D249; Super and IT Admins)"""
        try:
            count = int((data or {}).get("count"))
        except (TypeError, ValueError):
            abort(400, message="count is a whole number.")
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="system.servers", object_type="system", object_id="api",
                         details={"count": count})
        return _ops("POST", "/servers", {"count": count, "by": g.user.username}, timeout=30)


@blp.route("/admin/config-file")
class ConfigFile(MethodView):
    """/api/v1/admin/config-file: GET the config file (work/eaexplorer.env), or one dated copy of it (?name=), as it
    is: in clear text, passwords and secrets too (owner, 5 Nov 2026)."""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "name", "schema": {"type": "string"}}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The config file (work/eaexplorer.env), or one dated copy of it (?name=), as it is: in clear text, passwords and
        secrets too (owner, 5 Nov 2026). Every view is recorded in the audit trail"""
        from urllib.parse import quote
        name = request.args.get("name", "")
        out = _ops("GET", "/config-file" + (f"?name={quote(name)}" if name else ""))
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="system.config_view", object_type="system",
                         object_id=name or "eaexplorer.env", details={"file": out.get("file")})
        return out


@blp.route("/admin/config-file/check")
class ConfigCheck(MethodView):
    """/api/v1/admin/config-file/check: POST checks a config file typed on screen ({text}) and lists what it would
    change; nothing is saved."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Checks a config file typed on screen ({text}) and lists what it would change; nothing is saved"""
        return _ops("POST", "/config-check", {"text": (data or {}).get("text") or ""}, timeout=30)


@blp.route("/admin/config-file/save")
class ConfigSave(MethodView):
    """/api/v1/admin/config-file/save: POST saves the config file typed on screen ({text, why}; IT and Super Admins,
    owner 5 Nov 2026): checked first, the file now kept as a dated copy, then written."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Saves the config file typed on screen ({text, why}; IT and Super Admins, owner 5 Nov 2026): checked first, the
        file now kept as a dated copy, then written. Changed service switches apply at once; every other setting at the
        next eax up. Recorded in the audit trail with the names of the settings that changed (not their values)"""
        data = data or {}
        out = _ops("POST", "/config-file", {"text": data.get("text") or "", "why": data.get("why") or "edited",
                                            "by": g.user.username}, timeout=30)
        if out.get("rows"):
            with get_engine().connect() as conn, conn.begin():
                audit.record(conn, actor=g.user.username, action="system.config_edit", object_type="system", object_id="config",
                             details={"settings": [r["setting"] for r in out["rows"]], "saved_first": out.get("saved_first"),
                                      "why": data.get("why") or ""})
        return out


@blp.route("/admin/config-diff")
class ConfigDiff(MethodView):
    """/api/v1/admin/config-diff: GET the differences between two config files, in clear text: a and b are copy
    names, empty for the current file."""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "a", "schema": {"type": "string"}},
                                            {"in": "query", "name": "b", "schema": {"type": "string"}}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The differences between two config files, in clear text: a and b are copy names, empty for the current file"""
        from urllib.parse import urlencode
        return _ops("GET", "/config-diff?" + urlencode({"a": request.args.get("a", ""), "b": request.args.get("b", "")}))


@blp.route("/admin/config-copies")
class ConfigCopies(MethodView):
    """/api/v1/admin/config-copies: GET the dated copies of the config file (each kept before a change from the
    console or the eax command)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The dated copies of the config file (each kept before a change from the console or the eax command)"""
        return _ops("GET", "/config-copies")


@blp.route("/admin/config-copies/new")
class ConfigCopyNew(MethodView):
    """/api/v1/admin/config-copies/new: POST keeps a dated copy of the config file now ({why}: a few words, part of
    the copy's name)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Keeps a dated copy of the config file now ({why}: a few words, part of the copy's name)"""
        why = (data or {}).get("why") or "kept-by-hand"
        out = _ops("POST", "/config-copy", {"why": why, "by": g.user.username})
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="system.config_copy", object_type="system", object_id="config",
                         details={"name": out.get("name")})
        return out


@blp.route("/admin/config-copies/restore")
class ConfigRestore(MethodView):
    """/api/v1/admin/config-copies/restore: POST makes a copy the config file again ({name}, IT and Super Admins; the
    current one is copied first)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Makes a copy the config file again ({name}, IT and Super Admins; the current one is copied first). Service switches
        apply at once; every other start-up setting at the next eax up"""
        name = (data or {}).get("name") or ""
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="system.config_restore", object_type="system", object_id="config",
                         details={"name": name})
        return _ops("POST", "/config-restore", {"name": name, "by": g.user.username}, timeout=30)


# ---------------------------------------------------------------- the engine, the mounts, container files, alerts
# (Release 2: R2.16 to R2.19, D638 to D641) all through the operations helper; IT Admins and Super Admins
def _looked(action: str, object_id: str, details: dict | None = None) -> None:
    with get_engine().begin() as conn:
        audit.record(conn, actor=g.user.username, action=action, object_type="container", object_id=object_id[:200],
                     details=details or {}, request_id=getattr(g, "request_id", None))


@blp.route("/admin/hosts")
class Hosts(MethodView):
    """/api/v1/admin/hosts: GET the Docker engine EA Explorer runs on (R2.16): OS, kernel, Docker and Compose
    versions, CPUs and their use, load, memory (EA Explorer's and the rest), disks and Docker's…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The Docker engine EA Explorer runs on (R2.16): OS, kernel, Docker and Compose versions, CPUs and their use, load,
        memory (EA Explorer's and the rest), disks and Docker's own disk, containers, uptime, the levels (green, amber,
        red by EAX_HOST_WARN_* and EAX_HOST_ALERT_*) and the day's history, one sample a minute"""
        return _ops("GET", "/hosts", timeout=90)


@blp.route("/admin/mounts")
class Mounts(MethodView):
    """/api/v1/admin/mounts: GET every volume and bind mount the containers use (R2.17): which containers use it,
    where, read only or not, its size, and warnings (read only where it must be writable, a…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Every volume and bind mount the containers use (R2.17): which containers use it, where, read only or not, its
        size, and warnings (read only where it must be writable, a container that could not start with it)"""
        return _ops("GET", "/mounts", timeout=90)


@blp.route("/admin/mounts/<mid>")
class MountDetail(MethodView):
    """/api/v1/admin/mounts/{mid}: GET one mount, looked into read only: its size, free space, files, largest folders
    and files, newest and oldest (or, with ?path=, one folder in it)."""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "path", "schema": {"type": "string"}}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, mid):
        """One mount, looked into read only: its size, free space, files, largest folders and files, newest and oldest
        (or, with ?path=, one folder in it). Every look is in the audit trail"""
        path = request.args.get("path", "")
        _looked("mount.look", mid, {"path": path or "/"})
        from urllib.parse import quote
        return _ops("GET", f"/mounts/{mid}" + (f"?path={quote(path)}" if path else ""), timeout=240)


@blp.route("/admin/mounts/<mid>/search")
class MountSearch(MethodView):
    """/api/v1/admin/mounts/{mid}/search: GET files in a mount by name (?name=), size (?min_mb=) or age (?days=,
    changed in the last N days); up to 500."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, mid):
        """Files in a mount by name (?name=), size (?min_mb=) or age (?days=, changed in the last N days); up to 500"""
        from urllib.parse import urlencode
        q = {k: request.args[k] for k in ("name", "min_mb", "days") if request.args.get(k)}
        _looked("mount.search", mid, q)
        return _ops("GET", f"/mounts/{mid}/search?{urlencode(q)}", timeout=240)


@blp.route("/admin/containers/<service>/files")
class ContainerFiles(MethodView):
    """/api/v1/admin/containers/{service}/files: GET a folder in a container (R2.18): name, size, date, owner and
    permissions, the mounts marked; secrets and keys are not shown; POST a change in a container's files {op:
    write|upload|mkdir|rename|move|copy|delete, path, to, content, sha256, files: [{name, content (base64)}],
    overwrite, confirm…"""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "path", "schema": {"type": "string"}}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, service):
        """A folder in a container (R2.18): name, size, date, owner and permissions, the mounts marked; secrets and keys
        are not shown. Off with EAX_CONTAINER_CONSOLE=off"""
        from urllib.parse import quote
        return _ops("GET", f"/containers/{service}/files?path={quote(request.args.get('path', '/'))}", timeout=60)

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data, service):
        """A change in a container's files {op: write|upload|mkdir|rename|move|copy|delete, path, to, content, sha256,
        files: [{name, content (base64)}], overwrite, confirm, confirm_path}: an edit is refused when the file changed
        since it was opened (sha256); a delete needs the full path typed again; a database's data folder needs
        confirm "database"; the helper's own files, secrets and Docker's socket are never written. Every change is in
        the audit trail (an edit with its before and after)"""
        data = data or {}
        out = _ops("POST", f"/containers/{service}/files", data, timeout=300)
        _looked(f"container.files.{str(data.get('op') or '?')[:20]}", service,
                {k: out.get(k) for k in ("path", "to", "files", "bytes", "before", "after") if out.get(k) is not None})
        return {k: v for k, v in out.items() if k not in ("before", "after")}


@blp.route("/admin/containers/<service>/files/content")
class ContainerFileContent(MethodView):
    """/api/v1/admin/containers/{service}/files/content: GET a text file in a container (up to 2 MB), with its sha256
    for a safe edit; a binary file: its size only."""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "path", "schema": {"type": "string"}}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, service):
        """A text file in a container (up to 2 MB), with its sha256 for a safe edit; a binary file: its size only"""
        from urllib.parse import quote
        path = request.args.get("path", "")
        _looked("container.files.view", service, {"path": path})
        return _ops("GET", f"/containers/{service}/files/content?path={quote(path)}", timeout=120)


@blp.route("/admin/containers/<service>/files/properties")
class ContainerFileProperties(MethodView):
    """/api/v1/admin/containers/{service}/files/properties: GET properties of a file or folder in a container (R3.5):
    kind, size (a folder: everything in it, and how many files and folders), owner, group, permissions, when changed…"""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "path", "schema": {"type": "string"}}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, service):
        """Properties of a file or folder in a container (R3.5): kind, size (a folder: everything in it, and how many files
        and folders), owner, group, permissions, when changed and last read"""
        from urllib.parse import quote
        return _ops("GET", f"/containers/{service}/files/properties?path={quote(request.args.get('path', ''))}", timeout=150)


@blp.route("/admin/containers/<service>/files/download")
class ContainerFileDownload(MethodView):
    """/api/v1/admin/containers/{service}/files/download: GET a file from a container, or a folder as a zip; several
    (?path= more than once) as one zip (R3.5)."""
    @blp.doc(security=SECURITY, parameters=[{"in": "query", "name": "path", "schema": {"type": "string"}}])
    @require_auth("system.operate")
    def get(self, service):
        """A file from a container, or a folder as a zip; several (?path= more than once) as one zip (R3.5)"""
        import base64
        from urllib.parse import quote

        from flask import Response
        paths = [p for p in request.args.getlist("path") if p][:200]
        path = paths[0] if paths else ""
        if len(paths) > 1:
            out = _ops("GET", f"/containers/{service}/files/download?many={quote(chr(10).join(paths))}", timeout=600)
        else:
            out = _ops("GET", f"/containers/{service}/files/download?path={quote(path)}", timeout=300)
        _looked("container.files.download", service, {"path": path if len(paths) < 2 else paths, "name": out.get("name")})
        name = str(out.get("name") or "file").replace('"', "")
        return Response(base64.b64decode(out.get("content") or ""), mimetype="application/octet-stream",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@blp.route("/admin/alerts")
class Alerts(MethodView):
    """/api/v1/admin/alerts: GET containers not working now and the history of alerts and recoveries (R2.19), from
    the operations helper's watcher (it looks every minute, also while the API is down)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Containers not working now and the history of alerts and recoveries (R2.19), from the operations helper's
        watcher (it looks every minute, also while the API is down)"""
        import time
        for attempt in (1, 2, 3):             # a moment while ops starts again (a restart, an update) is not an alert
            try:
                return _ops_raw("GET", "/alerts", timeout=15)
            except Exception:  # noqa: BLE001
                if attempt < 3:
                    time.sleep(2)
        return {"open": [{"service": "ops", "kind": "stopped",
                          "text": "The operations helper (the ops container) is not answering: Containers, Hosts, backups "
                                  "and the alerts wait for it",
                          "since": None}], "history": [], "helper": False}


@blp.route("/admin/alerts/test")
class AlertTest(MethodView):
    """/api/v1/admin/alerts/test: POST a test alert {service}: the watcher tells it as if that container had stopped,
    then its recovery notice on the next look (the self-test uses it; nothing is stopped)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """A test alert {service}: the watcher tells it as if that container had stopped, then its recovery notice on
        the next look (the self-test uses it; nothing is stopped)"""
        _looked("container.alert.test", str((data or {}).get("service") or "api"))
        return _ops("POST", "/alerts/test", {"service": str((data or {}).get("service") or "api")})


@blp.route("/internal/container-alerts")
class ContainerAlertsIn(MethodView):
    """/api/v1/internal/container-alerts: POST for the operations helper only (X-Ops-Token): alerts, reminders and
    recoveries from its watcher become notifications for the IT Admins and Super Admins (an alert needs…"""
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    def post(self, data):
        """For the operations helper only (X-Ops-Token): alerts, reminders and recoveries from its watcher become
        notifications for the IT Admins and Super Admins (an alert needs action) and go to the webhooks (R2.19)"""
        import hmac
        token = os.environ.get("EAX_OPS_TOKEN", "")
        if not token or not hmac.compare_digest(request.headers.get("X-Ops-Token", ""), token):
            abort(403, message="Not allowed.")
        from .. import container_alerts
        with get_engine().begin() as conn:
            return {"told": container_alerts.tell(conn, (data or {}).get("events") or [])}


@blp.route("/admin/coverage")
class Coverage(MethodView):
    """/api/v1/admin/coverage: GET code coverage of the API since it started (D642; EAX_COVERAGE=on): the share of EA
    Explorer's lines run, by area and by file (the least covered first)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Code coverage of the API since it started (D642; EAX_COVERAGE=on): the share of EA Explorer's lines run, by
        area and by file (the least covered first). The self-test keeps it with its run"""
        from .. import coverage_probe
        return coverage_probe.report()


# ---------------------------------------------------------------- the sites (R2.1, D646)
def _sites_call(fn):
    from .. import sites
    try:
        with get_engine().begin() as conn:
            return fn(conn, sites)
    except EditError as exc:
        abort(exc.status, message=str(exc))


@blp.route("/sites")
class Sites(MethodView):
    """/api/v1/sites: GET every EA Explorer site (Local first) with its health (green, amber, red) from its public
    heartbeat, every 5 minutes; anyone signed in sees them and opens one to sign in…; POST add a site {name, url,
    note} (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """Every EA Explorer site (Local first) with its health (green, amber, red) from its public heartbeat, every 5
        minutes; anyone signed in sees them and opens one to sign in there (R2.1)"""
        return _sites_call(lambda c, s: {"sites": s.listing(c), "may_change": "super-admin" in (g.user.roles or ())})

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data):
        """Add a site {name, url, note} (Super Admins)"""
        def go(c, s):
            out = s.create(c, g.user, data or {})
            audit.record(c, actor=g.user.username, action="site.add", object_type="site", object_id=str(out["id"]),
                         details={"name": out["name"], "url": out["url"]})
            return out
        return _sites_call(go)


@blp.route("/sites/<sid>")
class Site(MethodView):
    """/api/v1/sites/{sid}: PUT change a site's name, address or note (Super Admins; Local's address comes from its
    settings); DELETE remove a site from the list (Super Admins; nothing happens to the site itself; Local stays)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, sid):
        """Change a site's name, address or note (Super Admins; Local's address comes from its settings)"""
        def go(c, s):
            out = s.update(c, g.user, sid, data or {})
            audit.record(c, actor=g.user.username, action="site.change", object_type="site", object_id=sid,
                         details={k: (data or {}).get(k) for k in ("name", "url", "note") if k in (data or {})})
            return out
        return _sites_call(go)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, sid):
        """Remove a site from the list (Super Admins; nothing happens to the site itself; Local stays)"""
        def go(c, s):
            out = s.delete(c, g.user, sid)
            audit.record(c, actor=g.user.username, action="site.remove", object_type="site", object_id=sid, details={})
            return out
        return _sites_call(go)


# ---------------------------------------------------------------- IP allow-listing (R5.2, D686)
def _caller_address() -> str:
    """The caller's address as the front door saw it (X-Real-IP: nginx's $remote_addr, after the trusted load
    balancers, R5.2)."""
    return request.headers.get("X-Real-IP") or request.remote_addr or ""


@blp.route("/admin/allow")
class AdminAllow(MethodView):
    """/api/v1/admin/allow: GET the IP allow lists per place, the addresses always allowed, the trusted load
    balancers and your own address; PUT saves the lists ({lists: {place: [{address, name, why}]}, trusted: [...]}),
    refusing one that would lock you out; nginx takes them at once (tested first)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The IP allow lists per place, the addresses always allowed, the trusted load balancers and your own address"""
        out = _ops("GET", "/allow")
        out["your_address"] = _caller_address()
        out["may_change"] = g.user.can("settings.manage")
        return out

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def put(self, data):
        """Saves the lists ({lists: {place: [{address, name, why}]}, trusted: [...]}), refusing one that would lock you
        out; nginx takes them at once (tested first)"""
        from .. import ip_allow
        try:
            clean = ip_allow.clean(data)
            current = _ops("GET", "/allow")
            ip_allow.guard(clean["lists"], _caller_address(), current.get("internal") or [])
        except ip_allow.Refused as exc:
            abort(409, message=str(exc))
        out = _ops("POST", "/allow", clean | {"by": g.user.username}, timeout=60)
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="security.allow_lists", object_type="settings",
                         object_id="allow", details={"lists": {p: [e["address"] for e in v] for p, v in clean["lists"].items()},
                                                     "trusted": [e["address"] for e in clean["trusted"]]})
        return out


@blp.route("/admin/allow/refused")
class AdminAllowRefused(MethodView):
    """/api/v1/admin/allow/refused: GET the addresses the front door refused (since the proxy started): the most
    refused, by place, the latest."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The addresses the front door refused (since the proxy started): the most refused, by place, the latest"""
        return _ops("GET", "/allow/refused")


# ---------------------------------------------------------------- multi-factor sign-in (R5.3, D690)
@blp.route("/admin/security/mfa")
class AdminMfa(MethodView):
    """/api/v1/admin/security/mfa: GET the multi-factor setting, who has a code set up and who has been asked to set
    one up."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The multi-factor setting, who has a code set up and who has been asked to set one up"""
        from .. import keycloak_upkeep as ku
        with get_engine().connect() as conn:
            mode = st.values(conn).get("mfa_mode", "off")
        try:
            status = ku.mfa_status()
        except Exception as exc:  # noqa: BLE001
            status = {"error": f"Keycloak could not be asked ({exc})"}
        return {"mode": mode, "modes": list(ku.MODES), "admin_roles": list(ku.ADMIN_ROLES), **status,
                "may_change": g.user.can("settings.manage")}


@blp.route("/admin/security/mfa/reset")
class AdminMfaReset(MethodView):
    """/api/v1/admin/security/mfa/reset: POST removes a person's authenticator ({username}): they set up a new one at
    their next sign-in."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """Removes a person's authenticator ({username}): they set up a new one at their next sign-in"""
        from .. import keycloak_upkeep as ku
        username = str((data or {}).get("username") or "").strip().lower()
        if not username:
            abort(400, message="username: whose authenticator to remove.")
        try:
            out = ku.reset_device(username)
        except ku.UpkeepError as exc:
            abort(409, message=str(exc))
        with get_engine().connect() as conn, conn.begin():
            audit.record(conn, actor=g.user.username, action="security.mfa_reset", object_type="person",
                         object_id=username, details=out)
        return out


# ---------------------------------------------------------------- the web log (R5.6)
@blp.route("/admin/logs/web")
class WebLog(MethodView):
    """/api/v1/admin/logs/web: GET the web log of a day (every call to the API and MCP):
    ?day=YYYY-MM-DD&since=HH:MM&until=&who=&path= &status=(a code|4xx|5xx|errors)&sort=(time|slowest)&page=N (500 a…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The web log of a day (every call to the API and MCP): ?day=YYYY-MM-DD&since=HH:MM&until=&who=&path=
        &status=(a code|4xx|5xx|errors)&sort=(time|slowest)&page=N (500 a page); with the slowest and most failing
        routes summed, and whether web log debug is on"""
        from urllib.parse import urlencode

        from .. import weblog
        keep = {k: request.args.get(k, "") for k in ("day", "since", "until", "who", "path", "status", "sort", "page")}
        out = _ops("GET", "/logs/web?" + urlencode(keep), timeout=60)
        weblog.forget()
        out["debug_until"] = weblog.until() if weblog.on() else ""
        return out


@blp.route("/admin/logs/web/<any(files, csv, zip):what>")
class WebLogFiles(MethodView):
    """/api/v1/admin/logs/web/{what}: GET files: the days kept; csv: a day as CSV (the same filters as the web log);
    zip: the raw files of a period (?start=&end=, base64)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, what):
        """files: the days kept; csv: a day as CSV (the same filters as the web log); zip: the raw files of a period
        (?start=&end=, base64)"""
        from urllib.parse import urlencode
        keep = {k: v for k, v in request.args.items()}
        return _ops("GET", f"/logs/web/{what}?" + urlencode(keep), timeout=120)


@blp.route("/admin/logs/clean-range")
class LogCleanRange(MethodView):
    """/api/v1/admin/logs/clean-range: POST deletes the container logs and the web log: {what: period, start, end} |
    {what: before, start} | {what: all} (Super Admin); a log backup is taken first."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """Deletes the container logs and the web log: {what: period, start, end} | {what: before, start} | {what: all}
        (Super Admin); a log backup is taken first. In the audit trail"""
        data = data or {}
        out = _ops("POST", "/logs/clean-range", {"what": data.get("what"), "start": data.get("start") or "",
                                                 "end": data.get("end") or "", "by": g.user.username}, timeout=300)
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="logs.delete", object_type="logs", object_id=str(data.get("what")),
                         details={"start": out.get("start"), "end": out.get("end"), "backup": out.get("backup"),
                                  "deleted": len(out.get("deleted") or [])})
        return out


@blp.route("/admin/logs/web-debug")
class WebLogDebug(MethodView):
    """/api/v1/admin/logs/web-debug: POST web log debug on for {minutes} (1 to 1440; 0 switches it off): each API
    call's input and answer written too, masked (R5.6)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """Web log debug on for {minutes} (1 to 1440; 0 switches it off): each API call's input and answer written too,
        masked (R5.6). Super Admin; in the audit trail"""
        from datetime import UTC, datetime, timedelta

        from .. import weblog
        try:
            minutes = int((data or {}).get("minutes") or 0)
        except (TypeError, ValueError):
            abort(400, message="minutes is a whole number, 0 to 1440.")
        if not 0 <= minutes <= 1440:
            abort(400, message="minutes is a whole number, 0 to 1440.")
        until = (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat(timespec="seconds") if minutes else ""
        with get_engine().begin() as conn:
            st.store(conn, {"web_log_debug_until": until})
            audit.record(conn, actor=g.user.username, action="logs.web_debug", object_type="logs", object_id="web",
                         details={"minutes": minutes, "until": until})
        st.forget()
        weblog.forget()
        return {"until": until, "on": bool(until)}


# ---------------------------------------------------------------- alerts (R5.9, D689)
@blp.route("/admin/alerting")
class Alerting(MethodView):
    """/api/v1/admin/alerting: GET every check with its state, since when, acknowledged by whom; the open alerts
    first; the silences; each check's levels; the email settings (no password)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Every check with its state, since when, acknowledged by whom; the open alerts first; the silences; each check's
        levels; the email settings (no password)"""
        from .. import alerts
        with get_engine().connect() as conn:
            return alerts.overview(conn)


@blp.route("/admin/alerting/summary")
class AlertsSummary(MethodView):
    """/api/v1/admin/alerting/summary: GET how many alerts are open, critical and not acknowledged (the Health page
    and the header)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """How many alerts are open, critical and not acknowledged (the Health page and the header)"""
        from .. import alerts
        with get_engine().connect() as conn:
            o = alerts.overview(conn)
        return {k: o[k] for k in ("open", "critical", "unacknowledged")}


@blp.route("/admin/alerting/<path:key>/<any(ack, config, delete):what>")
class AlertOne(MethodView):
    """/api/v1/admin/alerting/{key}/{what}: POST ack {note}: acknowledge an open alert (it stops repeating); config
    {warning, critical, enabled, hold}: a check's levels (Super Admin); delete: remove a check a person…"""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data, key, what):
        """ack {note}: acknowledge an open alert (it stops repeating); config {warning, critical, enabled, hold}: a check's
        levels (Super Admin); delete: remove a check a person added (Super Admin)"""
        from .. import alerts
        data = data or {}
        if what in ("config", "delete") and not g.user.can("settings.manage"):
            abort(403, message="Only a Super Admin changes the checks.")
        try:
            with get_engine().begin() as conn:
                if what == "ack":
                    out = alerts.acknowledge(conn, key, g.user.username, str(data.get("note") or ""))
                elif what == "config":
                    out = alerts.set_config(conn, key, data)
                else:
                    n = conn.execute(text("DELETE FROM core.alert_custom WHERE key = :k"), {"k": key.removeprefix("custom:")}).rowcount
                    conn.execute(text("DELETE FROM core.alert_checks WHERE check_key = :k"), {"k": key})
                    out = {"deleted": n}
                audit.record(conn, actor=g.user.username, action=f"alert.{what}", object_type="alert", object_id=key, details=data)
                return out
        except ValueError as exc:
            abort(400, message=str(exc))


@blp.route("/admin/alerting/silence")
class AlertSilence(MethodView):
    """/api/v1/admin/alerting/silence: POST silence a check, or every check (key empty or *: a planned downtime), for
    {minutes} with a {reason}."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Silence a check, or every check (key empty or *: a planned downtime), for {minutes} with a {reason}"""
        from .. import alerts
        data = data or {}
        try:
            with get_engine().begin() as conn:
                out = alerts.silence(conn, str(data.get("key") or "*"), int(data.get("minutes") or 0), g.user.username,
                                     str(data.get("reason") or ""))
                audit.record(conn, actor=g.user.username, action="alert.silence", object_type="alert", object_id=out["check"], details=data)
                return out
        except (TypeError, ValueError) as exc:
            abort(400, message=str(exc))


@blp.route("/admin/alerting/custom")
class AlertCustom(MethodView):
    """/api/v1/admin/alerting/custom: POST a check of your own: {key, name, kind: url|sql, target, warning,
    critical}: an address that answers within a time (ms), or one read-only SELECT that returns a number."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """A check of your own: {key, name, kind: url|sql, target, warning, critical}: an address that answers within a
        time (ms), or one read-only SELECT that returns a number"""
        from .. import alerts
        try:
            with get_engine().begin() as conn:
                out = alerts.add_custom(conn, data or {}, g.user.username)
                audit.record(conn, actor=g.user.username, action="alert.custom", object_type="alert", object_id=out["key"],
                             details=data or {})
                return out
        except ValueError as exc:
            abort(400, message=str(exc))


@blp.route("/admin/alerting/history")
class AlertHistory(MethodView):
    """/api/v1/admin/alerting/history: GET every change of state in the last 90 days, as CSV ({name, csv})."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Every change of state in the last 90 days, as CSV ({name, csv})"""
        from .. import alerts
        with get_engine().connect() as conn:
            return {"name": "alert-history.csv", "csv": alerts.history_csv(conn)}


@blp.route("/admin/alerting/test-email")
class AlertTestEmail(MethodView):
    """/api/v1/admin/alerting/test-email: POST sends a test email to the alert addresses (or {to}) through the mail
    server in the config file."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """Sends a test email to the alert addresses (or {to}) through the mail server in the config file"""
        from .. import alerts
        with get_engine().connect() as conn:
            to = [a for a in str((data or {}).get("to") or "").split(",") if "@" in a] or alerts.recipients_of(conn)
        why = alerts.send_email(to, "[EA Explorer] Test of the alert email", "This is a test of the alert email (R5.9).")
        if why:
            abort(409, message=why)
        return {"sent_to": to}


# ---------------------------------------------------------------- database maintenance (R5.12, D691)
@blp.route("/admin/db-maintenance")
class DbMaintenance(MethodView):
    """/api/v1/admin/db-maintenance: GET the last check's findings, the runs (check, tidy, compact, clear, locks),
    the window and what would stop a run now."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The last check's findings, the runs (check, tidy, compact, clear, locks), the window and what would stop a run now"""
        from .. import dbmaint
        with get_engine().connect() as conn:
            return {"last_check": dbmaint.last_check(conn), "history": dbmaint.history(conn), "settings": dbmaint.settings_of(conn),
                    "busy": dbmaint.busy_reason()}


@blp.route("/admin/db-integrity")
class DbIntegrity(MethodView):
    """/api/v1/admin/db-integrity (R6.6.1, D750): GET the last integrity check (what is wrong, what was fixed, the recent
    records); POST check every database now, in the background (the safe fixes made after a backup)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The last integrity check: what is wrong, what was fixed, the recent records (R6.6.1)"""
        from .. import dbintegrity
        with get_engine().connect() as conn:
            return {"last": dbintegrity.last(conn)}

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(202, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Check every database's integrity now, in the background: only a check ({}), or with the safe fixes after a
        backup ({fix: true}, the maintenance page up while the backup is taken) (R6.6.1)"""
        from ..jobs import integrity_after
        fix = bool((data or {}).get("fix"))
        if fix:
            from .maintenance_gate import needs_yes
            needs_yes(data, "The database's safe fixes (a backup first, when there is none from the last day)")
        integrity_after(f"{'fixes' if fix else 'a check'} asked for by {g.user.username}", g.user.username, fix=fix)
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="db.integrity", object_type="database", object_id="all",
                         details={"fix": fix})
        return {"queued": True, "message": ("Checking every database and making the safe fixes, after a backup (the maintenance "
                                            "page is up while it is taken)" if fix else
                                            "Checking every database in the background, nothing changed")
                + " (minutes to an hour on a large one); the admins are told what was found."}


@blp.route("/admin/db-integrity/repair")
class DbIntegrityRepair(MethodView):
    """/api/v1/admin/db-integrity/repair (R6.6.1): POST {finding} a preview of the orphan rows a repair would remove,
    with a confirmation; POST {confirm} the rows removed (Super Admins; the rows kept in the run's record)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """{finding}: a preview of the orphan rows a repair would remove; {confirm}: removed (Super Admins) (R6.6.1)"""
        from .. import dbintegrity, dbmaint
        data = data or {}
        if not g.user.can("settings.manage"):
            abort(403, message="Only a Super Admin removes rows.")
        try:
            if data.get("confirm"):
                if why := dbmaint.busy_reason():
                    abort(409, message=f"Not now: {why}.")
                out = dbintegrity.repair(str(data["confirm"]))
                with get_engine().begin() as conn:
                    dbmaint.record(conn, "repair", g.user.username, actions=[out])
                    audit.record(conn, actor=g.user.username, action="db.repair", object_type="database",
                                 object_id=out["database"], details={"table": out["table"], "removed": out["removed"]})
                return {k: v for k, v in out.items() if k != "rows"}
            return dbintegrity.repair_preview(dict(data.get("finding") or {}))
        except ValueError as exc:
            abort(400, message=str(exc))


DB_ACTIONS = ("check", "tidy", "clear", "compact", "compact-preview", "locks", "stop", "stop-preview")


@blp.route("/admin/db-maintenance/<string:what>")
class DbMaintenanceDo(MethodView):
    """/api/v1/admin/db-maintenance/{what}: GET locks: who blocks whom, on every database; POST check: every database
    now; tidy {dry_run}: what the check finds, done (nothing locked); clear: the keep-for rules now; compact-preview
    {database, table} then compact…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, what):
        """locks: who blocks whom, on every database"""
        from .. import dbmaint
        if what not in DB_ACTIONS:
            abort(404, message=f"No {what}: one of {', '.join(DB_ACTIONS)}.")
        if what != "locks":
            abort(405, message="Use POST.")
        return {"sessions": dbmaint.locks()}

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data, what):
        """check: every database now; tidy {dry_run}: what the check finds, done (nothing locked); clear: the keep-for
        rules now; compact-preview {database, table} then compact {confirm}: VACUUM FULL (locks the table; Super Admin);
        stop-preview {pid, end} then stop {confirm}: cancel a query or end a session"""
        from .. import dbmaint
        data = data or {}
        if what not in DB_ACTIONS:
            abort(404, message=f"No {what}: one of {', '.join(DB_ACTIONS)}.")
        if what in ("compact", "compact-preview", "clear") and not g.user.can("settings.manage"):
            abort(403, message="Only a Super Admin compacts a table or clears by the keep-for rules.")
        if what in ("tidy", "compact", "clear") and not data.get("dry_run"):
            why = dbmaint.busy_reason()
            if why:
                abort(409, message=f"Not now: {why}. Try again when it has finished.")
        try:
            if what == "check":
                out = dbmaint.check()
                kind, found, done = "check", out["findings"], []
            elif what == "tidy":
                found = dbmaint.check()["findings"]
                done = dbmaint.tidy(found, dry_run=bool(data.get("dry_run")))
                out, kind = {"actions": done}, "tidy"
                if data.get("dry_run"):
                    return out
            elif what == "compact-preview":
                return dbmaint.compact_preview(str(data.get("database") or ""), str(data.get("table") or ""))
            elif what == "compact":
                r = dbmaint.compact(str(data.get("confirm") or ""))
                out, kind, found, done = r, "compact", [], [r]
            elif what == "stop-preview":
                return dbmaint.stop_preview(int(data.get("pid") or 0), bool(data.get("end")))
            elif what == "stop":
                r = dbmaint.stop(str(data.get("confirm") or ""))
                out, kind, found, done = r, "locks", [], [r]
            elif what == "clear":
                with get_engine().begin() as conn:
                    r = dbmaint.clear(conn, g.user.username)
                out, kind, found, done = r, "clear", [], [r]
            else:
                abort(405, message="Use GET for locks.")
        except ValueError as exc:
            abort(400, message=str(exc))
        with get_engine().begin() as conn:
            dbmaint.record(conn, kind, g.user.username, found, done)
            audit.record(conn, actor=g.user.username, action=f"db.{what}", object_type="database", object_id=what,
                         details={"found": len(found), "done": len(done)})
        return out


# ---------------------------------------------------------------- the optimisation report (R5.1, D697)
def _optimise_view(conn, rep: dict | None) -> dict | None:
    """IT and Super Admins see the whole report; a Model Admin only what is theirs to decide (their models)."""
    from .. import permissions as P
    if rep is None or g.user.can("system.operate"):
        return rep
    mine = [s for s in rep["report"]["suggestions"] if s.get("params", {}).get("model")
            and "model-admin" in P.model_roles(conn, g.user.username, s["params"]["model"])]
    return {**rep, "report": {**rep["report"], "suggestions": mine}}


@blp.route("/admin/optimisation")
class Optimisation(MethodView):
    """/api/v1/admin/optimisation: GET the newest optimisation report, compared with the one before, and what of it
    was applied; POST measure now: a new report (nothing is changed)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The newest optimisation report, compared with the one before, and what of it was applied"""
        from .. import optimise as op
        with get_engine().connect() as conn:
            two = op.latest(conn, 2)
            now = _optimise_view(conn, two[0] if two else None)
            before = two[1]["report"] if len(two) > 1 else None
        return {"report": now, "compared": op.compare(two[0]["report"], before) if two else None,
                "unused_days": st.values().get("optimise_unused_days"), "may_measure": g.user.can("system.operate")}

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Measure now: a new report (nothing is changed)"""
        from .. import optimise as op
        with get_engine().begin() as conn:
            r = op.measure(conn)
            rid = op.save(conn, r, g.user.username)
            audit.record(conn, actor=g.user.username, action="optimise.report", object_type="optimisation", object_id=str(rid),
                         details={"suggestions": len(r["suggestions"])})
        return {"id": rid, **r}


@blp.route("/admin/optimisation/<int:report_id>/apply")
class OptimisationApply(MethodView):
    """/api/v1/admin/optimisation/{report_id}/apply: POST {key, choice}: one suggestion applied, for a whole model or
    project (history: choice condense or remove)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, report_id):
        """{key, choice}: one suggestion applied, for a whole model or project (history: choice condense or remove)"""
        from .. import optimise as op
        data = data or {}
        if g.user.auditor_view:
            abort(403, message="Auditor: view only.")
        try:
            with get_engine().begin() as conn:
                return op.apply(conn, g.user, report_id, str(data.get("key") or ""), str(data.get("choice") or ""))
        except op.NotAllowed as exc:
            abort(403, message=str(exc))
        except EditError as exc:
            abort(exc.status, message=str(exc))
        except ValueError as exc:
            abort(409, message=str(exc))


@blp.route("/admin/optimisation/<int:report_id>/xlsx")
class OptimisationExcel(MethodView):
    """/api/v1/admin/optimisation/{report_id}/xlsx: GET the report as an Excel workbook."""
    @blp.doc(security=SECURITY)
    @require_auth()
    def get(self, report_id):
        """The report as an Excel workbook"""
        from flask import Response

        from .. import optimise as op
        with get_engine().connect() as conn:
            row = conn.execute(text("SELECT id, at, by_whom, report, applied FROM core.optimisation_reports WHERE id = :i"),
                               {"i": report_id}).mappings().first()
            if not row:
                abort(404, message="No such report.")
            rep = _optimise_view(conn, dict(row))
        body = op.workbook(rep["report"], rep["applied"])
        return Response(body, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="eaexplorer-optimisation-{report_id}.xlsx"'})


# ---------------------------------------------------------------- the server sizing estimate (R5.19)
@blp.route("/admin/sizing")
class Sizing(MethodView):
    """/api/v1/admin/sizing: GET the defaults (a laptop's figures), the assumptions a person may change, the saved
    estimates, and this installation's real memory per container (to set beside an estimate); POST {users, models,
    model_size, projects, documents_per_project, reports, documents, mcp, discovery, backups_kept, headroom, node_gb,
    node_cores, assumptions, save: name}…"""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The defaults (a laptop's figures), the assumptions a person may change, the saved estimates, and this
        installation's real memory per container (to set beside an estimate)"""
        from .. import resources as rs
        from .. import sizing
        with get_engine().connect() as conn:
            saved = [{**dict(r), "at": r["at"].isoformat()} for r in conn.execute(text(
                "SELECT id, at, by_whom, name, result->'server' AS server FROM core.sizing_estimates ORDER BY at DESC LIMIT 50")).mappings()]
            try:
                from .. import databases
                on = databases.on("operations", conn)
                rows = [dict(r) for r in on.execute(text(f"SELECT * FROM {rs.TABLE} WHERE at > now() - interval '7 days' ORDER BY at")).mappings()]
                measured = (rs.merge(rows) or {}).get("containers") or []
            except Exception:  # noqa: BLE001 - no resource history: nothing to set beside it
                measured = []
        here = sizing.estimate(sizing.LAPTOP)
        return {"defaults": {**sizing.LAPTOP, "headroom": sizing.HEADROOM}, "assumptions": sizing.DATA, "saved": saved,
                "model_version": sizing.VERSION, "changes": sizing.CHANGES, "measured": sizing.against(here, measured)}

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """{users, models, model_size, projects, documents_per_project, reports, documents, mcp, discovery, backups_kept,
        headroom, node_gb, node_cores, assumptions, save: name}: the estimate (saved when a name is given)"""
        from .. import sizing
        data = dict(data or {})
        try:
            out = sizing.estimate(data)
        except ValueError as exc:
            abort(400, message=str(exc))
        name = str(data.get("save") or "").strip()
        if name:
            with get_engine().begin() as conn:
                out["id"] = conn.execute(text("INSERT INTO core.sizing_estimates (by_whom, name, result) VALUES (:b, :n, CAST(:r AS jsonb)) "
                                              "RETURNING id"), {"b": g.user.username, "n": name[:200], "r": json.dumps(out)}).scalar()
                audit.record(conn, actor=g.user.username, action="sizing.saved", object_type="sizing", object_id=str(out["id"]),
                             details={"name": name, "server": out["server"]})
        return out


@blp.route("/admin/sizing/<int:estimate_id>/<any(json, xlsx, override):fmt>")
class SizingFile(MethodView):
    """/api/v1/admin/sizing/{estimate_id}/{fmt}: GET a saved estimate: as JSON, as Excel, or the compose override to
    paste."""
    @blp.doc(security=SECURITY)
    @require_auth("system.operate")
    def get(self, estimate_id, fmt):
        """A saved estimate: as JSON, as Excel, or the compose override to paste"""
        from flask import Response

        from .. import sizing
        with get_engine().connect() as conn:
            row = conn.execute(text("SELECT name, result FROM core.sizing_estimates WHERE id = :i"), {"i": estimate_id}).mappings().first()
        if not row:
            abort(404, message="No such estimate.")
        r = row["result"]
        if fmt == "json":
            return r
        if fmt == "override":
            return Response(r.get("override") or sizing.override(r["containers"]), mimetype="text/yaml",
                            headers={"Content-Disposition": f'attachment; filename="docker-compose.sizing-{estimate_id}.yml"'})
        return Response(sizing.workbook(r), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="eaexplorer-sizing-{estimate_id}.xlsx"'})
