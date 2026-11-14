"""The resource history (Release 3.5, R3.5-M8; owner, 14 Nov 2026, 17:14: "instrument memory CPU disk cache etc every
15 min configurable from admin screen and have it available and can be deleted. We should be able to run this while
testing or working and keeping it").

Every few minutes (the setting resource_every_minutes, 15 unless set; 0 stops it) the job eax.resource_sample asks the
operations helper for one sample (GET /resources: one `docker stats` call; footprint.resources) and adds the database's
own figures (its cache hit rate, size and connections), then keeps it in operations.resource_samples (the operations
schema, D630). A sample says what was happening (a self-test and its level, a backup, a restore, a start-up), so the
figures under test and under use are told apart.

For a while the interval can be shorter (resource_boost_every until resource_boost_until, set on System Admin ›
Footprint for a test) and goes back by itself. Samples older than resource_detail_days (7) become one row an hour
(average and peak, nothing lost but the detail); older than resource_keep_days (90) they are deleted. A Super Admin
deletes a period, everything before a date, or all of it.

  GET    /api/v1/admin/resources?from=&to=   the history over a period, charted on System Admin › Footprint
  GET    /api/v1/admin/resources/csv         the same, one line per container per sample
  POST   /api/v1/admin/resources/sample      a sample now
  PUT    /api/v1/admin/resources/settings    the interval, how long kept, the shorter interval for a while
  DELETE /api/v1/admin/resources             a period, or everything before a date, or all (Super Admin)
  eax footprint --history [days]             the same on the command line (python -m eax.resources history [days])
"""

from __future__ import annotations

import csv
import io
import json
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from . import databases
from . import settings as st

GRACE_SECONDS = 20               # the job runs each minute; a sample due within this is taken now
POINTS = 400                     # at most this many points in a chart; more are merged (as an hour's are)
COUNTERS = ("net_in_mb", "net_out_mb", "disk_read_mb", "disk_write_mb")    # Docker's totals since the container started
TABLE = "operations.resource_samples"


def _time(v) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def interval(values: dict, now: datetime) -> tuple[int, dict | None]:
    """The minutes between samples now, and the shorter interval when one is set and not yet over."""
    base = int(values.get("resource_every_minutes") or 0)
    boost = int(values.get("resource_boost_every") or 0)
    until = _time(values.get("resource_boost_until") or "")
    if boost and until and until > now:
        return boost, {"every": boost, "until": until.isoformat(timespec="seconds")}
    return base, None


def due(last: datetime | None, minutes: int, now: datetime) -> bool:
    return minutes > 0 and (last is None or (now - last).total_seconds() >= minutes * 60 - GRACE_SECONDS)


