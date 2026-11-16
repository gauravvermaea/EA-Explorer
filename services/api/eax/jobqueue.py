"""The job queue, seen and looked after on screen (R5.30; owner, 15 Nov 2026, 21:40: "if a job is stuck for too long I
should see in the dashboard number of jobs stuck and advise to clear them or delete them from queue or add more api
servers"; 21:41: "a jobs view which clearly shows what is in job queue"; "I will not run commands I want a UI").

Background work runs on the job runner (Procrastinate, in each API container, EAX_JOB_CONCURRENCY jobs at a time, 4
by default) from the queue in the database (jobs.procrastinate_jobs, its events in jobs.procrastinate_events). Here:

  queue()     every job waiting or running, the newest finished ones, each with what it is in words (its background
              task's label and who asked, core.tasks), how long it has waited or run, and whether it is stuck
  summary()   the counts, the job slots, and advice in words (restart the job runner, add an API server, clear them)
  cancel()    a waiting job taken off the queue (its background task failed, saying so)
  kill()      a job being worked on, stopped: freed in the screens at once, its work ends when the job runner restarts
  move()      a waiting job moved down (or up) the queue
  delete_history()  the finished jobs' history deleted, all or older than some days (R5.34)

A job is **stuck** when it has waited longer than jobs_waiting_minutes (5) or run longer than jobs_running_minutes
(60; three times that for backups, restores and the self-test, which are long by nature). Every action is audited by
the caller. Nothing in the database but rows (D248).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

LONG_KINDS = ("backup", "restore", "selftest", "self-test", "test")
# what each kind of job does, in words (owner, 21:42: "User friendly description")
WORDS = {
    "eax.run_task": "Work someone asked for", "eax.admin_sign_in_check": "Check the admins can sign in",
    "eax.alerts_run": "Run the alert checks", "eax.announce_restores": "Announce finished restores",
    "eax.backup_scheduler": "Start the scheduled backups", "eax.copy_model": "Copy a model",
    "eax.db_check": "Check the databases", "eax.db_idle_sessions": "Close idle database sessions",
    "eax.db_tidy": "Tidy the databases", "eax.deliver_webhooks": "Send webhook messages",
    "eax.discovery_scheduler": "Start scheduled discovery feeds", "eax.housekeeping": "Housekeeping",
    "eax.industry_packs": "Load the industry packs", "eax.keycloak_upkeep": "Keep sign-in (Keycloak) in step",
    "eax.kpi_monthly": "Monthly KPI report", "eax.library_models_move": "Move library models",
    "eax.logs_clean": "Delete old logs", "eax.optimise_report": "Monthly optimisation report",
    "eax.personal_flush": "Save personal settings", "eax.project_repositories": "Build the project repositories",
    "eax.project_repository": "Build a project's repository", "eax.quality_digest": "Data quality digest",
    "eax.quality_entities": "Measure data quality of entities", "eax.quality_measure": "Measure data quality",
    "eax.quality_scheduler": "Start scheduled data quality runs", "eax.quality_watch": "Watch data quality",
    "eax.record_backup_events": "Record backup events", "eax.record_heartbeat": "Sample job (heartbeat)",
    "eax.record_terminal_ends": "Record closed terminals", "eax.reports_refresh": "Refresh the report views",
    "eax.resource_sample": "Measure memory, CPU and disk", "eax.security_weekly": "Weekly security test",
    "eax.servicedesk_overdue": "Remind about overdue requests", "eax.sites_health": "Check the other sites",
    "eax.surveys": "Send survey reminders", "eax.task_files_cleanup": "Delete old task files",
    "eax.template_library_load": "Load the template library", "eax.test_results_cleanup": "Delete old test results",
    "eax.update_watch": "Look for updates",
}
STATUS_WORDS = {"todo": "Waiting", "doing": "Being worked on", "aborting": "Being stopped", "succeeded": "Done",
                "failed": "Failed", "cancelled": "Cancelled", "aborted": "Stopped"}
FINISHED_SHOWN = 50


def limits(values: dict | None = None) -> tuple[int, int]:
    """(minutes a job may wait, minutes it may run) before it counts as stuck: the settings, else 5 and 60."""
    if values is None:
        try:
            from . import settings as st
            values = st.values()
        except Exception:  # noqa: BLE001 - the defaults
            values = {}
    return int(values.get("jobs_waiting_minutes") or 5), int(values.get("jobs_running_minutes") or 60)


def per_server(values: dict | None = None) -> dict[str, int]:
    """Each API server's job slots (R5.33, owner, 15 Nov 2026: "give me ability to increase or decrease job slots"):
    people's work and the scheduled jobs from the settings (else the config file's EAX_JOB_CONCURRENCY and
    EAX_SCHEDULED_CONCURRENCY, else 4 and 2), and the alert checks' 1."""
    if values is None:
        try:
            from . import settings as st
            values = st.values()
        except Exception:  # noqa: BLE001 - the config file's, else the defaults
            values = {}

    def n(key: str, env: str, default: int) -> int:
        for v in (values.get(key), os.environ.get(env)):
            try:
                if v not in (None, ""):
                    return max(1, int(v))
            except (TypeError, ValueError):
                pass
        return default
    return {"tasks": n("jobs_slots_tasks", "EAX_JOB_CONCURRENCY", 4),
            "scheduled": n("jobs_slots_scheduled", "EAX_SCHEDULED_CONCURRENCY", 2), "watch": 1}


