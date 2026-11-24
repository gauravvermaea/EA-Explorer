"""Background jobs (Procrastinate, queue held in PostgreSQL, schema "jobs").

The job runner runs in the same container as the API (see entrypoint.sh):
    procrastinate --app=eax.jobs.app worker
"""

from __future__ import annotations

import logging

from . import coverage_probe

coverage_probe.start()      # the job runners measured too (D810): EAX_COVERAGE=on, before the jobs' code is imported

from procrastinate import App, PsycopgConnector  # noqa: E402
from sqlalchemy import text  # noqa: E402

from . import audit, databases  # noqa: E402
from .config import get_settings  # noqa: E402
from .db import get_engine, get_projects_engine  # noqa: E402

log = logging.getLogger(__name__)

_settings = get_settings()

# kwargs must be a mapping: Procrastinate's LISTEN/NOTIFY listener opens its own connection with
# **kwargs, and fails with "argument after ** must be a mapping, not NoneType" when none are given.
app = App(
    connector=PsycopgConnector(
        conninfo=_settings.libpq_conninfo,
        kwargs={"options": "-c search_path=jobs,public"},
    )
)


@app.task(name="eax.record_heartbeat", queue="default", pass_context=True)
def record_heartbeat(context, note: str, requested_by: str) -> None:
    """Sample job for phase 0: records a heartbeat row and an audit event."""
    job_id = context.job.id if context and context.job else None
    with get_engine().begin() as conn:
        databases.on("operations", conn).execute(
            text(
                "INSERT INTO operations.heartbeat_logs (source, note, requested_by, job_id) "
                "VALUES ('job', :note, :by, :job_id)"
            ),
            {"note": note, "by": requested_by, "job_id": job_id},
        )
        audit.record(
            conn,
            actor=requested_by,
            action="job.completed",
            object_type="job",
            object_id=str(job_id),
            details={"task": "eax.record_heartbeat", "note": note},
            source="job",
        )
    log.info("heartbeat job %s done", job_id)


@app.task(name="eax.copy_model", queue="default", pass_context=True)
def copy_model(context, source: str, target: str, actor: str, roles: list[str], publish: bool = False) -> None:
    """Phase 4: fills a new model from another (metamodel and content), as the person who asked: the
    database checks their rights as it would in the screens. With publish, a Library Admin's promotion is
    locked into the library once copied. A failure is written on the model (copy_state failed)."""
    from . import model_ops, permissions

    token = permissions.current.set(permissions.Principal(actor, tuple(roles or ())))
    try:
        try:
            with get_engine().begin() as conn:
                counts = model_ops.run_copy(conn, source, target, actor, publish=publish)
                audit.record(conn, actor=actor, action="model.copied", object_type="model", object_id=target,
                             details={"source": source, "counts": counts, "published": publish}, source="job")
            log.info("copy %s -> %s done: %s", source, target, counts)
        except Exception as exc:  # recorded on the model so the screens can say why
            with get_engine().begin() as conn:
                model_ops.copy_failed(conn, target, str(exc)[:400])
            log.exception("copy %s -> %s failed", source, target)
            raise
    finally:
        permissions.current.reset(token)


@app.task(name="eax.run_task", queue="tasks")
def run_task(task_id: str, actor: str, roles: list[str]) -> None:
    """Long work in the background (D192): tagging a model, ... (eax/tasks.py). On a queue of its own with slots of its
    own (R5.30): what people ask for (a backup, a delivery, a merge) never waits behind the scheduled housekeeping, which
    held every slot when the full test's backup waited for an hour (15 Nov 2026)."""
    from . import tasks
    tasks.run(task_id, actor, roles)


@app.task(name="eax.admin_sign_in_check", queue="default", pass_context=True)
def admin_sign_in_check(context, username: str) -> None:
    """D215: when an IT or Super Admin signs in, check the installation and notify them of anything that needs attention."""
    from . import admin_check
    nid = admin_check.run(username)
    log.info("sign-in check for %s: %s", username, f"notification {nid}" if nid else "all well")


# Every scheduled job carries a lock of its own name (R5.32, owner, 15 Nov 2026: "if a job already exists like we had
# exactly the 4 jobs of loading industry pack then can we ensure it doesnt load again?"): queueing_lock lets only one
# wait, lock lets only one run; the next waits for it without taking a slot, so the same job never runs twice at once.
@app.periodic(cron="* * * * *")
@app.task(name="eax.record_terminal_ends", queue="default", queueing_lock="record_terminal_ends", lock="record_terminal_ends")
def record_terminal_ends(timestamp: int) -> None:
    """D214: interactive terminal sessions that ended go into the audit trail, every minute."""
    from .api.admin import record_terminal_ends as record
    n = record()
    if n:
        log.info("terminal sessions recorded: %s", n)


