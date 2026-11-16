"""Background jobs: start the sample job and follow its progress."""

from __future__ import annotations

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy import text

from .. import audit
from ..auth import require_auth
from ..db import get_engine
from .models import Free, FreeIn
from .schemas import JobOut, JobRequestIn

blp = Blueprint("jobs", __name__, url_prefix="/api/v1/jobs", description="Background jobs")


@blp.route("/heartbeat")
class HeartbeatJob(MethodView):
    """/api/v1/jobs/heartbeat: POST start the sample background job (signed in) The job runner in the api container
    picks it up, writes a heartbeat row and an audit event."""
    @blp.arguments(JobRequestIn)
    @blp.response(202, JobOut)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth()
    def post(self, data):
        """Start the sample background job (signed in)

        The job runner in the api container picks it up, writes a heartbeat row and an
        audit event.
        """
        from ..jobs import app as jobs_app
        from ..jobs import record_heartbeat

        with jobs_app.open():
            job_id = record_heartbeat.defer(note=data["note"], requested_by=g.user.username)
        with get_engine().begin() as conn:
            audit.record(
                conn, actor=g.user.username, action="job.requested", object_type="job",
                object_id=str(job_id), details={"task": "eax.record_heartbeat"},
                request_id=g.request_id,
            )
        return {"job_id": job_id, "status": "todo", "task": "eax.record_heartbeat"}


@blp.route("/<int:job_id>")
class JobStatus(MethodView):
    """/api/v1/jobs/{job_id}: GET status of a job: todo, doing, succeeded, failed or cancelled."""
    @blp.response(200, JobOut)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth()
    def get(self, job_id: int):
        """Status of a job: todo, doing, succeeded, failed or cancelled"""
        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT id, status, task_name FROM jobs.procrastinate_jobs WHERE id = :id"),
                {"id": job_id},
            ).one_or_none()
        if row is None:
            abort(404, message="No such job.")
        return {"job_id": row.id, "status": str(row.status), "task": row.task_name}


# ---------------------------------------------------------------- the job queue on screen (R5.30, System Admin › Jobs)
@blp.route("/queue")
class JobQueue(MethodView):
    """/api/v1/jobs/queue: GET every job waiting or being worked on, the newest finished, in words; how many are stuck,
    the job slots, and what to do (IT Admins, Super Admins; R5.30)."""
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def get(self):
        """Every job waiting or being worked on, the newest finished, in words; how many are stuck and what to do"""
        from .. import jobqueue
        with get_engine().connect() as conn:
            return jobqueue.queue(conn)


@blp.route("/queue/<int:job_id>/<any(cancel, kill, up, down):action>")
class JobQueueAction(MethodView):
    """/api/v1/jobs/queue/{job_id}/{action}: POST cancel (a waiting job off the queue), kill (a job being worked on,
    stopped), up or down (a waiting job moved in the queue). In the audit trail (R5.30)."""
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def post(self, job_id: int, action: str):
        """cancel (a waiting job off the queue), kill (a job being worked on, stopped), up or down (a waiting job moved
        in the queue). In the audit trail"""
        from .. import jobqueue
        try:
            with get_engine().begin() as conn:
                out = (jobqueue.cancel(conn, job_id, g.user.username) if action == "cancel"
                       else jobqueue.kill(conn, job_id, g.user.username) if action == "kill"
                       else jobqueue.move(conn, job_id, g.user.username, action))
                audit.record(conn, actor=g.user.username, action=f"jobs.{action}", object_type="job", object_id=str(job_id),
                             details=out, request_id=g.request_id)
                return out
        except ValueError as exc:
            abort(409, message=str(exc))


@blp.route("/priorities")
class JobPriorities(MethodView):
    """/api/v1/jobs/priorities: GET every kind of job with its level (high, normal or low; as it ships or changed), its
    skips when the queue was too full, and the limits (R5.6-Q2)."""
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def get(self):
        """Every kind of job with its level, its skips and the limits"""
        from .. import job_priorities as jp
        from ..jobs import app as jobs_app
        with get_engine().connect() as conn:
            return jp.listing(conn, [t for t in jobs_app.tasks if t.startswith("eax.")])


@blp.route("/priorities/<string:task>")
class JobPriority(MethodView):
    """/api/v1/jobs/priorities/{task}: PUT {level: high|normal|low, or "" for as it ships}: a kind of job's level
    (R5.6-Q2), applied to its waiting jobs by the queue keeper within a minute. In the audit trail."""
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def put(self, data, task):
        """{level}: a kind of job's level"""
        from .. import job_priorities as jp
        from ..jobs import app as jobs_app
        try:
            with get_engine().begin() as conn:
                out = jp.set_level(conn, task, str((data or {}).get("level") or ""), g.user.username,
                                   [t for t in jobs_app.tasks if t.startswith("eax.")])
                audit.record(conn, actor=g.user.username, action="jobs.priority", object_type="job", object_id=task,
                             details=out, request_id=g.request_id)
                return out
        except ValueError as exc:
            abort(400, message=str(exc))


