"""Job priorities (R5.6-Q2; owner, 15 Nov 2026, 22:47: "If the queue is too full then low priorty reoccuring jobs may not
be done like DQ check (automated), notifications etc"; agreed 16 Nov 2026, 15:46).

Every kind of job has a level: high (what people ask for, backups, restores and the alert checks), normal, or low (the
recurring jobs that may miss a turn). The job runner takes the highest first (Procrastinate's own priority: high 100,
normal 0, low -100, set on each task; a level changed on System Admin › Jobs is applied by the queue keeper to the
jobs waiting and to the next ones).

The queue keeper (eax.queue_keeper, every minute, on the alerts' own queue so it runs when the rest is blocked): when
the queue is **too full** (more than jobs_full_waiting waiting, or the oldest waiting longer than jobs_full_minutes), a
waiting low-priority **recurring** job is taken off the queue (cancelled, its event kept) and its next run does the
work: **a missed turn is not caught up**. After jobs_skip_max skips in a row, it is let through. Each skip is counted
(core.job_skips) and shown on the Jobs page and in the jobs_stuck alert's message: nothing is lost silently. A job a
person asked for is never skipped, whatever its level.

The decisions are pure (too_full, decide), tested alone; keep() applies them. Rules here, never in the database (D248).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

LEVELS = {"high": 100, "normal": 0, "low": -100}
# the owner's lists (15:46): data quality checks; digests and reminders; trends and samples; background loads
LOW = {"eax.quality_scheduler", "eax.quality_watch", "eax.quality_entities", "eax.quality_measure",
       "eax.quality_digest", "eax.surveys", "eax.servicedesk_overdue",
       "eax.kpi_monthly", "eax.resource_sample", "eax.reports_refresh",
       "eax.industry_packs", "eax.sites_health", "eax.optimise_report", "eax.discovery_scheduler"}
# what people ask for, and the checks that must run whatever happens
HIGH = {"eax.run_task", "eax.copy_model", "eax.record_heartbeat", "eax.admin_sign_in_check", "eax.project_repository",
        "eax.template_library_load", "eax.alerts_run", "eax.queue_keeper",
        "eax.sync_tick", "eax.sync_enqueue", "eax.sync_commit"}
DEFAULTS = {"jobs_full_waiting": 20, "jobs_full_minutes": 10, "jobs_skip_max": 5}
SKIP_NOTE = "Skipped: the job queue was too full; its next run does the work (System Admin › Jobs, priorities)."


def default_level(task: str) -> str:
    """A kind of job's level as it ships."""
    return "low" if task in LOW else "high" if task in HIGH else "normal"


def number(level: str) -> int:
    """The level as the job runner's priority."""
    return LEVELS[level]


def level_of(task: str, overrides: dict[str, str] | None = None) -> str:
    """A kind of job's level now: changed on the Jobs page, else as it ships."""
    return (overrides or {}).get(task) or default_level(task)


def too_full(waiting: int, oldest_minutes: float, values: dict | None = None) -> bool:
    """Whether the queue is too full: more waiting than the limit, or the oldest waiting longer (pure)."""
    v = {**DEFAULTS, **(values or {})}
    return waiting > int(v["jobs_full_waiting"]) or oldest_minutes > float(v["jobs_full_minutes"])


def decide(waiting: list[dict], now: datetime, overrides: dict[str, str] | None, skips: dict[str, int],
           values: dict | None = None) -> dict[str, Any]:
    """What the keeper does now (pure). waiting: the jobs waiting and due ({id, task_name, scheduled_at, periodic,
    priority}); skips: each kind's skips in a row. Returns {full, skip: [job ids], let_through: [kinds], reprioritise:
    {job id: priority}}."""
    v = {**DEFAULTS, **(values or {})}
    due = [w for w in waiting if w["scheduled_at"] is None or w["scheduled_at"] <= now]
    oldest = max(((now - w["scheduled_at"]).total_seconds() / 60 for w in due if w["scheduled_at"]), default=0.0)
    full = too_full(len(due), oldest, v)
    skip, through = [], []
    if full:
        for w in due:
            if not w.get("periodic") or level_of(w["task_name"], overrides) != "low":
                continue                                       # a job a person asked for is never skipped
            if skips.get(w["task_name"], 0) + skip.count(w["task_name"]) < int(v["jobs_skip_max"]):
                skip.append(w["id"])
            elif w["task_name"] not in through:
                through.append(w["task_name"])                 # skipped too often in a row: it runs this time
    skipped_ids = {i: True for i in skip}
    re = {w["id"]: number(level_of(w["task_name"], overrides)) for w in waiting
          if w["id"] not in skipped_ids and w.get("priority") in LEVELS.values()
          and w["priority"] != number(level_of(w["task_name"], overrides))}   # a job moved by hand keeps its place
    return {"full": full, "oldest_minutes": round(oldest, 1), "due": len(due),
            "skip": skip, "skip_kinds": [w["task_name"] for w in due if w["id"] in skipped_ids],
            "let_through": through, "reprioritise": re}