def threads_warning(per: dict[str, int], servers: int, threads: int | None, gunicorn: int = 2) -> str:
    """A warning when the slots asked for (with each server's web workers) are more than the host's CPU threads (pure)."""
    if not threads:
        return ""
    total = (per["tasks"] + per["scheduled"] + per["watch"] + gunicorn) * max(1, servers)
    if total > threads:
        return (f"{total} at once ({per['tasks'] + per['scheduled'] + per['watch']} job slots and {gunicorn} web workers on "
                f"each of {servers} server(s)) is more than the {threads} CPU threads this machine has: jobs will slow each "
                "other down. Fewer slots or more CPUs.")
    return ""


def slots(servers: int | None = None) -> int:
    """How many jobs run at once: each server's slots (people's work, the scheduled jobs, the alert checks) times the
    API servers."""
    p = per_server()
    per = p["tasks"] + p["scheduled"] + p["watch"]
    try:
        n = servers if servers is not None else int(os.environ.get("EAX_API_SERVERS") or 1)
    except ValueError:
        n = 1
    return per * max(1, n)


def _long(row: dict) -> bool:
    what = f"{row.get('task_name') or ''} {row.get('kind') or ''}".lower()
    return any(k in what for k in LONG_KINDS)


def judge(row: dict, now: datetime, wait_min: int, run_min: int) -> dict:
    """A job with its minutes waited or run and whether it is stuck (pure, so it is tested alone).

    Running ("doing", or "aborting": asked to stop and not stopped yet) counts from when it started, against the running
    limit. Waiting counts from when it was asked for, or from the time it was put off to (a job run at a time, a retry):
    one whose time has not come is not waiting yet. A waiting job behind an earlier run of the same job (its lock, which
    keeps two copies from running at once) is not stuck itself: it says which job it waits for, and that one is judged
    (R5.46; owner, 16 Nov 2026: "Stuck: waiting for 38 minutes" on the next run of a job that was still running)."""
    out = dict(row)
    status = row.get("status")
    running = status in ("doing", "aborting")
    sched = row.get("scheduled_at")
    later = bool(status == "todo" and sched and sched > now)
    if running:
        since = row.get("started_at") or row.get("deferred_at")
    else:
        since = max([t for t in (row.get("deferred_at"), sched) if t] or [None]) if status == "todo" else row.get("deferred_at")
    minutes = round((now - since).total_seconds() / 60, 1) if since and not later else None
    limit = run_min * (3 if _long(row) else 1) if running else wait_min
    out["minutes"] = minutes
    out["limit_minutes"] = limit if (running or status == "todo") else None
    out["later"] = later
    behind = row.get("behind")
    out["stuck"] = bool((running or status == "todo") and not later and not behind and minutes is not None and minutes > limit)
    if later:
        out["why"] = f"starts at {sched.astimezone(UTC).strftime('%Y-%m-%d %H:%M')} UTC"
    elif behind and status == "todo":
        out["why"] = f"waiting for the earlier run of this job (job {behind}) to finish"
    elif out["stuck"]:
        out["why"] = (f"running for {int(minutes)} minutes (more than {limit})" if running
                      else f"waiting for {int(minutes)} minutes (more than {limit})")
    else:
        out["why"] = ""
    return out