@app.periodic(cron="17 3 * * *")
@app.task(name="eax.test_results_cleanup", queue="default", queueing_lock="test_results_cleanup", lock="test_results_cleanup")
def test_results_cleanup(timestamp: int) -> None:
    """R2.43: test runs older than the days set on the Self-test page go, once a day (their data, results, reports,
    logs and videos); 0 keeps them."""
    from .api.admin import _ops_raw
    from .db import get_engine
    from .testing import cleanup
    try:
        days = int((_ops_raw("GET", "/tests", timeout=20) or {}).get("keep_days", cleanup.DEFAULT_KEEP_DAYS))
    except Exception:  # noqa: BLE001 - the operations helper is not there: try tomorrow
        return
    if days <= 0:
        return
    from .testing import store
    with store.engine().connect() as conn:          # the runs are in the tests database (R2.28)
        ids = [r["id"] for r in cleanup.pick(conn, "", days)]
    if ids:
        out = cleanup.delete(get_engine(), ids, "test results kept " + str(days) + " days",
                             lambda folders: _ops_raw("POST", "/tests/results/delete", {"folders": folders}, timeout=120))
        log.info("test results cleanup: %s", cleanup.message(out))


@app.periodic(cron="*/10 * * * *")
@app.task(name="eax.task_files_cleanup", queue="default", queueing_lock="task_files_cleanup", lock="task_files_cleanup")
def task_files_cleanup(timestamp: int) -> None:
    """D273: a background task's file is kept 24 hours; the uploaded files of finished tasks go at once."""
    from . import tasks
    from .db import get_engine
    with get_engine().begin() as conn:
        n = tasks.cleanup(conn)
    if n:
        log.info("removed %s background task files", n)


@app.periodic(cron="* * * * *")
@app.task(name="eax.deliver_webhooks", queue="default", queueing_lock="deliver_webhooks", lock="deliver_webhooks")
def deliver_webhooks(timestamp: int) -> None:
    """Phase 8.1: sends the webhook deliveries that are due (D209), every minute."""
    from . import webhooks
    with get_engine().begin() as conn:
        out = webhooks.deliver_due(conn)
    if any(out.values()):
        log.info("webhooks: %s", out)


@app.periodic(cron="* * * * *")
@app.task(name="eax.personal_flush", queue="default", queueing_lock="personal_flush", lock="personal_flush")
def personal_flush(timestamp: int) -> None:
    """R2.53 (D632): the notifications made while the personal data service could not be reached, sent now it is back."""
    from . import personal
    with get_engine().begin() as conn:
        if not conn.execute(text("SELECT EXISTS (SELECT 1 FROM core.personal_outbox)")).scalar():
            return
        out = personal.flush(conn)
    log.info("personal data service: %s", out)


@app.periodic(cron="* * * * *")
@app.task(name="eax.resource_sample", queue="default", queueing_lock="resource_sample", lock="resource_sample")
def resource_sample(timestamp: int) -> None:
    """R3.5-M8: the resource history: a sample when one is due (every 15 minutes unless set, System Admin > Footprint),
    old samples made hourly and deleted; quiet when the operations helper is not there (tried again next minute)."""
    from . import resources
    from .api.admin import _ops_raw
    try:
        out = resources.tick(get_engine(), _ops_raw)
    except Exception as exc:  # noqa: BLE001 - a missed sample is not an error worth more than a line
        log.info("resource history: no sample (%s)", str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__)
        return
    if not out.startswith("not due"):
        log.info("resource history: %s", out)


@app.periodic(cron="*/5 * * * *")
@app.task(name="eax.library_models_move", queue="default", queueing_lock="library_models_move", lock="library_models_move")
def library_models_move(timestamp: int) -> None:
    """R2.42 (D633): a library model made since (published, uploaded, an industry pack) has its content moved into the
    library schema; nothing to do most of the time."""
    from . import library_models
    done = library_models.move_all(by="system")
    if done:
        log.info("library models moved into their schema: %s", done)


@app.periodic(cron="*/5 * * * *")
@app.task(name="eax.sites_health", queue="default", queueing_lock="sites_health", lock="sites_health")
def sites_health(timestamp: int) -> None:
    """R2.1 (D646): each site's health (green, amber, red) from its public heartbeat; sites deployed since are added."""
    from . import deploys, sites
    with get_engine().begin() as conn:
        added = sites.from_deployments(conn, deploys.history(conn))
        n = sites.check_all(conn)
    log.info("sites: %s checked, %s added from deployments", n, added)


# ---------------------------------------------------------------- site pairings and sync (Release 6.5, D749)
@app.periodic(cron="* * * * *")
@app.task(name="eax.sync_tick", queue="default", queueing_lock="sync_tick", lock="sync_tick")
def sync_tick(timestamp: int) -> None:
    """Every minute, on both sides of every pairing: Site 1 asks Site 2 whether a waiting pairing was accepted and what
    became of its batches, queues what changed for the pairings sending by themselves, and sends what is queued, in
    order; Site 2 commits the batches its pairings commit by themselves, one at a time and in order."""
    from . import pairing as sp
    with get_engine().begin() as core:
        if not core.execute(text("SELECT 1 FROM core.site_pairings WHERE status IN ('waiting', 'accepted') LIMIT 1")).first():
            return
        said = sp.check_peers(core)
        due = sp.due_for_auto(core)
    for ident in due:
        try:
            with get_engine().begin() as core, get_projects_engine().begin() as pc:
                said.append(sp.enqueue(core, pc, ident, "sync", only_changed=True)["say"])
        except Exception as exc:  # noqa: BLE001 - one pairing does not stop the others
            log.warning("sync: queueing %s failed: %s", ident, exc)
    with get_engine().begin() as core:
        said += sp.send_queued(core)
    with get_engine().connect() as core:
        waiting = sp.next_to_commit(core)
    for ident in waiting[:5]:
        _commit(ident, "sync")
    if said:
        log.info("sync: %s", "; ".join(said)[:2000])


