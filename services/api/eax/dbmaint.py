"""Database maintenance, by the application (R5.12, D691: "1 + find what else is needed"): on the web (System Admin >
Database maintenance) and on the command line (eax db ...), for every database on the server.

  check    daily (00:50) and on demand: in plain words, what needs doing, per database:
             swollen tables (dead rows) and indexes; tables autovacuum has not reached; statistics out of date; indexes
             never used, duplicated, or invalid (a build that failed); the transaction age (wraparound: past it
             PostgreSQL stops accepting changes); connections near the limit; long transactions and sessions idle in a
             transaction; the cache hit rate; the size and its growth; sequences near their limit; tables with no
             primary key; replication and its lag where a standby is used; the memory settings against the server
  tidy     nightly within the window (01:00 to 05:00 by default): VACUUM (ANALYZE) of the tables that need it, ANALYZE
           of those with stale statistics, REINDEX CONCURRENTLY of swollen and invalid indexes; never locks a table
  compact  by a person only (it locks the table while it runs): VACUUM FULL of one table, the space it will win said
           first
  clear    the keep-for rules applied now: housekeeping (eax/operations.py: loads, task files, notifications, webhook
           deliveries, discarded changes, usage), the logs past their days (R5.6), old alert history (R5.9)
  locks    who blocks whom and for how long; a query cancelled or a session ended after a preview and a yes; sessions
           idle in a transaction ended by themselves after 30 minutes (the setting db_idle_tx_minutes)

Guards: nothing runs during a backup, a restore or a self-test (it waits for the next window); every run is audited and
kept (core.db_maintenance_runs: what was found, what was done, the space won); the check's findings feed the alert
db_maintenance (R5.9). The maintenance logs in as PostgreSQL's own superuser (EAX_DB_SUPERUSER_PASSWORD), the one
login that may tidy every database; no logic is added to the database (D248).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

SKIP_DATABASES = ("template0", "template1", "postgres")
LEVELS = ("info", "warning", "critical")
WRAP_WARN, WRAP_CRIT = 500_000_000, 1_200_000_000
CONFIRM_SECONDS = 600


class Busy(Exception):
    """Something that must not be disturbed is running (a backup, a restore, a self-test)."""


# ---------------------------------------------------------------- confirmations (any API server may take them)
def _key() -> bytes:
    return hashlib.sha256(b"eax-dbmaint:" + (os.environ.get("EAX_OPS_TOKEN") or os.environ.get("EAX_DB_PASSWORD") or "x").encode()).digest()


def make_token(what: dict, now: float | None = None) -> str:
    """A signed confirmation for a locking action previewed, good for a few minutes."""
    body = base64.urlsafe_b64encode(json.dumps({**what, "until": (now or time.time()) + CONFIRM_SECONDS}).encode()).decode()
    return body + "." + hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()[:32]


def read_token(token: str, now: float | None = None) -> dict:
    """What a confirmation was for, refused when it is not ours or has expired."""
    body, _, sig = str(token).partition(".")
    if not hmac.compare_digest(sig, hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()[:32]):
        raise ValueError("Preview it again: that confirmation is not one of ours.")
    what = json.loads(base64.urlsafe_b64decode(body.encode()))
    if (now or time.time()) > what.pop("until"):
        raise ValueError("Preview it again: the confirmation has expired.")
    return what


# ---------------------------------------------------------------- connections
def _conninfo(dbname: str) -> str:
    from .config import get_settings
    s = get_settings()
    pw = os.environ.get("EAX_DB_SUPERUSER_PASSWORD", "")
    q = lambda v: "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"   # noqa: E731
    return f"host={q(s.db_host)} port={q(s.db_port)} dbname={q(dbname)} user=postgres password={q(pw)} connect_timeout=10"


def connect(dbname: str, autocommit: bool = True):
    """A superuser connection to one database on the server."""
    import psycopg
    return psycopg.connect(_conninfo(dbname), autocommit=autocommit)


def databases() -> list[str]:
    """Every database on the server that takes connections."""
    from .config import get_settings
    with connect(get_settings().db_name) as c:
        return [r[0] for r in c.execute("SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname")
                if r[0] not in SKIP_DATABASES]


def _rows(c, sql: str, *params) -> list[dict]:
    cur = c.execute(sql, params or None)
    names = [d.name for d in cur.description or []]
    return [dict(zip(names, r, strict=False)) for r in cur.fetchall()]


# ---------------------------------------------------------------- the check
def finding(db: str, key: str, level: str, what: str, detail: str, action: str = "", target: str = "") -> dict:
    """One finding of the database check: where, what kind, how bad, in words, and what to do."""
    return {"database": db, "key": key, "level": level, "what": what, "detail": detail, "action": action, "target": target}


def check_database(c, db: str, memory_bytes: int | None = None) -> tuple[list[dict], dict]:
    """One database's findings and its figures."""
    out: list[dict] = []
    size = c.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    for t in _rows(c, """SELECT schemaname || '.' || relname AS t, n_live_tup AS live, n_dead_tup AS dead,
                                n_mod_since_analyze AS changed, last_autovacuum, last_vacuum, last_analyze, last_autoanalyze,
                                pg_total_relation_size(relid) AS bytes
                           FROM pg_stat_user_tables"""):
        live, dead = int(t["live"] or 0), int(t["dead"] or 0)
        if dead > 10_000 and dead > 0.2 * max(live, 1):
            out.append(finding(db, "bloat", "warning", f"{t['t']} is swollen with dead rows",
                               f"{dead:,} dead rows to {live:,} live", "tidy: VACUUM (ANALYZE)", t["t"]))
        if dead > 1_000 and not (t["last_autovacuum"] or t["last_vacuum"]):
            out.append(finding(db, "never_vacuumed", "info", f"{t['t']} has never been tidied", f"{dead:,} dead rows",
                               "tidy: VACUUM (ANALYZE)", t["t"]))
        changed = int(t["changed"] or 0)
        if changed > 1_000 and changed > 0.2 * max(live, 1):
            out.append(finding(db, "stale_stats", "info", f"{t['t']}'s statistics are out of date",
                               f"{changed:,} rows changed since they were last gathered", "tidy: ANALYZE", t["t"]))
    for i in _rows(c, """SELECT s.schemaname || '.' || s.indexrelname AS i, s.schemaname || '.' || s.relname AS t,
                                pg_relation_size(s.indexrelid) AS bytes
                           FROM pg_stat_user_indexes s JOIN pg_index x ON x.indexrelid = s.indexrelid
                          WHERE s.idx_scan = 0 AND NOT x.indisunique AND NOT x.indisprimary
                            AND pg_relation_size(s.indexrelid) > 10 * 1024 * 1024"""):
        out.append(finding(db, "unused_index", "info", f"{i['i']} has never been used",
                           f"{int(i['bytes']) // 1048576} MB on {i['t']}", "a person decides whether to drop it", i["i"]))
    for d in _rows(c, """SELECT indrelid::regclass::text AS t, array_agg(indexrelid::regclass::text) AS idx
                           FROM pg_index GROUP BY indrelid, indkey, indclass, indexprs::text, indpred::text HAVING count(*) > 1"""):
        out.append(finding(db, "duplicate_index", "info", f"{d['t']} has duplicate indexes", ", ".join(d["idx"]),
                           "a person decides which to drop", d["t"]))
    for i in _rows(c, "SELECT indexrelid::regclass::text AS i FROM pg_index WHERE NOT indisvalid"):
        out.append(finding(db, "invalid_index", "warning", f"{i['i']} is invalid (a build that failed)", "",
                           "tidy: REINDEX INDEX CONCURRENTLY", i["i"]))
    age = int(c.execute("SELECT age(datfrozenxid) FROM pg_database WHERE datname = current_database()").fetchone()[0])
    if age > WRAP_WARN:
        out.append(finding(db, "wraparound", "critical" if age > WRAP_CRIT else "warning",
                           "the transaction age is high (wraparound)",
                           f"{age:,} of about 2,000,000,000: past it PostgreSQL stops accepting changes", "tidy: VACUUM"))
    hit = c.execute("""SELECT coalesce(sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0), 1)
                         FROM pg_statio_user_tables""").fetchone()[0]
    if float(hit) < 0.95:
        out.append(finding(db, "cache", "info", "the cache hit rate is low", f"{float(hit) * 100:.1f}% (95% or more is usual)",
                           "more memory for the database (shared_buffers)"))
    for s in _rows(c, """SELECT schemaname || '.' || sequencename AS s, last_value, max_value FROM pg_sequences
                          WHERE last_value IS NOT NULL AND last_value > 0.8 * max_value"""):
        out.append(finding(db, "sequence", "warning", f"{s['s']} is near its limit", f"{s['last_value']:,} of {s['max_value']:,}",
                           "a person widens it (bigint)", s["s"]))
    for t in _rows(c, """SELECT n.nspname || '.' || c.relname AS t FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                          WHERE c.relkind = 'r' AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                            AND n.nspname NOT LIKE 'pg_toast%'
                            AND NOT EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid = c.oid AND i.indisprimary)"""):
        out.append(finding(db, "no_primary_key", "info", f"{t['t']} has no primary key", "", "a person decides", t["t"]))
    return out, {"database": db, "bytes": int(size), "transaction_age": age, "cache_hit": round(float(hit) * 100, 1)}


