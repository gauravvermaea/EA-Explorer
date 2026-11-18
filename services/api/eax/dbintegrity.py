"""The databases' integrity and their recent records, checked, and fixed when wrong (Release 6.6, R6.6.1; owner, 15 Nov
2026, 21:31: "Postgres integrety and recent record check + fixing if issues are there"; agreed 17 Nov 2026, 19:46, D750).

For every database on the server (EA Explorer's, Keycloak's, Reports', Documents', the library's, the views'): weekly
(Sundays 02:20), after every restore (a rebuild from a backup is a restore) and after a DR site takes over, and on
demand (System Admin › Database maintenance › Integrity, `eax db integrity`):

  indexes         every B-tree index read whole and checked (PostgreSQL's amcheck)        fix: REINDEX (safe)
  tables          each table's pages checked (amcheck's verify_heapam)                     no fix here: restore that part
  constraints     a foreign key or check never validated                                   fix: VALIDATE (safe)
  orphan rows     rows whose foreign key points at nothing                                 fix: removed, on an admin's yes
  sequences       a sequence behind the rows it numbers (the next insert would collide)    fix: moved on (safe)
  recent records  the newest commit, tag, audit line, change and document: when each was   said, for comparing with the
                                                                                          backup or the primary

Safe fixes happen by themselves, each after a backup made in the last day (one is made first when there is none) and
with a notice to the admins; anything that touches rows waits for an admin's yes (a preview, then a confirmation good
for ten minutes), and the rows removed are kept in the run's record. Every check and fix is in core.db_maintenance_runs
(kinds integrity and repair) and the audit trail; the alert db_integrity counts what is still wrong. Superuser
connections, as the database maintenance uses (eax/dbmaint.py); nothing is added to the database's logic (D248).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from . import dbmaint as dm

SAFE = ("reindex", "validate", "sequence")
ROWS = ("orphans",)
MAX_INDEX_BYTES = 2 * 1024 ** 3        # bigger indexes are checked on demand only (they take long)
RECENT = [   # (what, the table, its time column)
    ("the newest commit", "core.commits", "committed_at"),
    ("the newest model tag", "core.model_tags", "created_at"),
    ("the newest audit line", "audit.events", "at"),
    ("the newest change log entry", "changelog.entries", "at"),
    ("the newest project document", "proj.documents", "created_at"),
    ("the newest sign-in", "personal.sign_ins", "at"),
]


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _qualified(schema: str, table: str) -> str:
    return f"{_q(schema)}.{_q(table)}"


# ---------------------------------------------------------------- the checks of one database (pure but for the cursor)
def check_indexes(c, db: str, everything: bool = False) -> list[dict]:
    """Every B-tree index in the database's own schemas read and checked; a broken one is rebuilt (safe)."""
    out = []
    try:
        c.execute("CREATE EXTENSION IF NOT EXISTS amcheck")
    except Exception as exc:  # noqa: BLE001 - not installed with this PostgreSQL: said, not failed
        return [dm.finding(db, "amcheck", "info", "Indexes and tables not read", f"amcheck is not available: {exc}")]
    rows = dm._rows(c, """SELECT n.nspname AS schema, i.relname AS index, i.oid::bigint AS oid, pg_relation_size(i.oid) AS bytes
                            FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid JOIN pg_namespace n ON n.oid = i.relnamespace
                            JOIN pg_am a ON a.oid = i.relam
                           WHERE a.amname = 'btree' AND x.indisvalid AND i.relpersistence = 'p'
                             AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%'""")
    for r in rows:
        if r["bytes"] > MAX_INDEX_BYTES and not everything:
            continue
        try:
            c.execute("SELECT bt_index_check(%s::regclass, true)", (r["oid"],))
        except Exception as exc:  # noqa: BLE001 - the index is broken: rebuilt
            out.append(dm.finding(db, "reindex", "critical", f"Index {r['schema']}.{r['index']} is damaged",
                                  str(exc).splitlines()[0][:300], "rebuilt (safe, by itself)",
                                  _qualified(r["schema"], r["index"])))
    return out