def _commit(batch: str, by: str) -> None:
    from . import pairing as sp
    try:
        with get_engine().begin() as core, get_projects_engine().begin() as pc:
            out = sp.commit(core, pc, batch, by)
        log.info("sync: batch %s %s (%s done, %s not)", batch, out["status"], len(out["done"]), len(out["failed"]))
    except Exception as exc:  # noqa: BLE001 - the batch is marked failed, its error kept
        log.warning("sync: committing %s failed: %s", batch, exc)
        with get_engine().begin() as core:
            core.execute(text("UPDATE core.sync_batches SET status = 'failed', error = :e WHERE guid = CAST(:g AS uuid)"),
                         {"e": str(exc)[:2000], "g": batch})


@app.task(name="eax.sync_enqueue", queue="default")
def sync_enqueue(pairing: str, by: str, scope: dict | None = None) -> None:
    """Sync now (a Super Admin on the sending site): the pairing's batches made and queued; the minute job sends them."""
    from . import pairing as sp
    with get_engine().begin() as core, get_projects_engine().begin() as pc:
        log.info("sync: %s", sp.enqueue(core, pc, pairing, by, scope=scope)["say"])


@app.task(name="eax.sync_commit", queue="default")
def sync_commit(batch: str, by: str) -> None:
    """A batch received here committed by a Super Admin (the pairing commits by hand)."""
    _commit(batch, by)


# ---------------------------------------------------------------- backups (phase 8.4, D216, D222)
@app.periodic(cron="* * * * *")
@app.task(name="eax.announce_restores", queue="default", queueing_lock="announce_restores", lock="announce_restores")
def announce_restores(timestamp: int) -> None:
    """Every minute: a restore that ended (or one running that was not announced) is told to everyone (D229); after a
    full restore this is how the restored database hears of it. A model lock left by a restore that stopped is lifted."""
    from . import backups, restore_notice
    with get_engine().begin() as conn:
        n = restore_notice.catch_up(conn, backups.list_records())
        lifted = backups.lift_stale_restore_locks(conn)     # D236: a restore that stopped leaves no lock behind
    if lifted:
        log.info("restore locks lifted: %s", lifted)
    if n:
        log.info("restores announced: %s", n)


@app.periodic(cron="*/10 * * * *")
@app.task(name="eax.discovery_scheduler", queue="default", queueing_lock="discovery_scheduler", lock="discovery_scheduler")
def discovery_scheduler(timestamp: int) -> None:
    """Every 10 minutes: the discovery sources due on their schedules (daily, weekly) run, each as the person who set it
    up; what changed becomes a delivery, previewed here, waiting for review (the Release 3 epic, D670)."""
    from . import discovery as dc
    for r in dc.run_due(get_engine()):
        log.info("discovery %s: %s", r["source"], r.get("message") or r.get("error"))


@app.periodic(cron="* * * * *")
@app.task(name="eax.backup_scheduler", queue="default", queueing_lock="backup_scheduler", lock="backup_scheduler")
def backup_scheduler(timestamp: int) -> None:
    """Every minute: the backups due on their schedules (operations.backup_schedules, set on Administration > Backups) start.
    Infrastructure: in the operations helper; application: here, as the system. The oldest beyond 'keep' go after each."""
    from . import __version__, backup_folder, services
    from . import backup_schedule as bs
    from . import backups as bk
    from . import permissions as perms
    from .api.admin import _ops_raw
    ok, why = backup_folder.ready()
    if not ok:                         # a server or platform with no folder for backups yet (R2.44, D635)
        log.info("scheduled backups: %s", why)
        return
    with get_engine().begin() as conn:
        due = bs.due(conn)
    for s in due:
        status = "started"
        try:
            if not services.enabled("backups"):
                status = "skipped: Backups are switched off"
            elif s["kind"] == "infrastructure":
                _ops_raw("POST", "/backups/backup", {"tag": s["tag"], "by": "system", "kind": "scheduled", "version": __version__,
                                                     "keep": s["keep"]}, timeout=30)
            else:
                with get_engine().begin() as conn:
                    status, _ = bk.application_backup(conn, perms.Principal("system", (perms.SUPER_ADMIN,)), s["tag"], keep_n=s["keep"])
        except Exception as exc:  # noqa: BLE001 - busy, or the helper is down: the sign-in check reports an old backup
            status = f"failed: {exc}"
            log.warning("scheduled %s backup: %s", s["kind"], exc)
        with get_engine().begin() as conn:
            bs.set_status(conn, s["kind"], status)
            audit.record(conn, actor="system", action="backup.scheduled", object_type="backup", object_id=s["kind"],
                         details={"tag": s["tag"], "status": status[:300]})