def check_server(c, memory_bytes: int | None = None, idle_minutes: int = 30) -> list[dict]:
    """What is the server's, not one database's: connections, long transactions, replication, memory settings."""
    out: list[dict] = []
    used, limit = c.execute("SELECT (SELECT count(*) FROM pg_stat_activity), current_setting('max_connections')::int").fetchone()
    if used > 0.8 * limit:
        out.append(finding("(server)", "connections", "critical" if used > 0.9 * limit else "warning",
                           "connections are near the limit", f"{used} of {limit}", "find who holds them (locks)"))
    for s in _rows(c, """SELECT pid, datname, usename, state, round(extract(epoch FROM now() - xact_start) / 60) AS minutes,
                                left(query, 200) AS query FROM pg_stat_activity
                          WHERE xact_start < now() - interval '30 minutes' AND pid <> pg_backend_pid()"""):
        idle = s["state"] == "idle in transaction"
        out.append(finding(str(s["datname"]), "long_tx", "warning",
                           f"a session has been {'idle in' if idle else 'running'} a transaction for {s['minutes']:.0f} minutes",
                           f"pid {s['pid']} ({s['usename']}): {s['query']}",
                           f"ended by itself after {idle_minutes} minutes" if idle else "a person may cancel it (locks)", str(s["pid"])))
    for r in _rows(c, """SELECT client_addr::text AS who, state, coalesce(extract(epoch FROM replay_lag), 0) AS lag
                           FROM pg_stat_replication"""):
        if float(r["lag"]) > 60:
            out.append(finding("(server)", "replication", "warning", "the standby is behind",
                               f"{r['who']}: {float(r['lag']):.0f} seconds", "look at the standby and the network"))
    shared = c.execute("SELECT pg_size_bytes(current_setting('shared_buffers'))").fetchone()[0]
    if memory_bytes and shared < memory_bytes * 0.1:
        out.append(finding("(server)", "settings", "info", "shared_buffers is small for this server",
                           f"{shared // 1048576} MB of {memory_bytes // 1048576} MB memory (about 25% is usual)",
                           "set it in the database's settings (docker-compose: postgres -c shared_buffers=...)"))
    return out


