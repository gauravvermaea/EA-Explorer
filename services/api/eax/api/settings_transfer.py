"""Settings and admin configuration, exported and imported (Release 6.7, D755; see eax/settings_transfer.py).

Super Admins (System Admin > Settings import and export):
GET  /admin/settings-transfer             the parts, and the safety copies kept before each import (newest first)
POST /admin/settings-transfer/export      {parts}: the settings file (JSON), to save
POST /admin/settings-transfer/preview     {file, parts}: every difference, by part (here and in the file)
POST /admin/settings-transfer/import      {file, picks: {part: [keys] | "all"}, accept_maintenance}: a safety copy
                                          first, then the differences picked; each change in the audit trail
POST /admin/settings-transfer/undo        {copy}: the settings that copy kept put back (itself undoable)

git is one more place for the file: POST /git/push {source: settings, parts, ...}, then /git/list and /git/fetch
(eax/api/pairing.py), the fetched file previewed and imported here like one chosen on this computer.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime

from flask import Response, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import settings_transfer as st
from ..auth import require_auth
from ..db import get_engine
from ..metamodel_edit import EditError
from .admin import _caller_address
from .models import Free, FreeIn

blp = Blueprint("settings_transfer", __name__, url_prefix="/api/v1",
                description="Settings and admin configuration exported and imported (Release 6.7)")
SECURITY = [{"bearerAuth": []}]


def _super() -> None:
    if "super-admin" not in (g.user.roles or ()):
        abort(403, message="Only a Super Admin exports or imports the settings.")


def _site() -> str:
    return os.environ.get("EAX_INSTALLATION_NAME", "")


def _roles() -> list[str]:
    return list(g.user.roles or [])


def file_name(site: str) -> str:
    """eax-settings-<site>-<UTC date and time>.json (a name gitpackages accepts)."""
    tag = re.sub(r"[^A-Za-z0-9-]+", "-", site or "site").strip("-")[:40] or "site"
    return f"eax-settings-{tag}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"


def settings_file(parts) -> tuple[bytes, str]:
    """The settings file's bytes and name (also what git is sent)."""
    try:
        with get_engine().connect() as conn:
            body = st.export(conn, parts, by=g.user.username, site=_site())
    except st.TransferError as exc:
        abort(exc.status, message=str(exc))
    return json.dumps(body, indent=1, sort_keys=True).encode(), file_name(_site())


def _keep(why: str):
    """The safety copy kept in a transaction of its own: it stays even when the import then fails."""
    def keep(body: dict, parts: list[str]) -> str:
        with get_engine().begin() as c:
            return st.keep_copy(c, body, parts, g.user.username, why)
    return keep


def _file_of(data: dict):
    raw = data.get("file")
    if not raw:
        abort(400, message="Choose a settings file (made by Export settings or eax settings export).")
    return raw


def _gate(data: dict, raw, picks: dict) -> None:
    """A schedule the import turns on that puts the maintenance page up later: asked first, as everywhere (428)."""
    from .maintenance_gate import LATER, needs_yes
    try:
        f = st.load(raw)
    except st.TransferError:
        return                                   # refused properly by take()
    wanted = picks.get("schedules")
    for key, v in (f["parts"].get("schedules") or {}).items():
        if wanted == "all" or key in (wanted or []):
            said = st.maintenance_of("schedules", key, v)
            if said:
                needs_yes(data, f"{said} (the schedule {key.split(':', 1)[1]})", LATER)


@blp.route("/admin/settings-transfer")
class SettingsTransfer(MethodView):
    """/api/v1/admin/settings-transfer: GET the parts and the safety copies."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def get(self):
        """The parts a settings file carries, and the safety copies kept before each import (newest first)"""
        _super()
        with get_engine().connect() as conn:
            kept = st.copies(conn)
        return {"parts": [{"id": k, "title": t, "carries": c, "where": "ops" if k in st.OPS_PARTS else "database"}
                          for k, (t, c) in st.PARTS.items()], "copies": kept, "format": st.FORMAT, "site": _site()}


@blp.route("/admin/settings-transfer/export")
class SettingsExport(MethodView):
    """/api/v1/admin/settings-transfer/export: POST {parts}: the settings file."""
    @blp.doc(security=SECURITY, responses={"200": {"description": "The settings file (JSON)"}})
    @blp.arguments(FreeIn)
    @require_auth("settings.manage")
    def post(self, data):
        """The settings file of the parts chosen (all when none): never content, people, a password, key or certificate"""
        _super()
        body, name = settings_file((data or {}).get("parts"))
        with get_engine().begin() as conn:
            st._record(conn, g.user.username, "settings.export", "file", name, {"parts": list(json.loads(body)["parts"])})
        return Response(body, mimetype="application/json", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@blp.route("/admin/settings-transfer/preview")
class SettingsPreview(MethodView):
    """/api/v1/admin/settings-transfer/preview: POST {file, parts}: every difference, by part."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """Every difference between this installation and the file, by part: nothing is changed"""
        _super()
        data = data or {}
        try:
            with get_engine().connect() as conn:
                return st.preview(conn, _file_of(data), data.get("parts"))
        except st.TransferError as exc:
            abort(exc.status, message=str(exc))


@blp.route("/admin/settings-transfer/import")
class SettingsImport(MethodView):
    """/api/v1/admin/settings-transfer/import: POST {file, picks, accept_maintenance}: the differences picked taken."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """A safety copy first, then the differences picked ({part: [keys] or "all"}); each change in the audit trail"""
        _super()
        data = data or {}
        raw, picks = _file_of(data), data.get("picks") or {}
        if not isinstance(picks, dict) or not picks:
            abort(400, message="Tick at least one difference to take.")
        _gate(data, raw, picks)
        try:
            with get_engine().begin() as conn:
                return st.take(conn, raw, picks, g.user.username, caller=_caller_address(), roles=_roles(),
                               keep=_keep("import"))
        except st.TransferError as exc:
            abort(exc.status, message=str(exc))
        except (EditError, ValueError, LookupError, PermissionError) as exc:
            abort(getattr(exc, "status", 400), message=f"Nothing was changed: {exc}")


@blp.route("/admin/settings-transfer/undo")
class SettingsUndo(MethodView):
    """/api/v1/admin/settings-transfer/undo: POST {copy}: the settings that safety copy kept put back."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, data):
        """The settings a safety copy kept put back (a new safety copy first, so the undo can be undone too)"""
        _super()
        try:
            with get_engine().begin() as conn:
                return st.undo(conn, str((data or {}).get("copy") or ""), g.user.username, caller=_caller_address(),
                               roles=_roles(), keep=_keep("undo"))
        except st.TransferError as exc:
            abort(exc.status, message=str(exc))
        except (EditError, ValueError, LookupError, PermissionError) as exc:
            abort(getattr(exc, "status", 400), message=f"Nothing was changed: {exc}")
