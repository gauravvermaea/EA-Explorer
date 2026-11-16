"""The jobs suite of the self-test (R5.46; owner, 16 Nov 2026, 08:42: "in self test dashboard have another item for job
tests"; 08:41: "ensure if jobs are dead then they dont show up. Please review your code of jobs, add tests for jobs").

Checks of the live job queue (jobs.procrastinate_jobs, System Admin > Jobs, eax/jobqueue.py):

  the job runner takes jobs        a scheduled job finished in the last minutes (the runner is alive)
  the alert checks run             the alert checks (their own queue) finished in the last minutes
  nothing is stuck being worked on  no job runs past its limit, and none is left by a job runner that stopped
  nothing waits too long           no waiting job past its limit (a job behind an earlier run of itself, or put off to
                                   a later time, is not waiting too long)
  every scheduled job has its lock no scheduled job can run twice at once (R5.30, R5.32)
  every job has a name in words    what the Jobs page shows for each kind of job
  Cancel, Move and Kill work       on probe jobs made for the check, in one transaction that is rolled back: nothing
                                   is left and no job runner ever sees them (R5.45: Kill and Cancel did nothing)

Nothing outside the probe jobs is changed; the probes never leave the transaction.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import text

Record = Callable[..., None]
ALIVE_MINUTES = 10                 # a scheduled job finishes every minute or two when the runner is alive
PROBE_TASK = "eax.selftest_probe"  # no such task: a probe is never run, and lives only inside the check's transaction
PROBE_QUEUE = "selftest-probe"     # no worker listens on it


def _timed(record: Record, name: str, fn: Callable[[], tuple[str, str]]) -> None:
    t0 = time.time()
    try:
        outcome, detail = fn()
    except Exception as exc:  # noqa: BLE001 - said, never raised: the next check runs
        outcome, detail = "failed", f"the check could not run: {str(exc).splitlines()[0][:300]}"
    record(name, outcome, detail, int((time.time() - t0) * 1000))


def _finished_lately(conn, task: str | None = None, minutes: int = ALIVE_MINUTES) -> int:
    sql = """SELECT count(*) FROM jobs.procrastinate_events e JOIN jobs.procrastinate_jobs j ON j.id = e.job_id
              WHERE e.type IN ('succeeded', 'failed') AND e.at > now() - make_interval(mins => :m)"""
    params: dict = {"m": minutes}
    if task:
        sql += " AND j.task_name = :t"
        params["t"] = task
    return int(conn.execute(text(sql), params).scalar() or 0)


def scheduled_without_lock() -> list[str]:
    """The scheduled jobs that could run twice at once: no lock, or a lock other than their queueing lock (pure on the
    job runner's registry)."""
    from .. import jobs as J
    periodic = [p.task for p in J.app.periodic_registry.periodic_tasks.values()]
    return sorted({t.name for t in periodic if not t.lock or t.lock != t.queueing_lock})


def unnamed_tasks() -> list[str]:
    """The kinds of job the Jobs page would show by their code name, not in words."""
    from .. import jobs as J
    from ..jobqueue import WORDS
    return sorted(n for n in J.app.tasks if n.startswith("eax.") and n not in WORDS)


def _probe(conn, status: str = "todo") -> int:
    jid = conn.execute(text("""INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args, scheduled_at)
                                VALUES (:q, :t, '{}'::jsonb, now() + interval '1 day') RETURNING id"""),
                       {"q": PROBE_QUEUE, "t": PROBE_TASK}).scalar()
    if status == "doing":
        conn.execute(text("UPDATE jobs.procrastinate_jobs SET status = 'doing' WHERE id = :j"), {"j": jid})
    return int(jid)


def _status(conn, jid: int) -> str:
    return str(conn.execute(text("SELECT status::text FROM jobs.procrastinate_jobs WHERE id = :j"), {"j": jid}).scalar())


def _events(conn, jid: int, kind: str) -> int:
    return int(conn.execute(text("SELECT count(*) FROM jobs.procrastinate_events WHERE job_id = :j AND type = :k"),
                            {"j": jid, "k": kind}).scalar() or 0)


def actions_work(engine) -> tuple[str, str]:
    """Cancel, Move up and down, and Kill, as the Jobs page does them, on probe jobs in a transaction rolled back."""
    from .. import jobqueue as jq
    conn = engine.connect()
    tx = conn.begin()
    try:
        conn.execute(text("SET LOCAL search_path TO jobs, public"))
        waiting = _probe(conn)
        jq.move(conn, waiting, "self-test", "down")
        jq.move(conn, waiting, "self-test", "up")
        jq.cancel(conn, waiting, "self-test")
        running = _probe(conn, "doing")
        jq.kill(conn, running, "self-test")              # asked to stop
        asked = _status(conn, running)
        jq.kill(conn, running, "self-test")              # then marked stopped
        got = (_status(conn, waiting), _events(conn, waiting, "cancelled"),
               f"{asked}, then {_status(conn, running)}", _events(conn, running, "aborted"))
    finally:
        tx.rollback()
        conn.close()
    want = ("cancelled", 1, "aborting, then aborted", 1)
    if got != want:
        return "failed", f"cancelled job: {got[0]} ({got[1]} event(s)); killed job: {got[2]} ({got[3]} event(s)); " \
                         f"expected cancelled, and aborting then aborted; one event each"
    return "passed", ("moved down and up, cancelled, and a running one asked to stop then marked stopped; each with "
                      "one event; all rolled back")


def run(engine, record: Record, now: datetime | None = None) -> dict[str, int]:
    """engine: the repository's (the API's own login, which looks after the queue). One result per check."""
    from .. import jobqueue as jq
    now = now or datetime.now(UTC)
    counts = {"passed": 0, "failed": 0, "warning": 0}

    def rec(name: str, outcome: str, detail: str = "", ms: int = 0) -> None:
        counts[outcome] = counts.get(outcome, 0) + 1
        record(name, outcome, detail, ms)

    with engine.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('jobs.procrastinate_jobs')")).scalar():
            rec("jobs: the job queue is there", "failed", "jobs.procrastinate_jobs is missing")
            return counts
        q = jq.queue(conn, now=now)

        def alive() -> tuple[str, str]:
            n = _finished_lately(conn)
            return ("passed", f"{n} job(s) finished in the last {ALIVE_MINUTES} minutes") if n else \
                ("failed", f"no job finished in the last {ALIVE_MINUTES} minutes: the job runner is not taking jobs "
                           "(restart it on System Admin > Jobs)")
        _timed(rec, "jobs: the job runner takes jobs", alive)

        def alerts() -> tuple[str, str]:
            n = _finished_lately(conn, "eax.alerts_run")
            return ("passed", f"ran {n} time(s) in the last {ALIVE_MINUTES} minutes") if n else \
                ("failed", f"the alert checks have not run in the last {ALIVE_MINUTES} minutes")
        _timed(rec, "jobs: the alert checks run", alerts)

        def running() -> tuple[str, str]:
            bad = [j for j in q["jobs"] if j["status"] in ("doing", "aborting") and j.get("stuck")]
            return ("passed", f"{q['summary']['running']} being worked on, none past its limit") if not bad else \
                ("failed", "; ".join(f"job {j['id']} {j['what']}: {j['why']}" for j in bad)[:900])
        _timed(rec, "jobs: nothing is stuck being worked on", running)

        def waiting() -> tuple[str, str]:
            bad = [j for j in q["jobs"] if j["status"] == "todo" and j.get("stuck")]
            return ("passed", f"{q['summary']['waiting']} waiting, none too long") if not bad else \
                ("failed", "; ".join(f"job {j['id']} {j['what']}: {j['why']}" for j in bad)[:900])
        _timed(rec, "jobs: nothing waits too long", waiting)

    def locks() -> tuple[str, str]:
        bad = scheduled_without_lock()
        return ("passed", "each scheduled job runs one copy at a time") if not bad else \
            ("failed", f"can run twice at once: {', '.join(bad)}")
    _timed(rec, "jobs: every scheduled job has its lock", locks)

    def names() -> tuple[str, str]:
        bad = unnamed_tasks()
        return ("passed", "every kind of job has a name in words") if not bad else \
            ("warning", f"shown by their code name: {', '.join(bad)}")
    _timed(rec, "jobs: every job has a name in words", names)

    _timed(rec, "jobs: Cancel, Move and Kill work", lambda: actions_work(engine))
    return counts