@blp.route("/queue/clear-stuck")
class JobQueueClear(MethodView):
    """/api/v1/jobs/queue/clear-stuck: POST {restart}: every stuck job being worked on killed, then (restart true) the
    job runner restarted so their work ends and the waiting jobs start (R5.30; owner: "an alert to kill and clear the job
    queue")."""
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def post(self, data):
        """{restart}: every stuck job being worked on killed, then the job runner restarted"""
        from .. import jobqueue
        with get_engine().begin() as conn:
            out = jobqueue.clear_stuck(conn, g.user.username)
            audit.record(conn, actor=g.user.username, action="jobs.clear_stuck", object_type="job", object_id="stuck",
                         details=out, request_id=g.request_id)
        if (data or {}).get("restart") and out["restart_needed"]:
            from .admin import _ops
            try:
                _ops("POST", "/restart/api", {"by": g.user.username}, timeout=30)
                out["restarting"] = True
            except Exception:  # noqa: BLE001 - the restart takes this API down with it: as asked
                out["restarting"] = True
        return out


@blp.route("/slots")
class JobSlots(MethodView):
    """/api/v1/jobs/slots: GET each API server's job slots (people's work, scheduled jobs, the alerts), the servers
    (wanted, running, the most in auto scaling), the machine's CPU threads and a warning when the slots are more than
    them; PUT {tasks, scheduled}: changed, taken when the API servers restart (R5.33; owner, 15 Nov 2026: "give me
    ability to increase or decrease job slots with warnings if they are more than number of available threads")."""
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def get(self):
        """Each API server's job slots, the servers, the CPU threads and a warning when the slots are more"""
        return _slots()

    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def put(self, data):
        """{tasks, scheduled}: each API server's job slots, taken when the API servers restart. In the audit trail"""
        from .. import settings as st
        data = data or {}
        clean = {}
        try:
            if "tasks" in data:
                clean["jobs_slots_tasks"] = st.check("jobs_slots_tasks", data["tasks"])
            if "scheduled" in data:
                clean["jobs_slots_scheduled"] = st.check("jobs_slots_scheduled", data["scheduled"])
        except st.EditError as exc:
            abort(getattr(exc, "status", 400), message=str(exc))
        with get_engine().begin() as conn:
            st.store(conn, clean)
            audit.record(conn, actor=g.user.username, action="jobs.slots", object_type="job", object_id="slots",
                         details=clean, request_id=g.request_id)
        return {**_slots(), "message": "Saved. The API servers take the new slots when they restart (Apply now)."}


def _slots() -> dict:
    from .. import jobqueue
    from .admin import _ops
    try:
        sc = _ops("GET", "/scaling", timeout=20) or {}
    except Exception:  # noqa: BLE001 - without the helper: what the API knows
        sc = {}
    per = jobqueue.per_server()
    s = sc.get("settings") or {}
    auto = s.get("EAX_SCALE_MODE") == "auto"
    wanted = int(sc.get("servers") or 1)
    most = int(s.get("EAX_SCALE_MAX") or wanted) if auto else wanted
    threads = sc.get("host_cpus")
    return {"per_server": per, "servers": wanted, "running": sc.get("running"), "auto": auto, "most_servers": most,
            "threads": threads, "total_now": (per["tasks"] + per["scheduled"] + per["watch"]) * wanted,
            "total_most": (per["tasks"] + per["scheduled"] + per["watch"]) * most,
            "warning": jobqueue.threads_warning(per, wanted, threads),
            "warning_most": jobqueue.threads_warning(per, most, threads) if auto and most > wanted else ""}


@blp.route("/queue/history")
class JobHistory(MethodView):
    """/api/v1/jobs/queue/history: DELETE ?older_than_days=N (0 or none: all): the finished jobs' history deleted;
    waiting and running jobs are never touched. In the audit trail (R5.34)."""
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def delete(self):
        """The finished jobs' history deleted (all, or ?older_than_days=N); waiting and running jobs never touched"""
        from flask import request

        from .. import jobqueue
        try:
            days = int(request.args.get("older_than_days") or 0)
            with get_engine().begin() as conn:
                out = jobqueue.delete_history(conn, days or None, g.user.username)
                audit.record(conn, actor=g.user.username, action="jobs.delete_history", object_type="job",
                             object_id="history", details=out, request_id=g.request_id)
            return out
        except ValueError as exc:
            abort(400, message=str(exc))


@blp.route("/queue/restart-runner")
class JobRunnerRestart(MethodView):
    """/api/v1/jobs/queue/restart-runner: POST restart the job runner (the API containers, through the operations
    helper): every job being worked on stops, the waiting ones start; the screens are back within a minute (R5.30)."""
    @blp.response(200, Free)
    @blp.doc(security=[{"bearerAuth": []}])
    @require_auth("system.operate")
    def post(self):
        """Restart the job runner (the API containers): every job being worked on stops, the waiting ones start"""
        from .admin import _ops
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="jobs.restart_runner", object_type="job", object_id="runner",
                         details={}, request_id=g.request_id)
        out = _ops("POST", "/restart/api", {"by": g.user.username}, timeout=30)
        return {"message": "The job runner is restarting with the API: the screens come back within a minute.", **(out or {})}