def advice(waiting: int, running: int, stuck_waiting: int, stuck_running: int, slot_count: int) -> list[dict]:
    """What to do, in words, with the action that does it (pure)."""
    out = []
    if stuck_running:
        out.append({"action": "kill", "text": f"{stuck_running} job(s) have run far longer than they should: they are probably "
                    "hung. Kill them (marked stopped at once), then restart the job runner to end their work."})
    if stuck_running and stuck_running >= slot_count:
        out.append({"action": "restart", "text": f"Every one of the {slot_count} job slots is held by a stuck job, so nothing "
                    "else can start (backups, alerts, deliveries wait). Restart the job runner (the API): the stuck work stops "
                    "and the waiting jobs start."})
    elif stuck_waiting and running < slot_count:
        out.append({"action": "restart", "text": f"{stuck_waiting} job(s) are waiting although {slot_count - running} slot(s) are "
                    "free: the job runner may not be working. Restart it (the API)."})
    if stuck_waiting and running >= slot_count and not stuck_running:
        out.append({"action": "scale", "text": f"Every job slot is busy and {stuck_waiting} job(s) have waited too long: add an "
                    "API server (each adds its own job slots) on System Admin › Scaling."})
    if stuck_waiting:
        out.append({"action": "cancel", "text": "A waiting job that is no longer wanted can be taken off the queue (its "
                    "background task shows as cancelled)."})
    if not out:
        out.append({"action": "", "text": "Nothing is stuck."})
    return out


def queue(conn, now: datetime | None = None, values: dict | None = None) -> dict[str, Any]:
    """Every job waiting or running and the newest finished, with their background tasks in words; the counts, the
    slots and the advice."""
    now = now or datetime.now(UTC)
    wait_min, run_min = limits(values)
    if not conn.execute(text("SELECT to_regclass('jobs.procrastinate_jobs')")).scalar():
        return {"jobs": [], "finished": [], "summary": summary([], [], wait_min, run_min), "limits": [wait_min, run_min]}
    cols = """j.id, j.task_name, j.queue_name, j.priority, j.status::text AS status, j.attempts, j.args, j.lock,
              j.scheduled_at,
              (SELECT min(b.id) FROM jobs.procrastinate_jobs b WHERE j.status = 'todo' AND j.lock IS NOT NULL
                  AND b.lock = j.lock AND b.id < j.id AND b.status IN ('todo', 'doing', 'aborting')) AS behind,
              (SELECT min(e.at) FROM jobs.procrastinate_events e WHERE e.job_id = j.id AND e.type = 'deferred') AS deferred_at,
              (SELECT max(e.at) FROM jobs.procrastinate_events e WHERE e.job_id = j.id AND e.type = 'started') AS started_at,
              (SELECT max(e.at) FROM jobs.procrastinate_events e WHERE e.job_id = j.id
                  AND e.type IN ('succeeded', 'failed', 'cancelled', 'aborted')) AS ended_at,
              t.id AS task_id, t.kind, t.label, t.requested_by, t.status AS task_status"""
    join = "LEFT JOIN core.tasks t ON t.job_id = j.id"
    open_rows = [dict(r) for r in conn.execute(text(f"""SELECT {cols} FROM jobs.procrastinate_jobs j {join}
                                                       WHERE j.status IN ('todo', 'doing', 'aborting')
                                                       ORDER BY (j.status::text = 'todo'), j.priority DESC, j.id""")).mappings()]
    done_rows = [dict(r) for r in conn.execute(text(f"""SELECT {cols} FROM jobs.procrastinate_jobs j {join}
                                                       WHERE j.status NOT IN ('todo', 'doing', 'aborting')
                                                       ORDER BY j.id DESC LIMIT :n"""), {"n": FINISHED_SHOWN}).mappings()]
    jobs = [_shape(judge(r, now, wait_min, run_min)) for r in open_rows]
    finished = [_shape(r) for r in done_rows]
    return {"jobs": jobs, "finished": finished, "summary": summary(jobs, finished, wait_min, run_min),
            "limits": [wait_min, run_min]}