@app.periodic(cron="* * * * *")
@app.task(name="eax.record_backup_events", queue="default", queueing_lock="record_backup_events", lock="record_backup_events")
def record_backup_events(timestamp: int) -> None:
    """Every minute: backups, restores and clean-ups done by the operations helper go into the audit trail."""
    from .api.admin import _ops_raw
    try:
        events = _ops_raw("GET", "/backups/events", timeout=20).get("events", [])
    except Exception:  # noqa: BLE001 - the helper is down: next minute
        return
    if not events:
        return
    action = {"backup": "backup.scheduled", "restore": "backup.restore.done", "cleanup": "backup.cleanup", "delete": "backup.delete"}
    with get_engine().begin() as conn:
        for e in events:
            act = action.get(e.get("kind"), "backup.scheduled")
            if e.get("kind") == "restore" and e.get("status", "ok") == "ok":     # R6.6.1: checked after every restore
                integrity_after(f"the restore of {e.get('name') or 'a backup'}", str(e.get("by") or "system"))
            if e.get("kind") == "backup" and e.get("reason") != "scheduled":
                act = "backup.infrastructure"
            audit.record(conn, actor=e.get("by") or "system", action=act, object_type="backup",
                         object_id=str(e.get("name") or e.get("kind")), details={k: v for k, v in e.items() if k != "log"})


# ---------------------------------------------------------------- data quality (phase 12, D239)
@app.periodic(cron="* * * * *")
@app.task(name="eax.quality_scheduler", queue="default", queueing_lock="quality_scheduler", lock="quality_scheduler")
def quality_scheduler(timestamp: int) -> None:
    """Every minute: each model whose quality is due on its schedule (every Sunday at 03:00 by default, D244) is measured, the
    measurement kept, and its responsible people told about new problems (stale entities among them)."""
    from datetime import datetime

    from . import backup_schedule as bs
    from . import quality
    with get_engine().begin() as conn:
        due = quality.due(conn, datetime.now(bs.zone(conn)))
    for m in due:
        try:
            with get_engine().begin() as conn:
                mm = {"_id": m["id"], "id": m["g"], "name": m["name"]}
                quality.run(conn, mm, "system", "scheduled")
                quality.tell_new(conn, mm)
        except Exception as exc:  # noqa: BLE001 - one model never stops the others
            log.warning("quality of %s: %s", m["name"], exc)


@app.task(name="eax.quality_entities", queue="default")
def quality_entities(model: str, entities: list[str]) -> None:
    """After a commit (D245, D248): the entities it touched recalculated and their stored rows written, a few seconds
    later; nothing runs inside the commit itself."""
    from . import quality
    with get_engine().begin() as conn:
        n = quality.refresh_entities(conn, model, entities)
    log.info("quality of %s entities of %s recalculated", n, model)


@app.task(name="eax.quality_measure", queue="default")
def quality_measure(request_id: str) -> None:
    """Measure now, Measure all and Recalculate (D245): one model's quality measured and kept in the background; the
    person who asked is told."""
    from . import quality
    quality.run_request(lambda: get_engine().begin(), request_id)


@app.periodic(cron="*/2 * * * *")
@app.task(name="eax.quality_watch", queue="default", queueing_lock="quality_watch", lock="quality_watch")
def quality_watch(timestamp: int) -> None:
    """Every two minutes: models changed lately are checked and the people responsible told about new problems as they
    happen (D239.3); each problem is told once until it is fixed."""
    from datetime import UTC, datetime, timedelta

    from . import quality
    with get_engine().begin() as conn:
        changed = quality.changed_since(conn, datetime.now(UTC) - timedelta(minutes=3))
    for m in changed:
        try:
            with get_engine().begin() as conn:
                n = quality.tell_new(conn, {"_id": m["id"], "id": m["g"], "name": m["name"]})
            if n:
                log.info("quality: %s people told about %s", n, m["name"])
        except Exception as exc:  # noqa: BLE001
            log.warning("quality watch of %s: %s", m["name"], exc)


@app.periodic(cron="0 * * * *")
@app.task(name="eax.quality_digest", queue="default", queueing_lock="quality_digest", lock="quality_digest")
def quality_digest(timestamp: int) -> None:
    """On Mondays at 07:00 in the installation's time zone: each responsible person's weekly data quality digest."""
    from datetime import datetime

    from . import backup_schedule as bs
    from . import quality
    with get_engine().begin() as conn:
        local = datetime.now(bs.zone(conn))
        if local.weekday() != 0 or local.hour != 7:
            return
        n = quality.weekly_digest(conn)
    log.info("quality digest sent to %s people", n)


# ---------------------------------------------------------------- KPI trends (phase 24, D365, D431)
@app.periodic(cron="7 * * * *")
@app.task(name="eax.kpi_monthly", queue="default", queueing_lock="kpi_monthly", lock="kpi_monthly")
def kpi_monthly(timestamp: int) -> None:
    """Every hour: each live model with no KPI snapshot for this month yet gets one, dated the 1st of the month; on the 1st
    that is in the first hour, and a month missed while the server was off is taken as soon as it is back."""
    from datetime import datetime

    from . import backup_schedule as bs
    from . import kpis
    with get_engine().begin() as conn:
        today = datetime.now(bs.zone(conn)).date()
    n = kpis.take_monthly(lambda: get_engine().begin(), today)
    if n:
        log.info("monthly KPIs kept for %s models", n)


# ---------------------------------------------------------------- architecture projects (phase 13, D260)

@app.task(name="eax.project_repository", queue="default", queueing_lock="project_repository")
def project_repository(project_id: int) -> None:
    """A project's repository built in Mayan (cabinets for its folders and items, templates copied)."""
    from . import projects
    note = projects.build_repository(lambda: get_projects_engine().begin(), project_id)
    log.info("project %s repository: %s", project_id, note)