def check_tables(c, db: str) -> list[dict]:
    """Each table's pages checked (amcheck's verify_heapam, PostgreSQL 14 and later); no fix here."""
    out = []
    try:
        tables = dm._rows(c, """SELECT n.nspname AS schema, t.relname AS table, t.oid::bigint AS oid FROM pg_class t
                                  JOIN pg_namespace n ON n.oid = t.relnamespace
                                 WHERE t.relkind = 'r' AND t.relpersistence = 'p'
                                   AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%'""")
        for t in tables:
            bad = dm._rows(c, "SELECT blkno, msg FROM verify_heapam(%s::regclass) LIMIT 3", t["oid"])
            if bad:
                out.append(dm.finding(db, "table", "critical", f"Table {t['schema']}.{t['table']} has damaged pages",
                                      "; ".join(f"page {b['blkno']}: {b['msg']}" for b in bad)[:400],
                                      "restore this database from the newest good backup (Backups › Restore › a database)",
                                      _qualified(t["schema"], t["table"])))
    except Exception as exc:  # noqa: BLE001 - an older amcheck without verify_heapam
        out.append(dm.finding(db, "table", "info", "Tables not read page by page", str(exc).splitlines()[0][:200]))
    return out


def check_constraints(c, db: str) -> list[dict]:
    """Foreign keys and checks never validated (safe to validate), and rows whose foreign key points at nothing (removed
    only on an admin's yes)."""
    out = []
    fks = dm._rows(c, """SELECT k.conname AS name, k.convalidated AS valid, k.contype AS kind,
                                cn.nspname AS cschema, cl.relname AS ctable, pn.nspname AS pschema, pl.relname AS ptable,
                                (SELECT array_agg(a.attname ORDER BY u.i) FROM unnest(k.conkey) WITH ORDINALITY u(n, i)
                                   JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.n) AS ccols,
                                (SELECT array_agg(a.attname ORDER BY u.i) FROM unnest(k.confkey) WITH ORDINALITY u(n, i)
                                   JOIN pg_attribute a ON a.attrelid = k.confrelid AND a.attnum = u.n) AS pcols
                           FROM pg_constraint k JOIN pg_class cl ON cl.oid = k.conrelid JOIN pg_namespace cn ON cn.oid = cl.relnamespace
                           LEFT JOIN pg_class pl ON pl.oid = k.confrelid LEFT JOIN pg_namespace pn ON pn.oid = pl.relnamespace
                          WHERE k.contype IN ('f', 'c') AND cn.nspname NOT IN ('pg_catalog', 'information_schema')""")
    for k in fks:
        where = f"{k['cschema']}.{k['ctable']}"
        if not k["valid"]:
            out.append(dm.finding(db, "validate", "warning", f"Constraint {k['name']} on {where} was never checked",
                                  "added NOT VALID: rows from before it may break it", "validated (safe, by itself)",
                                  json.dumps({"table": _qualified(k["cschema"], k["ctable"]), "name": k["name"]})))
        if k["kind"] != "f" or not k["ccols"]:
            continue
        sql = orphans_sql(k)
        n = c.execute(f"SELECT count(*) FROM ({sql}) o").fetchone()[0]
        if n:
            out.append(dm.finding(db, "orphans", "critical", f"{n} row(s) of {where} point at nothing in {k['pschema']}.{k['ptable']}",
                                  f"{', '.join(k['ccols'])} with no matching {', '.join(k['pcols'])} (foreign key {k['name']})",
                                  "remove them, on an admin's yes (preview first)", json.dumps({"constraint": k["name"],
                                                                                               "table": where})))
    return out


def orphans_sql(k: dict) -> str:
    """The rows of the child table whose foreign key matches no row of the parent (every column set)."""
    child, parent = _qualified(k["cschema"], k["ctable"]), _qualified(k["pschema"], k["ptable"])
    notnull = " AND ".join(f"c.{_q(a)} IS NOT NULL" for a in k["ccols"])
    match = " AND ".join(f"p.{_q(b)} = c.{_q(a)}" for a, b in zip(k["ccols"], k["pcols"], strict=True))
    return f"SELECT c.ctid AS row_id, c.* FROM {child} c WHERE {notnull} AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE {match})"