def _shape(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k != "args"}
    for k in ("deferred_at", "started_at", "ended_at", "scheduled_at"):
        if out.get(k):
            out[k] = out[k].isoformat()
    args = r.get("args") or {}
    out["what"] = r.get("label") or WORDS.get(r.get("task_name", ""), r.get("task_name", "").removeprefix("eax.").replace("_", " "))
    out["status_words"] = STATUS_WORDS.get(r.get("status", ""), r.get("status", ""))
    out["who"] = r.get("requested_by") or (args.get("actor") if isinstance(args, dict) else "") or "the schedule"
    out["periodic"] = isinstance(args, dict) and "timestamp" in args
    return out


def summary(jobs: list[dict], finished: list[dict], wait_min: int, run_min: int, slot_count: int | None = None) -> dict:
    """The counts the dashboard shows, the job slots and the advice."""
    slot_count = slot_count or slots()
    waiting = sum(1 for j in jobs if j["status"] == "todo")
    running = sum(1 for j in jobs if j["status"] in ("doing", "aborting"))
    sw = sum(1 for j in jobs if j["status"] == "todo" and j.get("stuck"))
    sr = sum(1 for j in jobs if j["status"] in ("doing", "aborting") and j.get("stuck"))
    failed = sum(1 for j in finished if j["status"] == "failed")
    return {"waiting": waiting, "running": running, "stuck": sw + sr, "stuck_waiting": sw, "stuck_running": sr,
            "failed_recently": failed, "slots": slot_count, "free_slots": max(0, slot_count - running),
            "advice": advice(waiting, running, sw, sr, slot_count)}


def _task_failed(conn, job_id: int, message: str) -> None:
    conn.execute(text("""UPDATE core.tasks SET status = 'failed', message = :m, finished_at = now()
                          WHERE job_id = :j AND status IN ('queued', 'running')"""), {"j": job_id, "m": message[:500]})


def _jobs_path(conn) -> None:
    """The job runner's own triggers name its types without their schema (procrastinate_job_status): a change to a
    job's status needs the jobs schema on the search path, for this transaction only (R5.45: Kill and Cancel answered
    "type procrastinate_job_status does not exist" and changed nothing)."""
    conn.execute(text("SET LOCAL search_path TO jobs, public"))


def cancel(conn, job_id: int, by: str) -> dict:
    """A waiting job taken off the queue; its background task failed, saying who cancelled it."""
    _jobs_path(conn)
    n = conn.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'cancelled' WHERE id = :j AND status = 'todo'"),
                     {"j": int(job_id)}).rowcount
    if not n:
        raise ValueError(f"Job {job_id} is not waiting (it may have started or finished).")
    _task_failed(conn, int(job_id), f"Cancelled on System Admin › Jobs by {by}.")
    return {"job": int(job_id), "status": "cancelled"}


def kill(conn, job_id: int, by: str) -> dict:
    """A job being worked on, killed (owner, 21:42: "abilty to kill").

    A job already running cannot be interrupted from outside, and marking it ended while it still runs would make the
    job runner fail when the job does end (R5.46: the runner refuses to finish a job that is no longer running, and
    stops). So the first Kill asks it to stop ("Being stopped", the runner's own abort request): its work ends when the
    job runner restarts (Restart the job runner, beside it; the restart marks every job it left as stopped, R5.45), or
    by itself if it finishes first. A second Kill on a job already being stopped marks it stopped at once: for a job left
    by a job runner on another server that is gone, whose slot and lock it would otherwise hold for ever."""
    _jobs_path(conn)            # the status change's event is written by the job runner's own trigger
    row = conn.execute(text("SELECT status::text FROM jobs.procrastinate_jobs WHERE id = :j"), {"j": int(job_id)}).scalar()
    if row not in ("doing", "aborting"):
        raise ValueError(f"Job {job_id} is not being worked on (it may have finished).")
    if row == "doing":
        conn.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'aborting' WHERE id = :j"), {"j": int(job_id)})
        return {"job": int(job_id), "status": "aborting", "restart_needed": True,
                "message": "Asked to stop: its work ends when the job runner restarts (Restart the job runner), or when "
                           "it finishes. Kill it again to mark it stopped at once if no job runner has it any more."}
    conn.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'aborted' WHERE id = :j"), {"j": int(job_id)})
    _task_failed(conn, int(job_id), f"Killed on System Admin › Jobs by {by}.")
    return {"job": int(job_id), "status": "aborted", "restart_needed": False,
            "message": "Marked stopped: its slot is free and its next run can start."}