def check(memory_bytes: int | None = None, idle_minutes: int = 30) -> dict:
    """Every database's findings and figures, worst first."""
    findings: list[dict] = []
    figures: list[dict] = []
    from .config import get_settings
    with connect(get_settings().db_name) as c:
        findings += check_server(c, memory_bytes, idle_minutes)
    for db in databases():
        try:
            with connect(db) as c:
                f, fig = check_database(c, db, memory_bytes)
                findings += f
                figures.append(fig)
        except Exception as exc:  # noqa: BLE001 - one database that cannot be reached is a finding, not a failure
            findings.append(finding(db, "unreachable", "warning", f"{db} could not be checked", str(exc)[:200]))
    findings.sort(key=lambda x: (-LEVELS.index(x["level"]), x["database"], x["key"]))
    return {"at": datetime.now(UTC).isoformat(timespec="seconds"), "findings": findings, "databases": figures}


# ---------------------------------------------------------------- the guards, the window
def busy_reason() -> str:
    """Why maintenance must wait ("" when it may run): a backup, a restore, a self-test, maintenance."""
    try:
        from . import maintenance
        if maintenance.state():
            return "a restore or an update is running"
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import test_lock
        from .testing import store
        with store.engine().connect() as t:
            if test_lock.active(t):
                return "a self-test is running"
    except Exception:  # noqa: BLE001
        pass
    try:
        from .mcp_operations import helper
        b = helper("GET", "/backups", timeout=10)
        if (b.get("state") or {}).get("running"):
            return "a backup is running"
    except Exception:  # noqa: BLE001
        pass
    return ""


