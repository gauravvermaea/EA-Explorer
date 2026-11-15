"""The service desk (R5.11, D692): the catalogue and the requests (eax/servicedesk.py).

GET  /service-desk/catalogue                 what people can ask for: the groups, then the types (enabled; ?all=1 every
                                             type, Super Admins)
GET  /service-desk/people                    who a request can be assigned to (Super Admins, R5.27)
PUT  /service-desk/catalogue/<key>           add or change a request type (Super Admin)
GET  /service-desk/tickets                   ?view=mine|queue|all&status=open|all|<status>&q=
POST /service-desk/tickets                   raise one {type, title, fields, priority, note, group (for "other")}
GET  /service-desk/tickets/<id>              one request with its history and files (REQ-12 or 12)
POST /service-desk/tickets/<id>/<action>     comment {note} | assign {to; "" hands it back} | status {status, note} | approve {note} |
                                             decline {note} | cancel {note} | priority {priority}
POST /service-desk/tickets/<id>/do           what it asks for, done (or the wizard's address with its details)
POST /service-desk/tickets/<id>/files        a file (multipart, 10 MB at most);  GET .../files/<f> to download it
GET  /service-desk/stats                     open by team, done, the average time to done, targets met
"""

from __future__ import annotations

from flask import Response, g, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit
from .. import servicedesk as sd
from ..auth import require_auth
from ..db import get_engine
from .models import Free, FreeIn

blp = Blueprint("servicedesk", __name__, url_prefix="/api/v1/service-desk", description="The service desk (R5.11)")
SECURITY = [{"bearerAuth": []}]


def _fail(exc: sd.DeskError):
    abort(exc.status, message=str(exc))


@blp.route("/catalogue")
class Catalogue(MethodView):
    """/api/v1/service-desk/catalogue: GET what people can ask for, by area."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """What people can ask for, by area"""
        everything = request.args.get("all") == "1" and g.user.can("settings.manage")
        with get_engine().connect() as conn:
            types = sd.catalogue(conn, everything)
            return {"groups": sd.groups(types), "types": types, "other": sd.OTHER, "field_kinds": list(sd.FIELD_KINDS),
                    "may_change": g.user.can("settings.manage")}


@blp.route("/people")
class People(MethodView):
    """/api/v1/service-desk/people: GET who a request can be assigned to: everyone who has signed in (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """Who a request can be assigned to: everyone who has signed in (Super Admins)"""
        if "super-admin" not in set(g.user.roles or []):
            abort(403, message="Only a Super Admin assigns requests.")
        with get_engine().connect() as conn:
            return {"people": sd.people(conn)}


@blp.route("/catalogue/<string:key>")
class CatalogueType(MethodView):
    """/api/v1/service-desk/catalogue/{key}: PUT adds or changes a request type: {name, area (its group), about, form:
    [{name, label, kind, required, choices}], target_hours, wizard, enabled}."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def put(self, data, key):
        """Adds or changes a request type: {name, area (its group), about, form: [{name, label, kind, required,
        choices}], target_hours, wizard, enabled}"""
        try:
            with get_engine().begin() as conn:
                out = sd.save_type(conn, {**(data or {}), "key": key}, g.user.username)
                audit.record(conn, actor=g.user.username, action="servicedesk.type", object_type="service_type", object_id=key,
                             details={k: (data or {}).get(k) for k in ("name", "area", "enabled")})
                return out
        except sd.DeskError as exc:
            _fail(exc)


@blp.route("/tickets")
class Tickets(MethodView):
    """/api/v1/service-desk/tickets: GET requests: ?view=mine (what I asked for) | queue (what my teams work on or
    approve) | all (Super Admins, Auditors); &status=open|all|<status>&q=words; POST raise a request: {type, title,
    fields: {...}, priority, note}."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """Requests: ?view=mine (what I asked for) | queue (what my teams work on or approve) | all (Super Admins,
        Auditors); &status=open|all|<status>&q=words"""
        with get_engine().connect() as conn:
            return sd.listing(conn, g.user.username, g.user.roles, request.args.get("view", "mine"),
                              request.args.get("status", "open"), request.args.get("q", ""))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data):
        """Raise a request: {type, title, fields: {...}, priority, note}"""
        try:
            with get_engine().begin() as conn:
                out = sd.raise_ticket(conn, g.user.username, data or {})
                audit.record(conn, actor=g.user.username, action="servicedesk.raise", object_type="service_ticket",
                             object_id=out["number"], details={"type": out["type_key"]})
                return out
        except sd.DeskError as exc:
            _fail(exc)


@blp.route("/tickets/<string:ident>")
class Ticket(MethodView):
    """/api/v1/service-desk/tickets/{ident}: GET one request with its history and its files."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, ident):
        """One request with its history and its files"""
        try:
            with get_engine().connect() as conn:
                return sd.get(conn, ident, g.user.username, g.user.roles)
        except (sd.DeskError, ValueError) as exc:
            abort(getattr(exc, "status", 404), message=str(exc))


@blp.route("/tickets/<string:ident>/<any(comment, assign, status, approve, decline, cancel, priority, do):action>")
class TicketAction(MethodView):
    """/api/v1/service-desk/tickets/{ident}/{action}: POST comment, assign, status, approve, decline, cancel,
    priority; do: what it asks for, done (or the wizard)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, ident, action):
        """comment, assign, status, approve, decline, cancel, priority; do: what it asks for, done (or the wizard)"""
        try:
            with get_engine().begin() as conn:
                out = (sd.run_wizard(conn, ident, g.user.username, g.user.roles) if action == "do"
                       else sd.act(conn, ident, g.user.username, g.user.roles, action, data or {}))
                audit.record(conn, actor=g.user.username, action=f"servicedesk.{action}", object_type="service_ticket",
                             object_id=str(ident).upper(), details={k: v for k, v in (data or {}).items() if k != "body"})
                return out
        except (sd.DeskError, ValueError) as exc:
            abort(getattr(exc, "status", 400), message=str(exc))


@blp.route("/tickets/<string:ident>/files")
class TicketFiles(MethodView):
    """/api/v1/service-desk/tickets/{ident}/files: POST a file for the request (multipart field "file", 10 MB at
    most)."""
    @blp.doc(security=SECURITY)
    @blp.response(201, Free)
    @require_auth()
    def post(self, ident):
        """A file for the request (multipart field "file", 10 MB at most)"""
        f = request.files.get("file")
        if not f:
            abort(400, message="Send the file as the multipart field 'file'.")
        try:
            with get_engine().begin() as conn:
                return sd.add_file(conn, ident, g.user.username, g.user.roles, f.filename or "file", f.mimetype or "", f.read())
        except sd.DeskError as exc:
            _fail(exc)


@blp.route("/tickets/<string:ident>/files/<int:fid>")
class TicketFile(MethodView):
    """/api/v1/service-desk/tickets/{ident}/files/{fid}: GET download a file of the request."""
    @blp.doc(security=SECURITY)
    @require_auth()
    def get(self, ident, fid):
        """Download a file of the request"""
        try:
            with get_engine().connect() as conn:
                data, name, mime = sd.file_of(conn, ident, g.user.username, g.user.roles, fid)
        except sd.DeskError as exc:
            _fail(exc)
        return Response(data, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{name.replace(chr(34), "")}"'})


@blp.route("/stats")
class Stats(MethodView):
    """/api/v1/service-desk/stats: GET open by team, done in 30 days, the average time to done, how many met their
    target."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Open by team, done in 30 days, the average time to done, how many met their target"""
        with get_engine().connect() as conn:
            return sd.stats(conn)