def move(conn, job_id: int, by: str, direction: str) -> dict:
    """A waiting job moved down (or up) the queue (owner, 21:42: "move things down in priority"): the job runner takes
    the highest priority first, then the oldest; down puts it below every other waiting job, up above them."""
    if direction not in ("up", "down"):
        raise ValueError("direction: up or down.")
    _jobs_path(conn)
    row = conn.execute(text("SELECT status::text FROM jobs.procrastinate_jobs WHERE id = :j"), {"j": int(job_id)}).scalar()
    if row != "todo":
        raise ValueError(f"Job {job_id} is not waiting: only a waiting job moves in the queue.")
    lo, hi = conn.execute(text("SELECT coalesce(min(priority), 0), coalesce(max(priority), 0) FROM jobs.procrastinate_jobs "
                               "WHERE status = 'todo' AND id <> :j"), {"j": int(job_id)}).one()
    to = (int(lo) - 1) if direction == "down" else (int(hi) + 1)
    conn.execute(text("UPDATE jobs.procrastinate_jobs SET priority = :p WHERE id = :j"), {"p": to, "j": int(job_id)})
    return {"job": int(job_id), "priority": to}


def clear_stuck(conn, by: str) -> dict:
    """Every stuck job dealt with at once (owner, 21:46: "There need to be an alert to kill and clear the job queue"):
    the stuck ones being worked on killed, the stuck waiting ones left to start (they are only waiting for a slot), and
    whether the job runner must restart for the killed work to end."""
    q = queue(conn)
    killed = []
    for j in q["jobs"]:
        if j.get("stuck") and j["status"] in ("doing", "aborting"):
            kill(conn, j["id"], by)
            killed.append({"id": j["id"], "what": j["what"]})
    return {"killed": killed, "restart_needed": bool(killed)}


def recover(conn, servers: int | None = None) -> dict:
    """Jobs left "being worked on" by a job runner that has stopped (R5.45; owner, 16 Nov 2026: "When repo is built
    and all is up why is this job still there? Killing is not really doing anything"). When the job runner restarts
    (Apply now, Restart the job runner, a clean restart) the jobs it was running end with it, but their rows stayed
    "doing" for ever, and each held its job's lock, so the next run of that job waited for ever behind it. With one API
    server, the only job runner is the one starting now: every job still "doing" belongs to no one, so it is marked
    failed (it already stopped; nothing is killed), saying why, and its next run can start. With several servers a job
    may be running on another one: nothing is touched, and Kill on System Admin > Jobs deals with a left-over one."""
    n = servers if servers is not None else int(os.environ.get("EAX_API_SERVERS") or 1)
    if n > 1:
        return {"recovered": [], "servers": n}
    _jobs_path(conn)
    rows = conn.execute(text("""UPDATE jobs.procrastinate_jobs SET status = 'failed'
                                 WHERE status IN ('doing', 'aborting') RETURNING id, task_name""")).all()
    for job_id, _name in rows:
        _task_failed(conn, int(job_id), "Stopped when the job runner restarted; run it again if it is still needed.")
    return {"recovered": [{"id": int(i), "task": t} for i, t in rows], "servers": n}


FINISHED = ("succeeded", "failed", "cancelled", "aborted")


