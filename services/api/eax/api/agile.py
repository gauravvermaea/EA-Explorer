"""Architecture in sprints for an Agile project (Release 12, R12.2, D858, D879): what the Sprints tab shows and does.

GET    /projects/<p>/agile                        the backlog, the sprints (newest first), the usual sprint length
GET    /projects/<p>/agile/offered                the requirements, epics and features in the project's models not in the
                                                  backlog yet (offered: nothing is taken in by itself, D880)
POST   /projects/<p>/agile/backlog                add to the backlog: {entities: [guid]}, {item: id} or {title}
PATCH  /projects/<p>/agile/backlog/<item>         {priority}
DELETE /projects/<p>/agile/backlog/<item>         take a waiting item out
PUT    /projects/<p>/agile/sprint-length          {days}: the project's usual sprint length
POST   /projects/<p>/agile/sprints                plan a sprint: {goal, starts_on, ends_on, phases, steps, deliverables,
                                                  accepter, items}
PATCH  /projects/<p>/agile/sprints/<sprint>       {starts_on, ends_on}: its own dates
POST   /projects/<p>/agile/sprints/<sprint>/review  {decisions: {item: true|false | {accepted, note}}, demo, retrospective,
                                                  note}: the guide's Demo, Outcome, Retrospective and Planning
PUT    /projects/<p>/agile/priority-rule          {rule}: value, risk, slice or easy

Only a project made from the Agile template has sprints; the rules are in eax/agile.py.
"""

from __future__ import annotations

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import agile as ag
from .. import audit
from .. import projects as pj
from .. import repository as repo
from ..auth import require_auth
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("agile", __name__, url_prefix="/api/v1", description="Architecture in sprints for an Agile project (Release 12)")
SECURITY = [{"bearerAuth": []}]


def _run(fn, write: bool = False, action: str | None = None, obj: str | None = None):
    """fn gets the projects' connection; a change is recorded in the audit log."""
    try:
        with pj.connections(write) as conn:
            out = fn(conn)
            if action:
                audit.record(pj.core(conn), actor=g.user.username, action=action, object_type="project", object_id=str(obj or ""))
            return out
    except (repo.NotFound, EditError) as exc:
        abort(getattr(exc, "status", 404) if isinstance(exc, EditError) else 404, message=str(exc))


@blp.route("/projects/<string:project>/agile")
class Agile(MethodView):
    """/api/v1/projects/{project}/agile: GET an Agile project's backlog, sprints and usual sprint length."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project):
        """The backlog, the sprints and the usual sprint length"""
        return _run(lambda c: ag.overview(c, project, g.user))


@blp.route("/projects/<string:project>/agile/offered")
class AgileOffered(MethodView):
    """/api/v1/projects/{project}/agile/offered: GET the requirements, epics and features in the project's models that
    are not in the backlog yet."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project):
        """What the project's models offer the backlog"""
        return _run(lambda c: {"offered": ag.offered(c, project, g.user)})


@blp.route("/projects/<string:project>/agile/backlog")
class AgileBacklog(MethodView):
    """/api/v1/projects/{project}/agile/backlog: POST adds requirements from the models, a deliverable or an item."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, project):
        """Add to the backlog"""
        return _run(lambda c: ag.add_to_backlog(c, project, g.user, data), True, "project.backlog.add", project)


@blp.route("/projects/<string:project>/agile/backlog/<string:item>")
class AgileBacklogItem(MethodView):
    """/api/v1/projects/{project}/agile/backlog/{item}: PATCH its priority; DELETE takes a waiting item out."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def patch(self, data, project, item):
        """A backlog item's priority"""
        return _run(lambda c: ag.prioritise(c, project, g.user, item, data.get("priority", 0)), True, "project.backlog.priority", project)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, project, item):
        """Take a waiting item out of the backlog"""
        return _run(lambda c: ag.remove_from_backlog(c, project, g.user, item), True, "project.backlog.remove", project)


@blp.route("/projects/<string:project>/agile/sprint-length")
class AgileSprintLength(MethodView):
    """/api/v1/projects/{project}/agile/sprint-length: PUT {days}, the project's usual sprint length."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, project):
        """The project's usual sprint length"""
        return _run(lambda c: ag.set_sprint_days(c, project, g.user, data.get("days")), True, "project.sprint.length", project)


@blp.route("/projects/<string:project>/agile/sprints")
class AgileSprints(MethodView):
    """/api/v1/projects/{project}/agile/sprints: POST plans a sprint."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, project):
        """Plan a sprint"""
        return _run(lambda c: ag.plan(c, project, g.user, data), True, "project.sprint.plan", project)


@blp.route("/projects/<string:project>/agile/sprints/<string:sprint>")
class AgileSprint(MethodView):
    """/api/v1/projects/{project}/agile/sprints/{sprint}: PATCH its own dates while it is open."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def patch(self, data, project, sprint):
        """A sprint's own dates"""
        return _run(lambda c: ag.change_dates(c, project, g.user, sprint, data.get("starts_on"), data.get("ends_on")),
                    True, "project.sprint.dates", project)


@blp.route("/projects/<string:project>/agile/sprints/<string:sprint>/review")
class AgileSprintReview(MethodView):
    """/api/v1/projects/{project}/agile/sprints/{sprint}/review: POST the review, each item accepted or not."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, project, sprint):
        """Review a sprint: each item accepted or back to the backlog"""
        return _run(lambda c: ag.review(c, project, g.user, sprint, data.get("decisions") or {}, data.get("note") or "",
                                        data.get("demo") or "", data.get("retrospective") or ""),
                    True, "project.sprint.review", project)


@blp.route("/projects/<string:project>/agile/priority-rule")
class AgilePriorityRule(MethodView):
    """/api/v1/projects/{project}/agile/priority-rule: PUT {rule}: value, risk, slice or easy (G210)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, project):
        """How the project prioritises its backlog"""
        return _run(lambda c: ag.set_priority_rule(c, project, g.user, data.get("rule") or ""), True, "project.backlog.rule", project)