def check_sequences(c, db: str) -> list[dict]:
    """A sequence behind the column it numbers (the next insert would collide): moved on (safe)."""
    out = []
    seqs = dm._rows(c, """SELECT sn.nspname AS sschema, s.relname AS seq, tn.nspname AS tschema, t.relname AS table, a.attname AS col
                            FROM pg_class s JOIN pg_namespace sn ON sn.oid = s.relnamespace
                            JOIN pg_depend d ON d.objid = s.oid AND d.classid = 'pg_class'::regclass AND d.deptype IN ('a', 'i')
                            JOIN pg_class t ON t.oid = d.refobjid JOIN pg_namespace tn ON tn.oid = t.relnamespace
                            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
                           WHERE s.relkind = 'S' AND sn.nspname NOT IN ('pg_catalog', 'information_schema')""")
    for s in seqs:
        seq = _qualified(s["sschema"], s["seq"])
        top = c.execute(f"SELECT max({_q(s['col'])}) FROM {_qualified(s['tschema'], s['table'])}").fetchone()[0]
        last, called = c.execute(f"SELECT last_value, is_called FROM {seq}").fetchone()
        nxt = last + 1 if called else last
        if isinstance(top, int) and top >= nxt:
            out.append(dm.finding(db, "sequence", "critical", f"{s['tschema']}.{s['table']}.{s['col']}'s numbering is behind",
                                  f"next number {nxt}, but {top} is already used", "moved on past it (safe, by itself)",
                                  json.dumps({"sequence": seq, "to": top})))
    return out


def recent_records(c, db: str) -> list[dict]:
    """When the newest of each kind of record was made (EA Explorer's databases): read beside the backup's or the
    primary's, they show a restore or a DR site did not lose the last hours."""
    out = []
    for what, table, col in RECENT:
        schema, name = table.split(".")
        if not c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema = %s AND table_name = %s AND column_name = %s",
                         (schema, name, col)).fetchone():
            continue
        at = c.execute(f"SELECT max({_q(col)}) FROM {_qualified(schema, name)}").fetchone()[0]
        out.append({"database": db, "what": what, "table": table, "newest": at.isoformat() if at else None})
    return out


def check(dbs: list[str] | None = None, everything: bool = False, connect=None) -> dict:
    """Every database checked: the findings, the recent records, how long it took."""
    connect = connect or dm.connect
    started = time.time()
    findings, recent, done = [], [], []
    for db in dbs or dm.databases():
        try:
            with connect(db) as c:
                findings += check_indexes(c, db, everything) + check_tables(c, db) + check_constraints(c, db) + check_sequences(c, db)
                recent += recent_records(c, db)
            done.append(db)
        except Exception as exc:  # noqa: BLE001 - one database away does not stop the others
            findings.append(dm.finding(db, "connect", "critical", "The database could not be checked", str(exc)[:300]))
    return {"findings": findings, "recent": recent, "databases": done, "seconds": round(time.time() - started, 1),
            "at": datetime.now(UTC).isoformat()}


# ---------------------------------------------------------------- fixes
def fix_sql(f: dict) -> str:
    """The statement a safe fix runs."""
    if f["key"] == "reindex":
        return f"REINDEX INDEX CONCURRENTLY {f['target']}"
    t = json.loads(f["target"])
    if f["key"] == "validate":
        return f"ALTER TABLE {t['table']} VALIDATE CONSTRAINT {_q(t['name'])}"
    if f["key"] == "sequence":
        return f"SELECT setval('{t['sequence']}', {int(t['to'])}, true)"
    raise ValueError(f"{f['key']} is not a safe fix")


def safe_fixes(findings: list[dict], connect=None) -> list[dict]:
    """Every safe fix of the findings, each on its own (one failing does not stop the others)."""
    connect = connect or dm.connect
    out = []
    for f in [f for f in findings if f["key"] in SAFE]:
        sql = fix_sql(f)
        try:
            with connect(f["database"]) as c:
                c.execute(sql)
            out.append({"database": f["database"], "what": f["what"], "sql": sql, "status": "done"})
        except Exception as exc:  # noqa: BLE001
            out.append({"database": f["database"], "what": f["what"], "sql": sql, "status": f"failed: {str(exc)[:200]}"})
    return out