def settings_of(values: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    every, boost = interval(values, now)
    return {"every_minutes": int(values.get("resource_every_minutes") or 0), "now_every_minutes": every, "boost": boost,
            "detail_days": int(values.get("resource_detail_days") or 7), "keep_days": int(values.get("resource_keep_days") or 90)}


def change_settings(conn, body: dict, now: datetime | None = None) -> dict:
    """{every_minutes, detail_days, keep_days} and the shorter interval for a while {boost_every, boost_hours}
    (boost_every 0 ends it). Checked as the Settings page checks them; applied at once."""
    now = now or datetime.now(UTC)
    clean = {}
    for key, setting in (("every_minutes", "resource_every_minutes"), ("detail_days", "resource_detail_days"),
                         ("keep_days", "resource_keep_days")):
        if key in body:
            clean[setting] = st.check(setting, body[key])
    if "boost_every" in body:
        every = st.check("resource_boost_every", body["boost_every"])
        hours = float(body.get("boost_hours") or 2)
        if not 0 < hours <= 48:
            raise st.EditError("The shorter interval lasts between a few minutes and 48 hours.")
        clean["resource_boost_every"] = every
        clean["resource_boost_until"] = (now + timedelta(hours=hours)).isoformat(timespec="seconds") if every else ""
    was = st.values(conn)
    if int(clean.get("resource_detail_days", was.get("resource_detail_days") or 7)) > int(
            clean.get("resource_keep_days", was.get("resource_keep_days") or 90)):
        raise st.EditError("Every sample can be kept at most as long as the history is kept.")
    st.store(conn, clean)
    return {"changed": sorted(clean), "settings": settings_of(st.values(conn), now)}


# ---------------------------------------------------------------- taking a sample
def database_stats(conn) -> dict:
    """The repository database's own figures: its cache (blocks found in memory and read from disk, since the server
    started), its size, its connections and the server's shared buffers."""
    r = conn.execute(text("""
        SELECT d.blks_hit, d.blks_read, d.numbackends, pg_database_size(d.datname),
               (SELECT count(*) FROM pg_stat_activity),
               (SELECT setting::bigint * current_setting('block_size')::bigint FROM pg_settings WHERE name = 'shared_buffers')
          FROM pg_stat_database d WHERE d.datname = current_database()""")).first()
    if not r:
        return {}
    hit, read = int(r[0] or 0), int(r[1] or 0)
    return {"blocks_hit": hit, "blocks_read": read, "cache_hit_percent": round(hit / (hit + read) * 100, 2) if hit + read else None,
            "size_mb": round(int(r[3] or 0) / 1e6, 1), "connections": int(r[2] or 0), "all_connections": int(r[4] or 0),
            "shared_buffers_mb": round(int(r[5] or 0) / 1e6, 1)}


def record(conn, sample: dict, db: dict) -> None:
    databases.on("operations", conn).execute(text(f"""
        INSERT INTO {TABLE} (at, activity, containers, host, disks, database)
        VALUES (COALESCE(CAST(:at AS timestamptz), now()), :act, CAST(:c AS jsonb), CAST(:h AS jsonb), CAST(:d AS jsonb),
                CAST(:db AS jsonb))"""),
        {"at": sample.get("at"), "act": list(sample.get("activity") or []), "c": json.dumps(sample.get("containers") or []),
         "h": json.dumps(sample.get("host") or {}), "d": json.dumps(sample.get("disks") or []), "db": json.dumps(db or {})})


def take(conn, ops) -> dict:
    """One sample now: the operations helper's (ops("GET", "/resources")) with the database's figures, kept."""
    sample = ops("GET", "/resources", timeout=90)
    try:
        db = database_stats(conn)
    except Exception:  # noqa: BLE001 - the containers are still kept
        db = {}
    record(conn, sample, db)
    return {"at": sample.get("at"), "containers": len(sample.get("containers") or []), "activity": sample.get("activity") or []}


def last_sample(conn) -> datetime | None:
    return databases.on("operations", conn).execute(text(
        f"SELECT max(at) FROM {TABLE} WHERE resolution = 'sample'")).scalar()


def tick(engine, ops, now: datetime | None = None) -> str:
    """The job's minute (eax.resource_sample): old samples tidied; a sample taken when one is due."""
    now = now or datetime.now(UTC)
    with engine.begin() as conn:
        values = st.values(conn)
        done = tidy(conn, values, now)
        minutes, _ = interval(values, now)
        if not due(last_sample(conn), minutes, now):
            return f"not due (every {minutes} minutes){'; ' + done if done else ''}"
        out = take(conn, ops)
    return f"sampled {out['containers']} containers{' during ' + ', '.join(out['activity']) if out['activity'] else ''}" \
           + (f"; {done}" if done else "")


# ---------------------------------------------------------------- merging (an hour, or the points of a long chart)
def _avg(rows: list[dict], key: str, weights: list[int]) -> float | None:
    pairs = [(r.get(key), w) for r, w in zip(rows, weights, strict=True) if isinstance(r.get(key), (int, float))]
    n = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / n, 2) if n else None


def _peak(rows: list[dict], key: str, fallback: str) -> float | None:
    vals = [r.get(key, r.get(fallback)) for r in rows]
    vals = [v for v in vals if isinstance(v, (int, float))]
    return max(vals) if vals else None