def in_window(now: datetime, start: str, end: str) -> bool:
    """Whether a local time is inside the window (it may cross midnight: 23:00 to 03:00)."""
    t = now.strftime("%H:%M")
    return start <= t < end if start <= end else t >= start or t < end


# ---------------------------------------------------------------- doing
def tidy(findings: list[dict], dry_run: bool = False) -> list[dict]:
    """What the check found for tidying, done: VACUUM (ANALYZE), ANALYZE, REINDEX CONCURRENTLY (no table locked)."""
    done: list[dict] = []
    wanted: dict[str, list[tuple[str, str]]] = {}
    for f in findings:
        if f["key"] in ("bloat", "never_vacuumed"):
            wanted.setdefault(f["database"], []).append(("VACUUM (ANALYZE) " + _ident(f["target"]), f["target"]))
        elif f["key"] == "stale_stats":
            wanted.setdefault(f["database"], []).append(("ANALYZE " + _ident(f["target"]), f["target"]))
        elif f["key"] == "invalid_index":
            wanted.setdefault(f["database"], []).append(("REINDEX INDEX CONCURRENTLY " + _ident(f["target"]), f["target"]))
        elif f["key"] == "wraparound":
            wanted.setdefault(f["database"], []).append(("VACUUM (FREEZE, ANALYZE)", "(the whole database)"))
    for db, steps in wanted.items():
        seen = set()
        if dry_run:
            done += [{"database": db, "sql": s, "target": t, "status": "would run"} for s, t in steps]
            continue
        with connect(db) as c:
            for sql, target in steps:
                if sql in seen:
                    continue
                seen.add(sql)
                started = time.perf_counter()
                try:
                    c.execute(sql)
                    done.append({"database": db, "sql": sql, "target": target, "status": "done",
                                 "seconds": round(time.perf_counter() - started, 1)})
                except Exception as exc:  # noqa: BLE001
                    done.append({"database": db, "sql": sql, "target": target, "status": f"failed: {str(exc)[:160]}"})
    return done


def _ident(qualified: str) -> str:
    """schema.name quoted for SQL, from what the catalogue gave (never from a person's typing alone)."""
    import re
    parts = [q.replace('""', '"') if q else plain
             for q, plain in re.findall(r'"((?:[^"]|"")*)"|([^."]+)', str(qualified))]
    return ".".join('"' + p.replace('"', '""') + '"' for p in parts if p)


def table_size(db: str, table: str) -> int:
    """A table's size with its indexes and toast, in bytes."""
    with connect(db) as c:
        return int(c.execute("SELECT pg_total_relation_size(%s::regclass)", (table,)).fetchone()[0])


def compact_preview(db: str, table: str) -> dict:
    """What VACUUM FULL of one table would win, and a token to confirm it with (10 minutes)."""
    if db not in databases():
        raise ValueError(f"No database {db}.")
    with connect(db) as c:
        row = c.execute("""SELECT pg_total_relation_size(c.oid), coalesce(s.n_dead_tup, 0), coalesce(s.n_live_tup, 0)
                             FROM pg_class c LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                            WHERE c.oid = to_regclass(%s)""", (table,)).fetchone()
    if not row:
        raise ValueError(f"No table {table} in {db}.")
    size, dead, live = (int(x) for x in row)
    win = int(size * dead / max(dead + live, 1))
    token = make_token({"database": db, "table": table})
    return {"database": db, "table": table, "bytes": size, "about_to_win": win, "confirm": token,
            "warning": "The table is locked while it runs: nobody can read or change it until it ends."}


