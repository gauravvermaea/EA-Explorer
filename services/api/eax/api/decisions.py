"""The organisation's Governance Log, links of decision records and dispensations, and an element's linked records
(R5.5.1). A project's records keep their routes under /projects/{project}/governance (api/projects.py)."""

from __future__ import annotations

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit
from .. import decisions as dec
from .. import projects as pj
from .. import repository as repo
from ..auth import require_auth
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("decisions", __name__, url_prefix="/api/v1",
                description="Architecture decision records and dispensations: the organisation's Governance Log, links, an element's records (R5.5.1)")
SECURITY = [{"bearerAuth": []}]


def _run(fn, write: bool = False, action: str | None = None, obj: str = ""):
    try:
        with pj.connections(write) as conn:
            out = fn(conn)
            if action:
                audit.record(pj.core(conn), actor=g.user.username, action=action, object_type="governance", object_id=str(obj))
            return out
    except (repo.NotFound, EditError) as exc:
        abort(getattr(exc, "status", 404) if isinstance(exc, EditError) else 404, message=str(exc))


@blp.route("/governance")
class OrgGovernance(MethodView):
    """/api/v1/governance: GET the organisation's own Governance Log (everyone signed in reads it); POST log an ADR or a
    dispensation there (the Architecture Board or a Super Admin)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The organisation's own Governance Log: its ADRs and dispensations, the kinds and the templates"""
        return _run(lambda c: dec.org_listing(c, g.user))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data):
        """Log an ADR or a dispensation: {kind, title, status, owner, sponsor, phase, record_type, expires_on, fields{}, html}"""
        d = {k: v for k, v in (data or {}).items() if k != "_ai"}
        return _run(lambda c: dec.org_add(c, g.user, d), write=True, action="governance.logged")


@blp.route("/governance/templates")
class GovernanceTemplates(MethodView):
    """/api/v1/governance/templates: GET the ADR's and the dispensation's forms: their fields, which are required, the
    record types and the ADM phases."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The ADR's and the dispensation's forms"""
        return dec.templates()


@blp.route("/governance/ending-soon")
class GovernanceEnding(MethodView):
    """/api/v1/governance/ending-soon: GET the accepted dispensations ending within the setting's days (30) that you may
    read, nearest first."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The accepted dispensations ending soon that you may read"""
        return _run(lambda c: {"dispensations": dec.ending_soon(c, g.user), "days": dec._warn_days()})


@blp.route("/governance/report")
class GovernanceReport(MethodView):
    """/api/v1/governance/report: GET the governance report as you may read it: decisions by status and project, active
    dispensations by expiry date with those ending soon marked; the OData feed is /api/v1/odata/governance/."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The governance report: decisions by status and project, active dispensations by expiry date"""
        return _run(lambda c: dec.summary(dec.report_rows(c, g.user)))


@blp.route("/governance/<string:rid>")
class OrgGovernanceRecord(MethodView):
    """/api/v1/governance/{rid}: PUT change a record of the organisation's Governance Log (the Architecture Board)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, rid):
        """Change a record of the organisation's Governance Log"""
        d = {k: v for k, v in (data or {}).items() if k != "_ai"}
        return _run(lambda c: dec.org_update(c, g.user, rid, d), write=True, action="governance.changed", obj=rid)


@blp.route("/governance/<string:rid>/decision")
class OrgGovernanceDecision(MethodView):
    """/api/v1/governance/{rid}/decision: POST {action: accept|reject, comment}: the Architecture Board accepts or rejects
    a record of the organisation's Governance Log (a rejection says why)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, rid):
        """The Architecture Board accepts or rejects a record: {action: accept|reject, comment}"""
        d = data or {}
        if d.get("action") not in ("accept", "reject"):
            abort(400, message="action is accept or reject.")
        word = "approved" if d["action"] == "accept" else "rejected"
        return _run(lambda c: dec.org_decide(c, g.user, rid, word, d.get("comment") or ""), write=True,
                    action=f"governance.{d['action']}ed", obj=rid)


@blp.route("/governance/<string:rid>/history")
class OrgGovernanceHistory(MethodView):
    """/api/v1/governance/{rid}/history: GET a record's history in the organisation's Governance Log."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, rid):
        """A record's history"""
        return _run(lambda c: dec.org_history(c, g.user, rid))


@blp.route("/governance/records/<string:rid>/links")
class GovernanceLinks(MethodView):
    """/api/v1/governance/records/{rid}/links: GET a record's links both ways (in a project or the organisation's log);
    POST link it: {kind: element|requirement|principle|standard|record, relation, target, model}."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, rid):
        """A record's links both ways"""
        return _run(lambda c: dec.links(c, g.user, rid))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data, rid):
        """Link a record: {kind: element|requirement|principle|standard|record, relation, target, model}"""
        return _run(lambda c: dec.add_link(c, g.user, rid, data or {}), write=True, action="governance.linked", obj=rid)


@blp.route("/governance/records/<string:rid>/links/<int:link_id>")
class GovernanceLink(MethodView):
    """/api/v1/governance/records/{rid}/links/{link_id}: DELETE remove a link."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, rid, link_id):
        """Remove a link"""
        return _run(lambda c: dec.remove_link(c, g.user, rid, link_id), write=True, action="governance.unlinked", obj=rid)


@blp.route("/models/<uuid:model_id>/entities/<uuid:entity_id>/decisions")
class ElementDecisions(MethodView):
    """/api/v1/models/{model_id}/entities/{entity_id}/decisions: GET the element's linked decisions and dispensations
    you may read: the active ones first, the waivers coming to an end marked."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, model_id, entity_id):
        """The element's linked decisions and dispensations"""
        return _run(lambda c: dec.for_element(c, g.user, str(model_id), str(entity_id)))