@app.task(name="eax.template_library_load", queue="default", queueing_lock="template_library_load")
def template_library_load(library_id: int) -> None:
    """An uploaded template library's files stored in Mayan (D264)."""
    from . import projects
    note = projects.load_library_upload(lambda: get_projects_engine().begin(), library_id)
    log.info("template library %s: %s", library_id, note)


@app.periodic(cron="* * * * *")
@app.task(name="eax.project_repositories", queue="default", queueing_lock="project_repositories", lock="project_repositories")
def project_repositories(timestamp: int) -> None:
    """Every minute: uploaded template libraries still to store, then the repositories still to build (made while
    Documents was starting or off) once Mayan answers; each failure is kept on the project and tried again (up to 30 times)."""
    from . import mayan, projects
    from . import settings as app_settings
    if not app_settings.parts().get("projects", True):     # switched off (D329): its work waits until it is on again
        return
    with get_projects_engine().begin() as conn:
        todo = projects.pending_repositories(conn)
        libraries = projects.pending_library_loads(conn)
        togaf = projects.togaf_files_waiting(conn)
    if not (todo or libraries or togaf) or not mayan.ping():
        return
    if togaf:                        # the TOGAF folder on disk, loaded again after a clean restart (no git, no hand work)
        try:
            log.info("TOGAF templates: %s", projects.auto_load_togaf(lambda: get_projects_engine().begin()))
        except Exception as exc:  # noqa: BLE001 - tried again next minute
            log.warning("TOGAF templates: %s", exc)
    for lid in libraries:            # uploaded template libraries first: projects using them wait for them
        try:
            projects.load_library_upload(lambda: get_projects_engine().begin(), lid)
        except Exception as exc:  # noqa: BLE001 - kept on the library; tried again next minute
            log.warning("template library %s: %s", lid, exc)
    for pid in todo:
        try:
            projects.build_repository(lambda: get_projects_engine().begin(), pid)
        except Exception as exc:  # noqa: BLE001 - kept on the project; tried again next minute
            log.warning("project %s repository: %s", pid, exc)


@app.periodic(cron="*/10 * * * *")
@app.task(name="eax.industry_packs", queue="default", queueing_lock="industry_packs", lock="industry_packs")
def industry_packs(timestamp: int) -> None:
    """Every 10 minutes: when the shipped industry packs are not all in Documents (the start-up step ran before Documents
    answered, some files failed, or a loader was stopped half way), they are loaded, each file on its own (D546, R2.23).

    R5.32 (the full test of 15 Nov 2026: the backup waited an hour because the job runner's four slots were all held by
    this job, started at 17:50, 18:00, 18:20 and 18:30 and never ended): a run that finds another one still going leaves
    at once, before it reads or waits on anything (queueing_lock only stops a second one waiting, not a second one
    running); a run loads for at most ip.RUN_BUDGET seconds and leaves the rest to the next; its database waits are short
    (ip.timeouts)."""
    from . import industry_packs as ip
    if ip.another_running(get_engine()):
        log.info("industry packs: another run is still loading; this one leaves")
        return
    try:
        with get_engine().connect() as conn:
            ip.timeouts(conn)
            state = databases.on("operations", conn).execute(text("SELECT state FROM operations.startup_parts WHERE part = :p"), {"p": ip.PART}).scalar()
            if state in ("up", "skipped") or (state is None and not ip.missing_shipped(conn)):
                return
        log.info("industry packs: %s", ip.load_shipped_each("system:job")["message"])
    except Exception as exc:  # noqa: BLE001 - tried again in 10 minutes
        log.warning("industry packs: %s", exc)


@app.task(name="eax.documents_ocr", queue="default", queueing_lock="documents_ocr", lock="documents_ocr")
def documents_ocr(on: bool) -> None:
    """Documents' OCR switched on (every type, then the documents already there asked to be read, the count starting
    again) or off (every type, then every OCR job, waiting or held for the window, cleared), when it is changed (D903)."""
    from . import documents_ocr as docr
    from . import mayan
    try:
        types = mayan.set_auto_ocr(bool(on))
        with get_engine().begin() as conn:
            if on:
                n = mayan.ocr_existing()
                docr.started(conn, n)
                log.info("documents OCR: on for %s document type(s); %s document(s) asked to be read", types, n)
            else:
                n = docr.clear()
                docr.stopped(conn, n)
                log.info("documents OCR: off for %s document type(s); %s OCR job(s) cleared", types, n)
    except Exception as exc:  # noqa: BLE001 - applied again at the next start
        log.warning("documents OCR: not applied (%s); applied at the next start", exc)


@app.periodic(cron="* * * * *")
@app.task(name="eax.documents_ocr_tick", queue="default", queueing_lock="documents_ocr_tick", lock="documents_ocr_tick")
def documents_ocr_tick(timestamp: int) -> None:
    """Every minute while OCR is on: its window kept (the pages waiting held outside it, put back inside) and how far it
    has got recorded for everyone to see (D903)."""
    from . import documents_ocr as docr
    from . import settings as S
    try:
        with get_engine().begin() as conn:
            values = S.values(conn)
            if values.get("documents_ocr"):
                docr.tick(conn, values)
    except Exception as exc:  # noqa: BLE001 - looked at again in a minute
        log.warning("documents OCR: progress not read (%s)", exc)


# ---------------------------------------------------------------- surveys (phase 38.1, D448)