def compact(token: str) -> dict:
    """VACUUM FULL of the table a confirmation names (it locks the table while it runs); the space won is said."""
    what = read_token(token)
    if "table" not in what:
        raise ValueError("That confirmation is not for compacting.")
    before = table_size(what["database"], what["table"])
    with connect(what["database"]) as c:
        c.execute("VACUUM (FULL, ANALYZE) " + _ident(what["table"]))
    after = table_size(what["database"], what["table"])
    return {**what, "before": before, "after": after, "won": before - after}


def locks() -> list[dict]:
    """Who is blocked by whom, and for how long, on every database."""
    from .config import get_settings
    with connect(get_settings().db_name) as c:
        return _rows(c, """SELECT a.pid, a.datname AS database, a.usename AS login, a.state,
                                  round(extract(epoch FROM now() - coalesce(a.xact_start, a.query_start))) AS seconds,
                                  left(a.query, 300) AS query, pg_blocking_pids(a.pid) AS blocked_by
                             FROM pg_stat_activity a
                            WHERE a.pid <> pg_backend_pid() AND (cardinality(pg_blocking_pids(a.pid)) > 0
                                  OR a.pid IN (SELECT unnest(pg_blocking_pids(b.pid)) FROM pg_stat_activity b)
                                  OR a.state = 'idle in transaction')
                            ORDER BY seconds DESC""")


def stop_preview(pid: int, end: bool) -> dict:
    """What cancelling a session's query (or ending the session) would stop, and the confirmation to do it."""
    found = [x for x in locks() if int(x["pid"]) == int(pid)]
    if not found:
        raise ValueError(f"No session {pid} holding or waiting for a lock.")
    token = make_token({"pid": int(pid), "end": bool(end)})
    return {**found[0], "action": "end the session" if end else "cancel its query", "confirm": token}


def stop(token: str) -> dict:
    """Cancels the query or ends the session a confirmation names."""
    what = read_token(token)
    if "pid" not in what:
        raise ValueError("That confirmation is not for a session.")
    from .config import get_settings
    with connect(get_settings().db_name) as c:
        fn = "pg_terminate_backend" if what["end"] else "pg_cancel_backend"
        ok = c.execute(f"SELECT {fn}(%s)", (what["pid"],)).fetchone()[0]
    return {**what, "done": bool(ok)}


def end_idle(minutes: int) -> list[int]:
    """Sessions idle in a transaction longer than `minutes` ended (they hold locks and stop tidying)."""
    if minutes <= 0:
        return []
    from .config import get_settings
    with connect(get_settings().db_name) as c:
        return [r[0] for r in c.execute("""SELECT pid FROM pg_stat_activity
                                             WHERE state = 'idle in transaction' AND pid <> pg_backend_pid()
                                               AND state_change < now() - make_interval(mins => %s)
                                               AND pg_terminate_backend(pid)""", (int(minutes),))]


def clear(conn, actor: str) -> dict:
    """The keep-for rules applied now: housekeeping, then the old alert history."""
    from . import operations
    out = {"housekeeping": operations.run(conn, actor, dry_run=False)}
    out["alert_history"] = conn.execute(text("DELETE FROM core.alert_history WHERE at < now() - interval '90 days'")).rowcount
    return out


# ---------------------------------------------------------------- kept
def record(conn, kind: str, by: str, findings=None, actions=None, status: str = "ok", note: str = "") -> int:
    """Keeps one maintenance run (check, tidy, compact, clear, locks) with what it found and did."""
    return conn.execute(text("""INSERT INTO core.db_maintenance_runs (kind, by_whom, findings, actions, status, note)
                                VALUES (:k, :b, CAST(:f AS jsonb), CAST(:a AS jsonb), :s, :n) RETURNING id"""),
                        {"k": kind, "b": by, "f": json.dumps(findings or [], default=str), "a": json.dumps(actions or [], default=str),
                         "s": status, "n": note[:500]}).scalar()


def last_check(conn) -> dict | None:
    """The newest database check's findings and when it ran."""
    r = conn.execute(text("""SELECT at, findings FROM core.db_maintenance_runs WHERE kind = 'check' AND status = 'ok'
                              ORDER BY at DESC LIMIT 1""")).mappings().first()
    return {"at": r["at"].isoformat(), "findings": r["findings"]} if r else None