# ---------------------------------------------------------------- reading and applying
def overrides(conn) -> dict[str, str]:
    """The levels changed on the Jobs page."""
    if not conn.execute(text("SELECT to_regclass('core.job_priorities')")).scalar():
        return {}
    return {r[0]: r[1] for r in conn.execute(text("SELECT task_name, level FROM core.job_priorities"))}


def skips(conn) -> dict[str, dict]:
    """Each kind's skips: in a row, in all, and the last."""
    if not conn.execute(text("SELECT to_regclass('core.job_skips')")).scalar():
        return {}
    return {r["task_name"]: dict(r) for r in conn.execute(text(
        "SELECT task_name, in_row, total, last_at FROM core.job_skips")).mappings()}


def _values() -> dict:
    try:
        from . import settings as st
        return {k: st.values().get(k, d) for k, d in DEFAULTS.items()}
    except Exception:  # noqa: BLE001 - the defaults
        return dict(DEFAULTS)


def keep(conn, now: datetime | None = None, values: dict | None = None) -> dict[str, Any]:
    """The queue keeper's turn: levels applied to the waiting jobs, and when the queue is too full, the low-priority
    recurring jobs that may miss a turn taken off it (each counted)."""
    from . import jobqueue as jq
    now = now or datetime.now(UTC)
    if not conn.execute(text("SELECT to_regclass('jobs.procrastinate_jobs')")).scalar():
        return {"full": False, "skip": [], "let_through": [], "reprioritise": {}}
    conn.execute(text("SET LOCAL search_path TO jobs, public"))
    rows = [dict(r) for r in conn.execute(text("""SELECT id, task_name, scheduled_at, priority, args ? 'timestamp' AS periodic
                                                    FROM jobs.procrastinate_jobs
                                                   WHERE status = 'todo' AND queue_name <> 'selftest-probe'""")).mappings()]
    sk = skips(conn)
    out = decide(rows, now, overrides(conn), {k: v["in_row"] for k, v in sk.items()}, values or _values())
    for jid, pri in out["reprioritise"].items():
        conn.execute(text("UPDATE jobs.procrastinate_jobs SET priority = :p WHERE id = :j AND status = 'todo'"), {"p": pri, "j": jid})
    for jid, task in zip(out["skip"], out["skip_kinds"], strict=True):
        try:
            jq.cancel(conn, jid, "the queue keeper")
        except ValueError:
            continue                                           # it started meanwhile
        conn.execute(text("""INSERT INTO core.job_skips (task_name, in_row, total, last_at) VALUES (:t, 1, 1, :n)
                             ON CONFLICT (task_name) DO UPDATE SET in_row = core.job_skips.in_row + 1,
                                    total = core.job_skips.total + 1, last_at = :n"""), {"t": task, "n": now})
    reset = set(out["let_through"]) | ({w["task_name"] for w in rows} - set(out["skip_kinds"]) if not out["full"] else set())
    if reset:
        conn.execute(text("UPDATE core.job_skips SET in_row = 0 WHERE task_name = ANY(:t) AND in_row > 0"), {"t": sorted(reset)})
    return out


def listing(conn, task_names: list[str]) -> dict[str, Any]:
    """Every kind of job with its level (and as it ships), its skips, and the limits: what the Jobs page shows."""
    from .jobqueue import WORDS
    ov, sk, v = overrides(conn), skips(conn), _values()
    kinds = []
    for t in sorted(task_names):
        s = sk.get(t) or {}
        kinds.append({"task": t, "what": WORDS.get(t, t.removeprefix("eax.").replace("_", " ")), "level": level_of(t, ov),
                      "default": default_level(t), "changed": t in ov, "skipped_in_row": s.get("in_row", 0),
                      "skipped_total": s.get("total", 0), "last_skipped": s["last_at"].isoformat() if s.get("last_at") else None})
    return {"kinds": kinds, "levels": list(LEVELS), "limits": v}


def set_level(conn, task: str, level: str, by: str, known: list[str]) -> dict[str, Any]:
    """Change a kind of job's level ("" or its shipped level: back to as it ships)."""
    if task not in known:
        raise ValueError(f"No kind of job {task}.")
    if level and level not in LEVELS:
        raise ValueError(f"The level is one of {', '.join(LEVELS)}.")
    if not level or level == default_level(task):
        conn.execute(text("DELETE FROM core.job_priorities WHERE task_name = :t"), {"t": task})
    else:
        conn.execute(text("""INSERT INTO core.job_priorities (task_name, level, set_by) VALUES (:t, :l, :b)
                             ON CONFLICT (task_name) DO UPDATE SET level = :l, set_by = :b, set_at = now()"""),
                     {"t": task, "l": level, "b": by})
    return {"task": task, "level": level or default_level(task),
            "message": f"{task}: {level or default_level(task)} priority, applied to its waiting jobs within a minute."}


def skipped_message(conn) -> str:
    """For the jobs_stuck alert's message: what was skipped in the last hour."""
    try:
        rows = conn.execute(text("SELECT task_name, total FROM core.job_skips WHERE last_at > now() - interval '1 hour' "
                                 "ORDER BY last_at DESC LIMIT 5")).all()
    except Exception:  # noqa: BLE001 - before the migration
        return ""
    return ("; low-priority jobs skipped as the queue was too full: " + ", ".join(f"{t} ({n})" for t, n in rows)) if rows else ""