@app.periodic(cron="7 * * * *")
@app.task(name="eax.surveys", queue="default", queueing_lock="surveys", lock="surveys")
def surveys(timestamp: int) -> None:
    """Every hour: surveys past their closing date close (a maturity assessment keeps its evidence and scores), and
    automatic reminders go to those who have not answered."""
    from . import surveys as sv
    with get_engine().begin() as conn:
        out = sv.housekeeping(conn)
    if out["closed"] or out["reminded"]:
        log.info("surveys: %s closed, %s reminded", out["closed"], out["reminded"])


# ---------------------------------------------------------------- housekeeping (phase 35.1, D371, D444)

@app.periodic(cron="40 2 * * *")
@app.task(name="eax.housekeeping", queue="default", queueing_lock="housekeeping", lock="housekeeping")
def housekeeping(timestamp: int) -> None:
    """Every night: the retention rules applied once a dry run of them is confirmed; until then, a dry run that waits
    for an IT Admin or Super Admin to confirm it (System admin > Operations > Housekeeping)."""
    from . import operations
    with get_engine().begin() as conn:
        out = operations.scheduled(conn)
    if out:
        log.info("housekeeping %s: %s", "dry run" if out["dry_run"] else "run",
                 {k: v["archived"] + v["deleted"] for k, v in out["results"].items()})


# ---------------------------------------------------------------- the logs (R2.30)
@app.periodic(cron="43 2 * * *")
@app.task(name="eax.logs_clean", queue="default", queueing_lock="logs_clean", lock="logs_clean")
def logs_clean(timestamp: int) -> None:
    """Every night: the containers' daily log files, eax's own logs and the log backups older than the days set in
    System Admin > Settings ("Delete logs older than"; 0 keeps them) deleted by the operations helper; in the audit trail."""
    from . import settings as st
    from .api.admin import _ops_raw
    from .db import get_engine
    days = int(st.values().get("logs_keep_days") or 0)
    if days <= 0:
        return
    try:
        out = _ops_raw("POST", "/logs/clean", {"days": days, "by": "nightly"}, timeout=300) or {}
    except Exception:  # noqa: BLE001 - the operations helper is not there: tomorrow
        return
    if out.get("deleted"):
        with get_engine().begin() as conn:
            audit.record(conn, actor="system", action="logs.clean", object_type="logs", object_id="nightly",
                         details={"days": days, "deleted": len(out["deleted"])})


# ---------------------------------------------------------------- the typed report views (D139)
@app.periodic(cron="*/10 * * * *")
@app.task(name="eax.reports_refresh", queue="default", queueing_lock="reports_refresh", lock="reports_refresh")
def reports_refresh(timestamp: int) -> None:
    """Every 10 minutes: the typed report views brought in line with every metamodel, for a change that saved without
    them because they were busy (reports.refresh_typed_views waits only seconds). Nothing changes when they are."""
    from . import reports
    with get_engine().begin() as conn:
        n = reports.refresh_typed_views(conn, wait="60s")
    if n:
        log.info("report views: %s", "busy, next time" if n < 0 else f"{n} brought up to date")


# ---------------------------------------------------------------- updates (phase 36, D417, D515)

@app.periodic(cron="*/5 * * * *")
@app.task(name="eax.update_watch", queue="default", queueing_lock="update_watch", lock="update_watch")
def update_watch(timestamp: int) -> None:
    """Every 5 minutes: the operations helper's record of updates copied into the database, and the Super Admins and
    IT Admins told once when an update fails, finishes or is rolled back. Once a day (at 06:15): whether the installed
    version is still supported (the Prod channel's releases, when a repository link is set)."""
    from . import updates as up
    from .api.admin import _ops_raw
    try:
        st = _ops_raw("GET", "/updates", timeout=15)
    except Exception:  # noqa: BLE001 - the helper is down or being rebuilt: next time
        return
    with get_engine().begin() as conn:
        up.sync(conn, st)
        told = up.tell(conn)
    if told:
        log.info("updates: %s notification(s)", told)
    from datetime import datetime
    t = datetime.now()
    if not (t.hour == 6 and 15 <= t.minute < 20) or not (st.get("settings") or {}).get("git_url"):
        return
    try:
        got = _ops_raw("GET", "/updates/versions?channel=prod", timeout=200)
    except Exception:  # noqa: BLE001
        return
    releases = [v["version"] for v in got.get("versions") or []] + [(st.get("installed") or {}).get("version") or ""]
    with get_engine().begin() as conn:
        up.tell_support(conn, (st.get("installed") or {}).get("version") or "", [r for r in releases if r])



@app.periodic(cron="23 * * * *")
@app.task(name="eax.governance", queue="default", queueing_lock="governance", lock="governance")
def governance(timestamp: int) -> None:
    """Every hour (R5.5.1): dispensations ending are warned of the setting's days before (30) and become Expired on their
    end date, each told once; and the governance report's rows are copied for Reports (rpt.v_governance_decisions)."""
    import logging

    from . import decisions as dec
    from . import projects as pj
    try:
        with pj.connections(write=True) as conn:
            out = dec.run_ending(conn)
            n = dec.refresh_report(conn)
        if out["warned"] or out["ended"]:
            logging.getLogger("eax.governance").info("dispensations: warned %s, ended %s; report %s rows",
                                                     out["warned"], out["ended"], n)
    except Exception as exc:  # noqa: BLE001 - tried again next hour
        logging.getLogger("eax.governance").warning("governance job: %s", exc)


