"""A project's risk register (Release 12, R12.5, D879, D887): the Governance log's Risk records with the risk Assessments
of the project's models they describe, and the risks in the models not logged yet.

GET    /projects/<p>/risk-register                       the register
POST   /projects/<p>/risk-register                       {model, element}: log a risk of a model as a Risk record
POST   /projects/<p>/risk-register/<record>/describes    {model, element}: link a Risk record to the risk it describes

The rules are in eax/risk_register.py.
"""

from __future__ import annotations

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit
from .. import projects as pj
from .. import repository as repo
from .. import risk_register as rr
from ..auth import require_auth
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("risk_register", __name__, url_prefix="/api/v1", description="A project's risk register (Release 12)")
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


@blp.route("/projects/<string:project>/risk-register")
class RiskRegister(MethodView):
    """/api/v1/projects/{project}/risk-register: GET the register; POST logs a risk of a model."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project):
        """The Risk records with the risks they describe, and the risks not logged yet"""
        return _run(lambda c: rr.register(c, project, g.user))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, project):
        """Log a risk of one of the project's models in the Governance log"""
        return _run(lambda c: rr.log(c, project, g.user, data), True, "project.risk.log", project)


@blp.route("/projects/<string:project>/risk-register/<string:record>/describes")
class RiskDescribes(MethodView):
    """/api/v1/projects/{project}/risk-register/{record}/describes: POST links a Risk record to the risk it describes."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data, project, record):
        """Link a Risk record to the risk in a model it describes"""
        return _run(lambda c: rr.describe(c, project, g.user, record, data), True, "project.risk.describe", project)