def history(conn, limit: int = 60) -> list[dict]:
    """The maintenance runs, newest first, with how much each found and did."""
    rows = conn.execute(text("""SELECT id, at, kind, by_whom, status, note, jsonb_array_length(findings) AS found,
                                       jsonb_array_length(actions) AS done FROM core.db_maintenance_runs
                                 ORDER BY at DESC LIMIT :l"""), {"l": limit}).mappings().all()
    return [{**dict(r), "at": r["at"].isoformat()} for r in rows]


def settings_of(conn) -> dict:
    """The maintenance window and the idle-transaction limit from the settings."""
    from . import settings as st
    v = st.values(conn)
    return {"window_start": v.get("db_maint_window_start", "01:00"), "window_end": v.get("db_maint_window_end", "05:00"),
            "idle_tx_minutes": int(v.get("db_idle_tx_minutes", 30))}


def tidy_due(conn, now_local: datetime) -> bool:
    """Whether tonight's tidy is due: in the window and not done since the window opened."""
    s = settings_of(conn)
    if not in_window(now_local, s["window_start"], s["window_end"]):
        return False
    last = conn.execute(text("SELECT max(at) FROM core.db_maintenance_runs WHERE kind = 'tidy' AND status = 'ok'")).scalar()
    return not last or datetime.now(UTC) - last > timedelta(hours=20)


# ---------------------------------------------------------------- eax db (in the api container)
def main(argv: list[str]) -> int:
    """python -m eax.dbmaint check | tidy [--dry-run] | compact <db> <table> [--yes] | clear | locks | cancel <pid> | end <pid>"""
    from .db import get_engine
    cmd = argv[0] if argv else "check"
    try:
        if cmd in ("tidy", "compact", "clear") and (why := busy_reason()):
            print(f"Not now: {why}. Try again when it has finished.")
            return 1
        if cmd == "check":
            out = check()
            with get_engine().begin() as conn:
                record(conn, "check", "eax db", out["findings"])
            for f in out["findings"]:
                print(f"[{f['level'].upper():8}] {f['database']}: {f['what']}. {f['detail']}" + (f" -> {f['action']}" if f["action"] else ""))
            print(f"{len(out['findings'])} finding(s) in {len(out['databases'])} database(s).")
            return 0
        if cmd == "tidy":
            found = check()["findings"]
            done = tidy(found, dry_run="--dry-run" in argv)
            if "--dry-run" not in argv:
                with get_engine().begin() as conn:
                    record(conn, "tidy", "eax db", found, done)
            for d in done:
                print(f"{d['database']}: {d['sql']} ({d['status']})")
            print(f"{len(done)} step(s).")
            return 0
        if cmd == "compact" and len(argv) >= 3:
            p = compact_preview(argv[1], argv[2])
            print(f"{p['table']} in {p['database']}: {p['bytes'] // 1048576} MB, about {p['about_to_win'] // 1048576} MB to win. {p['warning']}")
            if "--yes" not in argv and input("Type yes to compact it now: ").strip() != "yes":
                print("Nothing done.")
                return 1
            r = compact(p["confirm"])
            with get_engine().begin() as conn:
                record(conn, "compact", "eax db", actions=[r])
            print(f"Compacted: {r['won'] // 1048576} MB won.")
            return 0
        if cmd == "clear":
            with get_engine().begin() as conn:
                out = clear(conn, "eax db")
                record(conn, "clear", "eax db", actions=[out])
            print(json.dumps(out, default=str, indent=2))
            return 0
        if cmd == "locks":
            rows = locks()
            for r in rows:
                print(f"pid {r['pid']} {r['database']} {r['login']} {r['state']} {r['seconds']}s blocked by {r['blocked_by']}: {r['query']}")
            print(f"{len(rows)} session(s).")
            return 0
        if cmd in ("cancel", "end") and len(argv) >= 2:
            p = stop_preview(int(argv[1]), cmd == "end")
            print(f"{p['action']}: pid {p['pid']} ({p['login']}, {p['state']}): {p['query']}")
            if "--yes" not in argv and input("Type yes to go on: ").strip() != "yes":
                print("Nothing done.")
                return 1
            r = stop(p["confirm"])
            with get_engine().begin() as conn:
                record(conn, "locks", "eax db", actions=[r])
            print("Done." if r["done"] else "It had already ended.")
            return 0
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(main.__doc__)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