@app.periodic(cron="41 * * * *")
@app.task(name="eax.keycloak_upkeep", queue="default", queueing_lock="keycloak_upkeep", lock="keycloak_upkeep")
def keycloak_upkeep(timestamp: int) -> None:
    """Every hour (R5.3, R5.22): multi-factor sign-in applied to whoever the setting wants (new admins, new people)
    and the Auditor role made when the realm lacks it. Nothing happens when Keycloak's administrator cannot sign in."""
    import logging

    from . import keycloak_upkeep as ku
    from . import settings as st
    try:
        ku.ensure_roles()          # the Auditor, the Architecture Board and the Discovery Admin (R5.22, R5.5.1, R5.5)
        mode = st.values().get("mfa_mode", "off")
        if mode != "off":
            ku.apply_mfa(mode)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("eax.keycloak_upkeep").info("Keycloak upkeep skipped: %s", exc)


@app.periodic(cron="* * * * *")
@app.task(name="eax.alerts_run", queue="watch", queueing_lock="alerts_run", lock="alerts_run")
def alerts_run(timestamp: int) -> None:
    """Every minute (R5.9): every alert check once; states kept, the history written, people told. On a queue of its
    own (watch) with a job slot of its own, so the alerts still run, and say so, when every other slot is stuck (R5.30)."""
    import logging

    from . import alerts
    try:
        with get_engine().begin() as conn:
            alerts.run(conn)
    except Exception:  # noqa: BLE001 - tried again next minute
        logging.getLogger("eax.alerts").exception("the alert checks could not run")


@app.periodic(cron="* * * * *")
@app.task(name="eax.queue_keeper", queue="watch", queueing_lock="queue_keeper", lock="queue_keeper")
def queue_keeper(timestamp: int) -> None:
    """Every minute (R5.6-Q2): each kind of job's level applied to the jobs waiting, and when the queue is too full the
    low-priority recurring jobs taken off it (their next run does the work; each skip counted). On the alerts' queue
    (watch), so it runs when every other slot is busy."""
    import logging

    from . import job_priorities as jp
    try:
        with get_engine().begin() as conn:
            jp.keep(conn)
    except Exception:  # noqa: BLE001 - tried again next minute
        logging.getLogger("eax.jobs").exception("the queue keeper could not run")


@app.periodic(cron="20 3 * * 0")
@app.task(name="eax.security_weekly", queue="default", queueing_lock="security_weekly", lock="security_weekly")
def security_weekly(timestamp: int) -> None:
    """Every Sunday at 03:20 (R5.17 (1)): the security suite, detailed, by itself (the setting security_test_weekly):
    the scans, the attacks and the gate; nothing waits for a person. Not while another self-test runs."""
    import logging

    from . import settings as st
    from .api.admin import _ops_raw
    from .testing import store
    lg = logging.getLogger("eax.security")
    if not st.values().get("security_test_weekly", True):
        return
    with store.engine().begin() as tc:
        busy = tc.execute(text("SELECT id FROM tests.test_runs WHERE state IN ('queued', 'running') "
                               "AND queued_at > now() - interval '3 hours' LIMIT 1")).scalar()
        if busy:
            lg.info("weekly security test: self-test %s is going on: next week", busy)
            return
        run_id = store.create_run(tc, "schedule (weekly security test)", "eax", ["security"], level="detailed")
    body = {"run_id": run_id, "level": "detailed", "suites": ["security"], "by": "schedule (weekly security test)"}
    try:
        _ops_raw("POST", "/tests/build", {"by": "schedule", "then": body}, timeout=60)
    except Exception as exc:  # noqa: BLE001 - closed with the reason
        with store.engine().begin() as tc:
            store.set_state(tc, run_id, state="error", message=f"Could not start: {exc}")
        lg.warning("weekly security test could not start: %s", exc)


@app.periodic(cron="30 2 1 * *")
@app.task(name="eax.optimise_report", queue="default", queueing_lock="optimise_report", lock="optimise_report")
def optimise_report(timestamp: int) -> None:
    """The 1st of every month at 02:30 (R5.1, D697): the platform measured and a report of suggestions kept; the admins
    (and each Model Admin, for their models) told. Nothing is changed: every suggestion waits for a person's yes."""
    import logging

    from . import optimise
    try:
        with get_engine().begin() as conn:
            r = optimise.measure(conn)
            optimise.save(conn, r, "schedule")
            optimise.tell(conn, r)
    except Exception:  # noqa: BLE001
        logging.getLogger("eax.optimise").exception("the optimisation report failed")


@app.periodic(cron="50 0 * * *")
@app.task(name="eax.db_check", queue="default", queueing_lock="db_check", lock="db_check")
def db_check(timestamp: int) -> None:
    """Every day at 00:50 (R5.12): every database checked, the findings kept (and the alert db_maintenance fed)."""
    import logging

    from . import dbmaint
    try:
        out = dbmaint.check()
        with get_engine().begin() as conn:
            dbmaint.record(conn, "check", "schedule", out["findings"])
    except Exception:  # noqa: BLE001
        logging.getLogger("eax.dbmaint").exception("the database check failed")


@app.periodic(cron="20 2 * * 0")
@app.task(name="eax.db_integrity_weekly", queue="default", queueing_lock="db_integrity", lock="db_integrity")
def db_integrity_weekly(timestamp: int) -> None:
    """Every Sunday at 02:20 (R6.6.1, D750): every database's integrity and recent records checked, the safe fixes made
    after a backup, the admins told."""
    _integrity("schedule", "")


