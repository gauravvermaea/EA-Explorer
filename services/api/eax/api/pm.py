"""A project's plan (Release 12, R12.4, D879, D884, D889; TOGAF Series Guide: Project Management and the ADM): what the
Project plan tab shows and does.

GET    /projects/<p>/plan                          the settings, the phases' plan, the milestones, RACI and the status reports
PUT    /projects/<p>/plan/settings                 {raci, gates, roadmap_from, roadmap_to, roadmap_marks}
PUT    /projects/<p>/plan/phases/<phase>           {starts_on, ends_on}: the phase's plan (both empty: none)
POST   /projects/<p>/plan/milestones               {name, due_on, phase, note}
PATCH  /projects/<p>/plan/milestones/<milestone>   {name, due_on, phase, note, done}
DELETE /projects/<p>/plan/milestones/<milestone>
PUT    /projects/<p>/plan/raci/<ref>               {people: {username: [R, A, C, I]}}: a phase (its code), a
                                                   deliverable (its item's id) or a step (its id), as the project records RACI
POST   /projects/<p>/plan/status                   {rag, summary, next_steps}

The rules are in eax/pm.py.
"""

from __future__ import annotations

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit, pm
from .. import projects as pj
from .. import repository as repo
from ..auth import require_auth
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("project_plan", __name__, url_prefix="/api/v1", description="A project's plan: RACI, gates, milestones, status (Release 12)")
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


@blp.route("/projects/<string:project>/plan")
class Plan(MethodView):
    """/api/v1/projects/{project}/plan: GET the project's plan."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project):
        """The settings, the phases' plan, the milestones, RACI and the status reports"""
        return _run(lambda c: pm.overview(c, project, g.user))


@blp.route("/projects/<string:project>/plan/settings")
class PlanSettings(MethodView):
    """/api/v1/projects/{project}/plan/settings: PUT RACI, the approval gates and the roadmap's period."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, project):
        """How RACI is recorded, the approval gates and the roadmap's period"""
        return _run(lambda c: pm.set_settings(c, project, g.user, data), True, "project.plan.settings", project)


@blp.route("/projects/<string:project>/plan/phases/<string:phase>")
class PlanPhase(MethodView):
    """/api/v1/projects/{project}/plan/phases/{phase}: PUT a phase's planned start and end."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, project, phase):
        """A phase's planned start and end"""
        return _run(lambda c: pm.set_phase_plan(c, project, g.user, phase, data), True, "project.plan.phase", project)


@blp.route("/projects/<string:project>/plan/milestones")
class PlanMilestones(MethodView):
    """/api/v1/projects/{project}/plan/milestones: POST adds a milestone."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, project):
        """Add a milestone"""
        return _run(lambda c: pm.add_milestone(c, project, g.user, data), True, "project.milestone.add", project)


@blp.route("/projects/<string:project>/plan/milestones/<string:milestone>")
class PlanMilestone(MethodView):
    """/api/v1/projects/{project}/plan/milestones/{milestone}: PATCH changes it or marks it done; DELETE removes it."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def patch(self, data, project, milestone):
        """Change a milestone, or mark it done or not done"""
        return _run(lambda c: pm.change_milestone(c, project, g.user, milestone, data), True, "project.milestone.change", project)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, project, milestone):
        """Remove a milestone"""
        return _run(lambda c: pm.delete_milestone(c, project, g.user, milestone), True, "project.milestone.remove", project)


@blp.route("/projects/<string:project>/plan/raci/<string:ref>")
class PlanRaci(MethodView):
    """/api/v1/projects/{project}/plan/raci/{ref}: PUT who is R, A, C and I for a phase, a deliverable or a step."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, project, ref):
        """Who is Responsible, Accountable, Consulted and Informed"""
        return _run(lambda c: pm.set_raci(c, project, g.user, ref, data.get("people") or {}), True, "project.raci", project)


@blp.route("/projects/<string:project>/plan/status")
class PlanStatus(MethodView):
    """/api/v1/projects/{project}/plan/status: POST a status report."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, project):
        """Report the project's status: red, amber or green"""
        return _run(lambda c: pm.add_status(c, project, g.user, data), True, "project.status", project)
