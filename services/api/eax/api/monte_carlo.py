"""Monte Carlo studies in a project (Release 14.7; D957, D962): what the project's Monte Carlo tab reads and changes.

GET    /projects/<p>/monte-carlo                          the project's studies, each with its latest run in words; the
                                                          kinds, the risk scale, what this person may do
POST   /projects/<p>/monte-carlo                          a new study {name, kind, question?, currency?, unit?}
GET    /projects/<p>/monte-carlo/<s>                      one study in full: inputs, groups, settings, its runs
PUT    /projects/<p>/monte-carlo/<s>                      change {name?, question?, currency?, unit?, runs?, seed?,
                                                          inputs?, groups?, settings?} (each only when given)
DELETE /projects/<p>/monte-carlo/<s>                      the study and its runs
POST   /projects/<p>/monte-carlo/<s>/run                  run it {runs?, seed?}; the run is kept with what it used
GET    /projects/<p>/monte-carlo/<s>/runs                 its runs, newest first
GET    /projects/<p>/monte-carlo/<s>/runs/<n>             one run in full
GET    /projects/<p>/monte-carlo/<s>/runs/<n>/csv         one run's figures as CSV
GET    /monte-carlo/risk-scale                            the organisation's risk scale (or the defaults)
PUT    /monte-carlo/risk-scale                            set it (Super Admins)

The rules and every figure are in eax/monte_carlo_studies.py and eax/monte_carlo.py; a person's change here is saved
at once (the screen is the person's own hand; the AI's changes go through a preview and a yes, D458).
"""

from __future__ import annotations

import csv
import io
from urllib.parse import quote

from flask import Response, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy.exc import IntegrityError

from .. import audit
from .. import monte_carlo_studies as ms
from .. import projects as pj
from .. import repository as repo
from ..auth import require_auth
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("monte_carlo", __name__, url_prefix="/api/v1", description="Monte Carlo studies in a project (Release 14.7)")
SECURITY = [{"bearerAuth": []}]


def _read(fn):
    try:
        with pj.connections(False) as conn:
            return fn(conn)
    except (repo.NotFound, EditError) as exc:
        abort(getattr(exc, "status", 404) if isinstance(exc, EditError) else 404, message=str(exc))


def _write(fn, action: str, project: str = ""):
    try:
        with pj.connections(True) as conn:
            out = fn(conn)
            audit.record(pj.core(conn), actor=g.user.username, action=action, object_type="project", object_id=project,
                         details={k: v for k, v in (out or {}).items() if k in ("message", "changed")},
                         request_id=getattr(g, "request_id", None))
            return out
    except (repo.NotFound, EditError) as exc:
        abort(getattr(exc, "status", 400) if isinstance(exc, EditError) else 404, message=str(exc))
    except IntegrityError:          # two runs (or two studies of one name) kept at the same moment (MC-A08)
        abort(409, message="Someone else saved the same study at the same moment: open it again and repeat.")


@blp.route("/projects/<string:project>/monte-carlo")
class Studies(MethodView):
    """/api/v1/projects/{project}/monte-carlo: GET the project's Monte Carlo studies; POST a new study."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project):
        """The project's Monte Carlo studies, each with its latest run in words"""
        return _read(lambda c: ms.overview(c, project, g.user))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data, project):
        """A new study {name, kind (roadmap | business_case | risk | scenarios), question?, currency?, unit?}"""
        d = data or {}
        return _write(lambda c: ms.create(c, project, g.user, d.get("name", ""), d.get("kind", ""), d.get("question", ""),
                                          d.get("currency", ""), d.get("unit", "")), "monte_carlo.create", project)


@blp.route("/projects/<string:project>/monte-carlo/<string:study>")
class Study(MethodView):
    """/api/v1/projects/{project}/monte-carlo/{study}: GET one study in full; PUT a change; DELETE it and its runs."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project, study):
        """One study in full: its inputs, groups, settings and runs"""
        return _read(lambda c: ms.get_study(c, project, g.user, study))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data, project, study):
        """Change the study's name, question, currency, unit, runs, seed, inputs, groups or settings"""
        return _write(lambda c: ms.update(c, project, g.user, study, data or {}), "monte_carlo.update", project)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, project, study):
        """Delete the study and its runs"""
        return _write(lambda c: ms.delete(c, project, g.user, study), "monte_carlo.delete", project)


@blp.route("/projects/<string:project>/monte-carlo/<string:study>/run")
class StudyRun(MethodView):
    """/api/v1/projects/{project}/monte-carlo/{study}/run: POST run the study; the run is kept."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth()
    def post(self, data, project, study):
        """Run the study {runs?, seed?}: EA Explorer's engine works it out and keeps the run"""
        d = data or {}
        return _write(lambda c: ms.run(c, project, g.user, study, d.get("runs"), d.get("seed")), "monte_carlo.run", project)


@blp.route("/projects/<string:project>/monte-carlo/<string:study>/runs")
class StudyRuns(MethodView):
    """/api/v1/projects/{project}/monte-carlo/{study}/runs: GET the study's runs, newest first, each in words."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project, study):
        """The study's runs, newest first, each in words"""
        return _read(lambda c: {"runs": ms.get_study(c, project, g.user, study)["runs_list"]})


@blp.route("/projects/<string:project>/monte-carlo/<string:study>/runs/<string:number>")
class StudyRunOne(MethodView):
    """/api/v1/projects/{project}/monte-carlo/{study}/runs/{number}: GET one run in full."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self, project, study, number):
        """One run in full: the inputs it used and its results"""
        return _read(lambda c: ms.get_run(c, project, g.user, study, number))


@blp.route("/projects/<string:project>/monte-carlo/<string:study>/runs/<string:number>/csv")
class StudyRunCsv(MethodView):
    """/api/v1/projects/{project}/monte-carlo/{study}/runs/{number}/csv: GET one run's figures as CSV."""
    @blp.doc(security=SECURITY)
    @require_auth()
    def get(self, project, study, number):
        """One run's figures as CSV"""
        rows, name = _read(lambda c: ms.run_rows(c, project, g.user, study, number))
        buf = io.StringIO()
        csv.writer(buf).writerows(rows)
        return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}.csv"})


@blp.route("/monte-carlo/risk-scale")
class RiskScale(MethodView):
    """/api/v1/monte-carlo/risk-scale: GET the organisation's risk scale; PUT it (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """What Likelihood and Impact 1 to 5 mean as a chance in a year and a loss"""
        return _read(lambda c: ms.risk_scale(c))

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data):
        """Set the risk scale {likelihood: {1..5: chance}, impact: {1..5: [low, likely, high]}, currency} (Super Admins)"""
        return _write(lambda c: ms.set_risk_scale(c, g.user, data or {}), "monte_carlo.risk_scale")