def repair_preview(f: dict, connect=None) -> dict:
    """What removing a finding's orphan rows would remove (up to 20 shown), with a confirmation good for ten minutes."""
    if f.get("key") not in ROWS:
        raise ValueError("Only orphan rows are repaired by hand; the safe fixes run by themselves.")
    connect = connect or dm.connect
    t = json.loads(f["target"])
    k = _constraint(f["database"], t["constraint"], connect)
    with connect(f["database"]) as c:
        rows = dm._rows(c, orphans_sql(k) + " LIMIT 20")
        n = c.execute(f"SELECT count(*) FROM ({orphans_sql(k)}) o").fetchone()[0]
    return {"database": f["database"], "table": t["table"], "count": n, "sample": json.loads(json.dumps(rows, default=str)),
            "confirm": dm.make_token({"do": "orphans", "database": f["database"], "constraint": t["constraint"], "count": n})}


def _constraint(db: str, name: str, connect) -> dict:
    with connect(db) as c:
        for k in check_constraints_rows(c):
            if k["name"] == name:
                return k
    raise ValueError(f"The foreign key {name} is no longer there: check again.")


def check_constraints_rows(c) -> list[dict]:
    """The foreign keys of a database, as check_constraints reads them."""
    return [k for k in dm._rows(c, """SELECT k.conname AS name, cn.nspname AS cschema, cl.relname AS ctable, pn.nspname AS pschema,
                                             pl.relname AS ptable,
                                             (SELECT array_agg(a.attname ORDER BY u.i) FROM unnest(k.conkey) WITH ORDINALITY u(n, i)
                                                JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.n) AS ccols,
                                             (SELECT array_agg(a.attname ORDER BY u.i) FROM unnest(k.confkey) WITH ORDINALITY u(n, i)
                                                JOIN pg_attribute a ON a.attrelid = k.confrelid AND a.attnum = u.n) AS pcols
                                        FROM pg_constraint k JOIN pg_class cl ON cl.oid = k.conrelid
                                        JOIN pg_namespace cn ON cn.oid = cl.relnamespace JOIN pg_class pl ON pl.oid = k.confrelid
                                        JOIN pg_namespace pn ON pn.oid = pl.relnamespace WHERE k.contype = 'f'""")]


def repair(token: str, connect=None) -> dict:
    """The orphan rows previewed removed, in one transaction; the rows kept in the answer (and so in the run's record).
    Refused when more rows match than were previewed (someone changed things since)."""
    connect = connect or dm.connect
    what = dm.read_token(token)
    if what.get("do") != "orphans":
        raise ValueError("Preview it again: that confirmation is not for a repair.")
    k = _constraint(what["database"], what["constraint"], connect)
    with connect(what["database"], autocommit=False) as c:
        rows = dm._rows(c, orphans_sql(k))
        if len(rows) > int(what["count"]):
            raise ValueError(f"{len(rows)} rows match now, {what['count']} were previewed: preview it again.")
        ids = [r["row_id"] for r in rows]
        if ids:
            c.execute(f"DELETE FROM {_qualified(k['cschema'], k['ctable'])} WHERE ctid = ANY(%s::tid[])", ([str(i) for i in ids],))
        c.commit()
    return {"database": what["database"], "table": f"{k['cschema']}.{k['ctable']}", "removed": len(rows),
            "rows": json.loads(json.dumps(rows, default=str))}


