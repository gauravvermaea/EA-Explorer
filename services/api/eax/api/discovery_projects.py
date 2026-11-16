"""Enterprise discovery (R5.5): discovery projects, their sources, the runs the people's own AI makes, and where an
element was found. The rules are in eax/discovery_projects.py; the AI runs discovery through MCP (eax/mcp_discovery.py).

GET    /discovery-projects                               the projects you may see, with the kinds of source
POST   /discovery-projects                               set one up (Discovery Admin or Super Admin)
GET    /discovery-projects/<p>                           it, its sources and its runs
PUT    /discovery-projects/<p>    DELETE /discovery-projects/<p>
POST   /discovery-projects/<p>/sources                   add a source   PUT/DELETE /discovery-projects/<p>/sources/<s>
POST   /discovery-projects/test-link                     Test the link: {kind, location, sign_in, secret{...}, project?, source?}
                                                         (the sign-in is used once and forgotten; only the result is kept)
GET    /discovery-runs/<r>                               a run's report
POST   /discovery-runs/<r>/may-be-same/<f>               mark a "may be the same as" flag dealt with
GET    /models/<m>/entities/<e>/found-in                 where an element was found
"""

from __future__ import annotations

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit
from .. import discovery_projects as dp
from .. import repository as repo
from ..auth import require_auth
from ..db import get_engine
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("discovery_projects", __name__, url_prefix="/api/v1",
                description="Enterprise discovery: discovery projects, their sources and runs; the AI runs them through MCP (R5.5)")
SECURITY = [{"bearerAuth": []}]


def _do(fn, write: bool = False, action: str = "", obj: str = "", details: dict | None = None):
    try:
        engine = get_engine()
        with (engine.begin() if write else engine.connect()) as conn:
            out = fn(conn)
            if action:
                audit.record(conn, actor=g.user.username, action=action, object_type="discovery-project",
                             object_id=str(obj), details=details or {}, request_id=getattr(g, "request_id", None))
            return out
    except (repo.NotFound, EditError) as exc:
        abort(getattr(exc, "status", 404) if isinstance(exc, EditError) else 404, message=str(exc))


@blp.route("/discovery-projects")
class Projects(MethodView):
    """/api/v1/discovery-projects: GET the discovery projects you may see; POST set one up {name, purpose, target_model,
    read_default new|all, gone_default mark|delete, schedule none|daily|weekly|monthly, schedule_day, schedule_time}."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The discovery projects you may see, with the kinds of source and sign-in"""
        return _do(lambda c: dp.listing(c, g.user))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data):
        """Set up a discovery project (Discovery Admin or Super Admin)"""
        return _do(lambda c: dp.create(c, g.user, data or {}), write=True, action="discovery.project.created",
                   obj=(data or {}).get("name", ""))


@blp.route("/discovery-projects/test-link")
class TestLink(MethodView):
    """/api/v1/discovery-projects/test-link: POST {kind, location, sign_in, secret: {token | username, password |
    certificate, private_key}, project, source}: whether the source answers. The sign-in is used once and forgotten."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data):
        """Test the link of a source (the sign-in is used once, never kept or logged)"""
        d = dict(data or {})
        secret = d.pop("secret", None) or {}
        try:
            out = dp.test_link(g.user, d.get("kind", ""), d.get("location", ""), d.get("sign_in", "none"), secret)
        except EditError as exc:
            abort(exc.status, message=str(exc))
        finally:
            secret.clear()
        if d.get("project") and d.get("source"):
            _do(lambda c: dp.record_test(c, g.user, d["project"], d["source"], out), write=True,
                action="discovery.source.tested", obj=d["project"], details={"source": d["source"], "ok": out["ok"]})
        return out


@blp.route("/discovery-projects/<string:pid>")
class Project(MethodView):
    """/api/v1/discovery-projects/{pid}: GET a discovery project with its sources and runs; PUT change it; DELETE it."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, pid):
        """A discovery project with its sources and runs"""
        return _do(lambda c: dp.detail(c, g.user, pid))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, pid):
        """Change a discovery project"""
        return _do(lambda c: dp.update(c, g.user, pid, data or {}), write=True, action="discovery.project.changed", obj=pid)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, pid):
        """Delete a discovery project (what its runs added stays in the model)"""
        return _do(lambda c: dp.delete(c, g.user, pid), write=True, action="discovery.project.deleted", obj=pid)


@blp.route("/discovery-projects/<string:pid>/sources")
class Sources(MethodView):
    """/api/v1/discovery-projects/{pid}/sources: POST add a source {kind, name, location, include, attachments, sign_in}."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data, pid):
        """Add a source to a discovery project"""
        d = {k: v for k, v in (data or {}).items() if k != "secret"}
        return _do(lambda c: dp.add_resource(c, g.user, pid, d), write=True, action="discovery.source.added", obj=pid)


@blp.route("/discovery-projects/<string:pid>/sources/<int:sid>")
class Source(MethodView):
    """/api/v1/discovery-projects/{pid}/sources/{sid}: PUT change a source (reset_position: read everything next time);
    DELETE remove it."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, pid, sid):
        """Change a source"""
        d = {k: v for k, v in (data or {}).items() if k != "secret"}
        return _do(lambda c: dp.update_resource(c, g.user, pid, sid, d), write=True, action="discovery.source.changed", obj=pid)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, pid, sid):
        """Remove a source"""
        return _do(lambda c: dp.remove_resource(c, g.user, pid, sid), write=True, action="discovery.source.removed", obj=pid)


@blp.route("/discovery-runs/<string:rid>")
class Run(MethodView):
    """/api/v1/discovery-runs/{rid}: GET a run's report: found, skipped as NOT FOR AI, may be the same, not found."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, rid):
        """A discovery run's report"""
        return _do(lambda c: dp.report(c, g.user, rid))


@blp.route("/discovery-runs/<string:rid>/may-be-same/<int:fid>")
class MaybeSame(MethodView):
    """/api/v1/discovery-runs/{rid}/may-be-same/{fid}: POST mark a "may be the same as" flag dealt with."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def post(self, rid, fid):
        """Mark a "may be the same as" flag dealt with"""
        return _do(lambda c: dp.resolve_maybe_same(c, g.user, rid, fid), write=True, action="discovery.flag.resolved", obj=rid)


@blp.route("/models/<uuid:model_id>/entities/<uuid:entity_id>/found-in")
class FoundIn(MethodView):
    """/api/v1/models/{model_id}/entities/{entity_id}/found-in: GET where discovery runs found the element."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, model_id, entity_id):
        """Where discovery runs found the element"""
        return _do(lambda c: dp.found_in(c, g.user, str(model_id), str(entity_id)))