@app.task(name="eax.db_integrity_after", queue="default", queueing_lock="db_integrity", lock="db_integrity")
def db_integrity_after(why: str, by: str = "system", fix: bool | None = None) -> None:
    """After a restore (a rebuild from a backup is one), a DR site taking over, or a person asking (R6.6.1): fix None is
    the setting (integrity_fixes), False only checks (Check now), True makes the safe fixes (Fix the safe ones)."""
    _integrity(by, why, fix)


def _integrity(by: str, after: str, fix: bool | None = None) -> None:
    import logging

    from . import dbintegrity, dbmaint
    if dbmaint.busy_reason():
        logging.getLogger("eax.dbintegrity").info("the integrity check waits: %s", dbmaint.busy_reason())
        return
    try:
        with get_engine().begin() as conn:
            dbintegrity.run(conn, by, after, fix=fix)
    except Exception:  # noqa: BLE001
        logging.getLogger("eax.dbintegrity").exception("the integrity check failed")


def integrity_after(why: str, by: str = "system", fix: bool | None = None) -> None:
    """Queues the integrity check (a restore ended, a DR site took over, a person asked); a queued one already waiting
    does."""
    try:
        with app.open():
            db_integrity_after.defer(why=why, by=by, fix=fix)
    except Exception:  # noqa: BLE001 - one already queued, or no job runner: the weekly run does it
        pass


@app.periodic(cron="*/15 * * * *")
@app.task(name="eax.db_tidy", queue="default", queueing_lock="db_tidy", lock="db_tidy")
def db_tidy(timestamp: int) -> None:
    """Every 15 minutes (R5.12): once a night, inside the window and when nothing must not be disturbed, the tables
    and indexes that need it tidied (nothing locked)."""
    import logging
    from datetime import datetime

    from . import backup_schedule as bs
    from . import dbmaint
    try:
        with get_engine().connect() as conn:
            due = dbmaint.tidy_due(conn, datetime.now(bs.zone(conn)))
        if not due:
            return
        why = dbmaint.busy_reason()
        if why:
            logging.getLogger("eax.dbmaint").info("tonight's tidy waits: %s", why)
            return
        found = dbmaint.check()["findings"]
        done = dbmaint.tidy(found)
        with get_engine().begin() as conn:
            dbmaint.record(conn, "tidy", "schedule", found, done)
    except Exception:  # noqa: BLE001
        logging.getLogger("eax.dbmaint").exception("the nightly tidy failed")


@app.periodic(cron="*/5 * * * *")
@app.task(name="eax.db_idle_sessions", queue="default", queueing_lock="db_idle_sessions", lock="db_idle_sessions")
def db_idle_sessions(timestamp: int) -> None:
    """Every 5 minutes (R5.12): sessions idle in a transaction longer than the setting ended, and recorded."""
    import logging

    from . import dbmaint
    try:
        with get_engine().connect() as conn:
            minutes = dbmaint.settings_of(conn)["idle_tx_minutes"]
        ended = dbmaint.end_idle(minutes)
        if ended:
            with get_engine().begin() as conn:
                dbmaint.record(conn, "locks", "schedule", actions=[{"ended_idle": ended, "after_minutes": minutes}])
    except Exception:  # noqa: BLE001
        logging.getLogger("eax.dbmaint").info("idle sessions not looked at", exc_info=True)


@app.periodic(cron="*/15 * * * *")
@app.task(name="eax.servicedesk_overdue", queue="default", queueing_lock="servicedesk_overdue", lock="servicedesk_overdue")
def servicedesk_overdue(timestamp: int) -> None:
    """Every 15 minutes (R5.11): open requests past their target time, told to their team once."""
    import logging

    from . import servicedesk
    try:
        with get_engine().begin() as conn:
            servicedesk.overdue_reminders(conn)
    except Exception:  # noqa: BLE001
        logging.getLogger("eax.servicedesk").info("overdue requests not looked at", exc_info=True)


# every kind of job's level as it ships (R5.6-Q2): the job runner takes the highest first; a level changed on System
# Admin › Jobs is applied by the queue keeper
def _levels() -> None:
    from . import job_priorities as jp
    for _task in app.tasks.values():
        if _task.name.startswith("eax."):
            _task.priority = jp.number(jp.default_level(_task.name))


_levels()


# quiet while the backup and restore test runs (R5.6-B1): every recurring job misses its turn while work/quiet.json is
# there (eax/quiet.py); the jobs a person or the test asks for still run
from .quiet import QUIET_RUNS  # noqa: E402,I001 - the jobs that keep running while quiet (they finish what was asked)


def _quiet_wrap() -> None:
    import functools
    import inspect

    from . import quiet

    def wrap(func, name):
        @functools.wraps(func)
        def run(*a, **kw):
            if quiet.on():
                log.info("%s: skipped, the backup and restore test is running (quiet)", name)
                return None
            return func(*a, **kw)
        return run
    for _task in app.tasks.values():
        if _task.name.startswith("eax.") and _task.name not in QUIET_RUNS \
                and "timestamp" in inspect.signature(_task.func).parameters and not inspect.iscoroutinefunction(_task.func):
            _task.func = wrap(_task.func, _task.name)


_quiet_wrap()