def delete_history(conn, older_than_days: int | None, by: str) -> dict:
    """The finished jobs' history deleted (R5.34; owner, 15 Nov 2026: "add ability to delete job history"): every job
    that has ended (done, failed, cancelled, stopped), all or those that ended more than a number of days ago, with their
    events. A job waiting or being worked on is never touched. The schedule's record of what it deferred is kept (its
    link to the job emptied), so no scheduled job runs twice."""
    if older_than_days is not None and older_than_days < 0:
        raise ValueError("days: 0 or more.")
    _jobs_path(conn)        # the runner's trigger on deleting a job names its tables without their schema (R5.46)
    where = "j.status::text = ANY(:f)"
    params: dict = {"f": list(FINISHED)}
    if older_than_days:
        where += """ AND coalesce((SELECT max(e.at) FROM jobs.procrastinate_events e WHERE e.job_id = j.id),
                                  'epoch'::timestamptz) < now() - make_interval(days => :d)"""
        params["d"] = int(older_than_days)
    ids = [r[0] for r in conn.execute(text(f"SELECT j.id FROM jobs.procrastinate_jobs j WHERE {where}"), params)]
    if ids:
        conn.execute(text("UPDATE jobs.procrastinate_periodic_defers SET job_id = NULL WHERE job_id = ANY(:i)"), {"i": ids})
        conn.execute(text("DELETE FROM jobs.procrastinate_events WHERE job_id = ANY(:i)"), {"i": ids})
        conn.execute(text("DELETE FROM jobs.procrastinate_jobs WHERE id = ANY(:i)"), {"i": ids})
    return {"deleted": len(ids), "older_than_days": older_than_days or 0}