def merge(samples: list[dict]) -> dict:
    """Several samples as one (in time order): averages weighted by how many samples each stands for, and peaks kept:
    memory and CPU at their highest, the host's memory at its lowest, the swap at its most. Docker's network and disk
    totals, the volumes, the file systems and the database's counters are the last ones."""
    if not samples:
        return {}
    weights = [int(s.get("samples") or 1) for s in samples]
    names: list[str] = []
    for s in samples:
        for c in s.get("containers") or []:
            if c.get("container") not in names:
                names.append(c.get("container"))
    containers = []
    for name in names:
        rows, w = [], []
        for s, n in zip(samples, weights, strict=True):
            for c in s.get("containers") or []:
                if c.get("container") == name:
                    rows.append(c)
                    w.append(n)
        last = rows[-1]
        row = {"container": name, "memory_mb": _avg(rows, "memory_mb", w), "memory_peak_mb": _peak(rows, "memory_peak_mb", "memory_mb"),
               "cpu_percent": _avg(rows, "cpu_percent", w), "cpu_peak_percent": _peak(rows, "cpu_peak_percent", "cpu_percent")}
        for k in (*COUNTERS, "volumes_mb", "memory_limit_mb", "state"):
            if k in last:
                row[k] = last[k]
        containers.append({k: v for k, v in row.items() if v is not None})
    hosts = [s.get("host") or {} for s in samples]
    host = dict(hosts[-1])
    if any(hosts):
        host["available_mb"] = _avg(hosts, "available_mb", weights)
        least = [h.get("least_available_mb", h.get("available_mb")) for h in hosts]
        least = [v for v in least if isinstance(v, (int, float))]
        if least:
            host["least_available_mb"] = min(least)
        most = _peak(hosts, "most_swap_used_mb", "swap_used_mb")
        if most is not None:
            host["most_swap_used_mb"] = most
    db = dict(samples[-1].get("database") or {})
    conns = _peak([s.get("database") or {} for s in samples], "most_connections", "all_connections")
    if conns is not None:
        db["most_connections"] = conns
    activity = sorted({a for s in samples for a in (s.get("activity") or [])})
    return {"at": samples[0].get("at"), "until": samples[-1].get("until") or samples[-1].get("at"), "samples": sum(weights),
            "activity": activity, "containers": containers, "host": host, "disks": samples[-1].get("disks") or [], "database": db}


def tidy(conn, values: dict, now: datetime) -> str:
    """Samples older than resource_detail_days become one row an hour; older than resource_keep_days are deleted."""
    on = databases.on("operations", conn)
    keep = int(values.get("resource_keep_days") or 90)
    deleted = on.execute(text(f"DELETE FROM {TABLE} WHERE at < :t"), {"t": now - timedelta(days=keep)}).rowcount or 0
    cut = (now - timedelta(days=int(values.get("resource_detail_days") or 7))).replace(minute=0, second=0, microsecond=0)
    rows = [dict(r) for r in on.execute(text(f"""
        SELECT id, at, samples, activity, containers, host, disks, database FROM {TABLE}
         WHERE resolution = 'sample' AND at < :cut ORDER BY at LIMIT 5000"""), {"cut": cut}).mappings()]
    hours: dict[datetime, list[dict]] = {}
    for r in rows:
        hours.setdefault(_time(r["at"]).replace(minute=0, second=0, microsecond=0), []).append(r)
    for hour, group in hours.items():
        m = merge(group)
        on.execute(text(f"""
            INSERT INTO {TABLE} (at, resolution, samples, activity, containers, host, disks, database)
            VALUES (:at, 'hour', :n, :act, CAST(:c AS jsonb), CAST(:h AS jsonb), CAST(:d AS jsonb), CAST(:db AS jsonb))"""),
            {"at": hour, "n": m["samples"], "act": m["activity"], "c": json.dumps(m["containers"]), "h": json.dumps(m["host"]),
             "d": json.dumps(m["disks"]), "db": json.dumps(m["database"])})
        on.execute(text(f"DELETE FROM {TABLE} WHERE id = ANY(:ids)"), {"ids": [r["id"] for r in group]})
    parts = ([f"{len(rows)} samples made {len(hours)} hours"] if hours else []) + ([f"{deleted} older than {keep} days deleted"] if deleted else [])
    return "; ".join(parts)