# ---------------------------------------------------------------- a backup first, a run, the notice
def backed_up_recently(hours: int = 24, ask=None) -> bool:
    """Whether the operations helper has a successful infrastructure backup from the last `hours`."""
    from .api.admin import _ops_raw
    ask = ask or (lambda: _ops_raw("GET", "/backups", timeout=20).get("infrastructure") or [])
    now = datetime.now(UTC)
    for b in ask():
        try:
            made = datetime.strptime(str(b.get("name", ""))[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            continue
        if b.get("status", "ok") == "ok" and (now - made).total_seconds() <= hours * 3600:
            return True
    return False


def fixes_by_themselves(conn) -> bool:
    """Whether the weekly and after-restore checks make the safe fixes by themselves (setting integrity_fixes, off until an
    admin chooses it: a fix takes a backup behind the maintenance page first; the owner, 18 Nov 2026, 10:18: "not sure
    how or why the application went to mantainance ... I didnt ask")."""
    from . import settings as S
    try:
        return bool(S.values(conn).get("integrity_fixes"))
    except Exception:  # noqa: BLE001
        return False


def run(conn, by: str, after: str = "", backup=None, fix: bool | None = None) -> dict:
    """A whole run: the check; when it found safe fixes and fixing is asked for (fix=True: Fix the safe ones) or switched
    on (integrity_fixes, for the weekly and after-restore runs), a backup first (when there is none from the last day),
    the fixes, the check again; the run kept; the admins told when anything was found or fixed. Check now only checks."""
    fix = fixes_by_themselves(conn) if fix is None else fix
    out = check()
    actions: list[dict] = []
    safe = [f for f in out["findings"] if f["key"] in SAFE]
    if fix and safe:
        if not backed_up_recently():
            (backup or _backup_now)(by)
        actions = safe_fixes(safe)
        out = {**check(), "fixed_before": safe}
    dm.record(conn, "integrity", by, out["findings"], actions, note=(f"after {after}; " if after else "")
              + f"{len(out['databases'])} databases in {out['seconds']} s")
    _tell(conn, out, actions, after)
    return {**out, "actions": actions}


def _backup_now(by: str) -> None:
    """An infrastructure backup before the fixes, waited for (the weekly run can wait)."""
    from .api.admin import _ops_raw
    _ops_raw("POST", "/backups/backup", {"tag": "before-integrity-fixes", "by": by, "kind": "on-demand"}, timeout=30)
    started = time.time()
    while time.time() - started < 3 * 3600:
        time.sleep(5)
        st = _ops_raw("GET", "/backups", timeout=30).get("state") or {}
        if not st.get("busy"):
            if (st.get("result") or {}).get("status") != "ok":
                raise RuntimeError("the backup before the fixes failed: nothing was fixed")
            return
    raise RuntimeError("the backup before the fixes took over three hours: nothing was fixed")


def _tell(conn, out: dict, actions: list[dict], after: str) -> None:
    from . import alerts, notify
    left = [f for f in out["findings"] if f["level"] in ("warning", "critical")]
    if not left and not actions:
        return
    body = "\n".join([f"Fixed: {a['what']} ({a['status']})" for a in actions]
                     + [f"Still wrong: {f['database']}: {f['what']}. {f['action']}" for f in left])
    notify.create(conn, kind="db.integrity", category="system", actor="system", link="#/admin/db-maintenance",
                  title=(f"Database integrity{' after ' + after if after else ''}: {len(actions)} fixed, {len(left)} to look at")[:300],
                  body=body, recipients=alerts.people(conn), needs_action=bool(left))


def last(conn) -> dict | None:
    """The newest integrity run: its findings, its recent records, what it fixed."""
    from sqlalchemy import text
    r = conn.execute(text("""SELECT at, findings, actions, note FROM core.db_maintenance_runs WHERE kind = 'integrity'
                              ORDER BY at DESC LIMIT 1""")).mappings().first()
    return {"at": r["at"].isoformat(), "findings": r["findings"], "actions": r["actions"], "note": r["note"]} if r else None


def main(argv: list[str]) -> int:
    """python -m eax.dbintegrity check [--fix] [--everything] | repair <database> <constraint> [--yes]"""
    from .db import get_engine
    cmd = argv[0] if argv else "check"
    if cmd == "check":
        with get_engine().begin() as conn:
            out = run(conn, "eax db integrity", fix="--fix" in argv)   # only a check unless --fix
        for a in out["actions"]:
            print(f"fixed  {a['database']}: {a['what']} ({a['status']})")
        for f in out["findings"]:
            print(f"[{f['level'].upper():8}] {f['database']}: {f['what']}. {f['detail']}" + (f" -> {f['action']}" if f["action"] else ""))
        for r in out["recent"]:
            print(f"  {r['database']}: {r['what']}: {r['newest'] or 'none'}")
        print(f"{len(out['findings'])} finding(s), {len(out['actions'])} fixed, in {len(out['databases'])} database(s).")
        return 0
    if cmd == "repair" and len(argv) >= 3:
        f = {"key": "orphans", "database": argv[1], "target": json.dumps({"constraint": argv[2], "table": "?"})}
        p = repair_preview(f)
        print(f"{p['count']} row(s) of {p['database']} would be removed (foreign key {argv[2]}).")
        if "--yes" not in argv and input("Type yes to remove them: ").strip() != "yes":
            print("Nothing done.")
            return 1
        r = repair(p["confirm"])
        with get_engine().begin() as conn:
            dm.record(conn, "repair", "eax db repair", actions=[r])
        print(f"Removed {r['removed']} row(s); they are kept in the run's record.")
        return 0
    print(main.__doc__)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