def _restart_runner() -> str:
    """The job runner (the API containers) restarted through the operations helper."""
    import json
    import urllib.request
    url = os.environ.get("EAX_OPS_URL", "http://ops:8090") + "/restart/api"
    req = urllib.request.Request(url, method="POST", data=json.dumps({"by": "eax"}).encode(),
                                 headers={"X-Ops-Token": os.environ.get("EAX_OPS_TOKEN", ""), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return str(json.load(r).get("message") or "Restarting the API.")


def _print_queue(q: dict) -> None:
    s = q["summary"]
    print(f"Job queue: {s['running']} being worked on, {s['waiting']} waiting, {s['stuck']} stuck, "
          f"{s['free_slots']} of {s['slots']} slots free.")
    for title, rows in (("Being worked on", [j for j in q["jobs"] if j["status"] != "todo"]),
                        ("Waiting, in the order they will start", [j for j in q["jobs"] if j["status"] == "todo"])):
        print(f"\n{title} ({len(rows)})")
        for j in rows:
            mins = f"{j['minutes']:.0f} min" if j.get("minutes") is not None else ""
            flag = f"  STUCK: {j['why']}" if j.get("stuck") else f"  ({j['why']})" if j.get("why") else ""
            print(f"  {j['id']:>7}  {str(j['what'])[:48]:<48} {str(j['who'])[:20]:<20} {mins:>8}{flag}")
    if s["stuck"]:
        print("\nWhat to do:")
        for a in s["advice"]:
            print(f"  - {a['text']}")


def main(argv: list[str]) -> int:
    """python -m eax.jobqueue (eax jobs, R5.30 to R5.34; as "eax", every action in the audit trail):
  list                          what is being worked on and waiting, stuck ones said, what to do
  history [N]                   the newest N finished jobs (50)
  cancel <id> | kill <id>       a waiting job off the queue | a job being worked on stopped
  up <id> | down <id>           a waiting job moved in the queue
  clear-stuck [--restart]       every stuck job being worked on killed (then the job runner restarted)
  restart                       the job runner (the API containers) restarted
  delete-history [--older-than DAYS]   the finished jobs' history deleted (all, or older than DAYS)
  slots [<people's work> <scheduled>]  each API server's job slots shown, or set (taken at the next restart)"""
    from . import audit
    from .db import get_engine
    cmd = argv[0] if argv else "list"
    try:
        if cmd == "recover":                               # the entrypoint, before the job runner starts (R5.45)
            with get_engine().begin() as conn:
                out = recover(conn)
                if out["recovered"]:
                    audit.record(conn, actor="system", action="jobs.recovered", object_type="job", object_id="runner",
                                 details=out)
            print(f"EA Explorer: {len(out['recovered'])} job(s) left running by the last job runner marked stopped"
                  + (": " + ", ".join(f"{r['id']} {r['task']}" for r in out["recovered"]) if out["recovered"] else ""))
            return 0
        if cmd == "slots" and len(argv) == 1 and not os.environ.get("EAX_JOBS_CLI"):
            p = per_server()                                # the entrypoint's question: "<tasks> <scheduled>"
            print(f"{p['tasks']} {p['scheduled']}")
            return 0
        if cmd == "slots":
            from . import settings as st
            if len(argv) == 3:
                clean = {"jobs_slots_tasks": st.check("jobs_slots_tasks", argv[1]),
                         "jobs_slots_scheduled": st.check("jobs_slots_scheduled", argv[2])}
                with get_engine().begin() as conn:
                    st.store(conn, clean)
                    audit.record(conn, actor="eax", action="jobs.slots", object_type="job", object_id="slots", details=clean)
                print("Saved: taken when the API servers restart (eax jobs restart).")
            p = per_server()
            print(f"Each API server: {p['tasks']} for people's work, {p['scheduled']} for scheduled jobs, 1 for the alerts.")
            return 0
        with get_engine().begin() as conn:
            if cmd == "list":
                _print_queue(queue(conn))
                return 0
            if cmd == "history":
                rows = queue(conn)["finished"][: int(argv[1]) if len(argv) > 1 else FINISHED_SHOWN]
                for j in rows:
                    print(f"  {j['id']:>7}  {str(j['what'])[:48]:<48} {str(j['who'])[:20]:<20} {j['status_words']:<10} "
                          f"{str(j.get('ended_at') or '')[:16]}")
                print(f"{len(rows)} finished job(s).")
                return 0
            if cmd in ("cancel", "kill", "up", "down") and len(argv) > 1:
                out = (cancel(conn, int(argv[1]), "eax") if cmd == "cancel" else kill(conn, int(argv[1]), "eax")
                       if cmd == "kill" else move(conn, int(argv[1]), "eax", cmd))
                audit.record(conn, actor="eax", action=f"jobs.{cmd}", object_type="job", object_id=argv[1], details=out)
                print(f"Job {argv[1]}: " + (out.get("message") or "done.") if cmd == "kill" else f"Job {argv[1]}: {cmd} done.")
                return 0
            if cmd == "clear-stuck":
                out = clear_stuck(conn, "eax")
                audit.record(conn, actor="eax", action="jobs.clear_stuck", object_type="job", object_id="stuck", details=out)
                print(f"{len(out['killed'])} stuck job(s) killed: " + ", ".join(f"{k['id']} {k['what']}" for k in out["killed"]))
            elif cmd == "restart":
                audit.record(conn, actor="eax", action="jobs.restart_runner", object_type="job", object_id="runner", details={})
            elif cmd == "delete-history":
                days = int(argv[argv.index("--older-than") + 1]) if "--older-than" in argv else None
                out = delete_history(conn, days, "eax")
                audit.record(conn, actor="eax", action="jobs.delete_history", object_type="job", object_id="history",
                             details=out)
                print(f"{out['deleted']} finished job(s) deleted from the history.")
                return 0
            else:
                print(main.__doc__)
                return 2
        if cmd == "restart" or (cmd == "clear-stuck" and "--restart" in argv):
            print(_restart_runner() + " The screens come back within a minute.")
        return 0
    except Exception as exc:  # noqa: BLE001 - a wrong id, number or setting, said plainly
        print(f"ERROR: {exc}")
        return 1


def measure(conn) -> tuple[float | None, str]:
    """For the alerts (the check jobs_stuck): how many jobs are stuck, and which."""
    try:
        q = queue(conn)
    except Exception as exc:  # noqa: BLE001 - shown as unknown
        return None, f"the job queue could not be read: {exc}"
    s = q["summary"]
    names = ", ".join(f"{j['what']} ({j['why']})" for j in q["jobs"] if j.get("stuck"))[:400]
    return float(s["stuck"]), (f"{s['stuck']} stuck: {names}. Kill and clear them on System Admin › Jobs "
                               "(Clear the stuck jobs)" if s["stuck"] else
                               f"{s['running']} running, {s['waiting']} waiting, {s['slots']} slots")


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