# ---------------------------------------------------------------- reading
def period(start=None, end=None, days: float | None = None, now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    end_t = _time(end) if end else now
    start_t = _time(start) if start else end_t - timedelta(days=days or 1)
    if not start_t or not end_t or start_t >= end_t:
        raise st.EditError("A period from a time to a later one, please.")
    return start_t, end_t


def rows_between(conn, start: datetime, end: datetime) -> list[dict]:
    out = []
    for r in databases.on("operations", conn).execute(text(f"""
            SELECT at, resolution, samples, activity, containers, host, disks, database FROM {TABLE}
             WHERE at >= :a AND at <= :b ORDER BY at"""), {"a": start, "b": end}).mappings():
        d = dict(r)
        d["at"] = _time(d["at"]).isoformat(timespec="seconds")
        d["activity"] = list(d["activity"] or [])
        out.append(d)
    return out


def _total(s: dict, key: str) -> float:
    return round(sum(c.get(key) or 0 for c in s.get("containers") or []), 1)


def points(rows: list[dict], most: int = POINTS) -> list[dict]:
    """The samples as chart points: at most `most`, neighbours merged when there are more."""
    if len(rows) <= most:
        return rows
    size = -(-len(rows) // most)
    return [merge(rows[i:i + size]) for i in range(0, len(rows), size)]


def history(rows: list[dict], most: int = POINTS) -> dict:
    """The period as charts and a summary: the whole installation's memory (average and peak) and CPU (a share of the
    host), the host's memory left and swap (paging: the swap grew), the database's cache hit rate between samples, the
    file systems; each container's memory and CPU; the peaks and when."""
    out_points, series = [], {}
    prev_db, prev_swap = None, None
    for p in points(rows, most):
        h, db = p.get("host") or {}, p.get("database") or {}
        cpus = h.get("cpus") or 0
        cpu = _total(p, "cpu_percent")
        swap = h.get("most_swap_used_mb", h.get("swap_used_mb"))
        hit = db.get("cache_hit_percent")
        if prev_db and db.get("blocks_hit") is not None and prev_db.get("blocks_hit") is not None:
            dh, dr = db["blocks_hit"] - prev_db["blocks_hit"], db.get("blocks_read", 0) - prev_db.get("blocks_read", 0)
            if dh >= 0 and dr >= 0 and dh + dr > 0:            # a restarted server starts its counters again
                hit = round(dh / (dh + dr) * 100, 2)
        disk = max([d.get("used_percent") or 0 for d in p.get("disks") or []] or [0])
        out_points.append({"at": p["at"], "samples": p.get("samples", 1), "activity": p.get("activity") or [],
                           "memory_mb": _total(p, "memory_mb"),
                           "memory_peak_mb": round(sum(c.get("memory_peak_mb", c.get("memory_mb")) or 0 for c in p.get("containers") or []), 1),
                           "cpu_percent": round(cpu / cpus, 1) if cpus else cpu, "available_mb": h.get("least_available_mb", h.get("available_mb")),
                           "host_mb": h.get("total_mb"), "swap_used_mb": swap,
                           "paged": bool(prev_swap is not None and swap is not None and swap - prev_swap >= 1),
                           "cache_hit_percent": hit, "db_size_mb": db.get("size_mb"), "connections": db.get("all_connections"),
                           "disk_used_percent": disk})
        for c in p.get("containers") or []:
            series.setdefault(c["container"], []).append(
                {"at": p["at"], "memory_mb": c.get("memory_mb"), "memory_peak_mb": c.get("memory_peak_mb", c.get("memory_mb")),
                 "cpu_percent": round((c.get("cpu_percent") or 0) / cpus, 1) if cpus else c.get("cpu_percent")})
        prev_db, prev_swap = db or prev_db, swap if swap is not None else prev_swap
    summary = {}
    if out_points:
        top = max(out_points, key=lambda q: q["memory_peak_mb"])
        busy = max(out_points, key=lambda q: q["cpu_percent"] or 0)
        low = min((q for q in out_points if q["available_mb"] is not None), key=lambda q: q["available_mb"], default=None)
        biggest = sorted(series, key=lambda k: -max((x["memory_peak_mb"] or 0) for x in series[k]))
        summary = {"samples": sum(q["samples"] for q in out_points), "memory_peak_mb": top["memory_peak_mb"], "memory_peak_at": top["at"],
                   "memory_average_mb": round(sum(q["memory_mb"] for q in out_points) / len(out_points), 1),
                   "cpu_peak_percent": busy["cpu_percent"], "cpu_peak_at": busy["at"],
                   "least_available_mb": low["available_mb"] if low else None, "least_available_at": low["at"] if low else None,
                   "paged": any(q["paged"] for q in out_points), "biggest": biggest[:5],
                   "activity": sorted({a for q in out_points for a in q["activity"]})}
    disks = (rows[-1].get("disks") if rows else None) or []
    return {"points": out_points, "containers": series, "summary": summary, "disks": disks}


def csv_text(rows: list[dict]) -> str:
    """One line per container per sample, and one for the whole installation (container "(host)")."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["at", "resolution", "samples", "activity", "container", "memory_mb", "memory_peak_mb", "memory_limit_mb",
                "cpu_percent", "net_in_mb", "net_out_mb", "disk_read_mb", "disk_write_mb", "volumes_mb", "host_total_mb",
                "host_available_mb", "swap_used_mb", "db_cache_hit_percent", "db_size_mb", "db_connections"])
    for r in rows:
        head = [r["at"], r.get("resolution", "sample"), r.get("samples", 1), " ".join(r.get("activity") or [])]
        for c in r.get("containers") or []:
            w.writerow(head + [c.get("container"), c.get("memory_mb"), c.get("memory_peak_mb", c.get("memory_mb")),
                               c.get("memory_limit_mb"), c.get("cpu_percent"), *(c.get(k) for k in COUNTERS), c.get("volumes_mb"),
                               "", "", "", "", "", ""])
        h, db = r.get("host") or {}, r.get("database") or {}
        w.writerow(head + ["(host)", _total(r, "memory_mb"), "", "", _total(r, "cpu_percent"), "", "", "", "", "",
                           h.get("total_mb"), h.get("least_available_mb", h.get("available_mb")),
                           h.get("most_swap_used_mb", h.get("swap_used_mb")), db.get("cache_hit_percent"), db.get("size_mb"),
                           db.get("all_connections")])
    return out.getvalue()


def delete(conn, start=None, end=None) -> int:
    """Deletes a period (start and end), everything before a time (end only), or all of it (neither)."""
    a, b = (_time(start) if start else None), (_time(end) if end else None)
    if (start and not a) or (end and not b) or (a and b and a >= b):
        raise st.EditError("A period from a time to a later one, a time to delete everything before, or nothing for all of it.")
    where, args = [], {}
    if a:
        where.append("at >= :a")
        args["a"] = a
    if b:
        where.append("at < :b")
        args["b"] = b
    return databases.on("operations", conn).execute(
        text(f"DELETE FROM {TABLE}" + (" WHERE " + " AND ".join(where) if where else "")), args).rowcount or 0


# ---------------------------------------------------------------- eax footprint --history [days]
def text_summary(h: dict, days: float, start: datetime, end: datetime) -> str:
    s = h["summary"]
    gb = lambda mb: "-" if mb is None else f"{mb / 1024:.1f} GB"  # noqa: E731
    if not s:
        return (f"No resource history from {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC. It is taken every few minutes "
                "once the setting is on (System Admin > Footprint, or Settings > System).")
    lines = [f"EA Explorer resource history, the last {days:g} days ({start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC), "
             f"{s['samples']} samples",
             f"  Memory, the whole installation: peak {gb(s['memory_peak_mb'])} at {s['memory_peak_at'][:16]}, average {gb(s['memory_average_mb'])}",
             f"  CPU, a share of the host: peak {s['cpu_peak_percent']}% at {s['cpu_peak_at'][:16]}",
             f"  Docker host memory left: least {gb(s['least_available_mb'])}" + (f" at {s['least_available_at'][:16]}" if s["least_available_at"] else ""),
             f"  Paging: {'YES, the swap grew' if s['paged'] else 'none'}",
             f"  While: {', '.join(s['activity']) or 'normal use'}", "", f"  {'Container':<16}{'Average MB':>12}{'Peak MB':>10}{'CPU % peak':>12}"]
    for name in sorted(h["containers"], key=lambda k: -max((x["memory_peak_mb"] or 0) for x in h["containers"][k])):
        pts = h["containers"][name]
        mem = [x["memory_mb"] for x in pts if x["memory_mb"] is not None]
        lines.append(f"  {name:<16}{(sum(mem) / len(mem) if mem else 0):>12.1f}{max((x['memory_peak_mb'] or 0) for x in pts):>10.1f}"
                     f"{max((x['cpu_percent'] or 0) for x in pts):>12.1f}")
    for d in h["disks"]:
        lines.append(f"  Disk {d['label']}: {d['used_gb']} of {d['total_gb']} GB used ({d['used_percent']}%)")
    lines += ["", "Charts, CSV and deleting: System Admin > Footprint."]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "history":
        print("Usage: python -m eax.resources history [days]")
        return 2
    try:
        days = float(argv[1]) if len(argv) > 1 else 1.0
    except ValueError:
        print(f"ERROR: days is a number, not {argv[1]!r}")
        return 2
    from .db import get_engine
    start, end = period(days=days)
    with get_engine().connect() as conn:
        h = history(rows_between(conn, start, end))
    print(text_summary(h, days, start, end))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
