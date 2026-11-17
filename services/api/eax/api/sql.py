"""The SQL window: POST /api/v1/sql/query runs SQL (see eax/sqlconsole.py). In password mode a database user and password
are typed, as before Release 6 (owner, 17 Nov 2026, 20:45: "if username + password is used it comes prepopulated like
now"); in certificate mode nobody types one: the window's own login for the person's role (D742)."""

from __future__ import annotations

from flask import Response, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit, sqlconsole
from ..auth import require_auth
from ..db import get_engine
from .models import Free, FreeIn
from .schemas import SqlQueryIn, SqlQueryOut

blp = Blueprint(
    "sql", __name__, url_prefix="/api/v1/sql",
    description="SQL window: run queries as the window's own login for your role (Super Admin and IT Admin only; D742)",
)


def _console() -> tuple[str, str]:
    """The window's login for the person signed in: a Super Admin's, else an IT Admin's (D742)."""
    from ..permissions import SUPER_ADMIN
    return sqlconsole.console_login(g.user.has_role(SUPER_ADMIN))


def _creds(data: dict) -> tuple[str, str]:
    """The login a run uses: the typed user and password in password mode (as before Release 6), the window's own
    login for the person's role in certificate mode (D742, D752)."""
    if not sqlconsole.typed_login():
        return _console()
    user, pw = str(data.get("username") or ""), str(data.get("password") or "")
    if not user or not pw:
        abort(400, message="Give the database user and password (the services sign in with passwords here).")
    return user, pw


def _who(query: dict) -> str:
    return str(query.get("username") or "") if sqlconsole.typed_login() else _console()[0]


def _audit(query: dict, outcome: str, **extra) -> None:
    try:
        with get_engine().begin() as conn:
            audit.record(conn, actor=g.user.username, action="sql.query", object_type="database",
                         object_id=query.get("database") or "eaexplorer", source="api",
                         request_id=getattr(g, "request_id", None),
                         details={"db_user": _who(query),
                                  "outcome": outcome, "sql": query["sql"][:2000], **extra})
    except Exception:  # the audit must never hide the query's own result
        pass


@blp.route("/query")
class SqlQuery(MethodView):
    """/api/v1/sql/query: POST run SQL with a database login One or more statements; every result set comes back (at
    most 1,000 rows each, 30-second limit)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(SqlQueryIn)
    @blp.response(200, SqlQueryOut)
    @require_auth("system.operate")
    def post(self, query):
        """Run SQL with a database login

        One or more statements; every result set comes back (at most 1,000 rows each, 30-second
        limit). Rolled back at the end unless keep is true: then committed, and what the database login may do decides
        what is written (owner, 6 Nov 2026, replacing D52). Every run is in the audit trail, with whether it was kept.
        """
        if not sqlconsole.enabled():
            abort(404, message="The SQL window is turned off on this installation (EAX_SQL_CONSOLE_ENABLED=false).")
        try:
            result = sqlconsole.run(query.get("database") or "", *_creds(query), query["sql"], bool(query.get("keep")))
        except sqlconsole.SqlConsoleError as exc:
            _audit(query, "error", error=str(exc)[:500])
            abort(exc.status, message=str(exc), errors=exc.details)
        _audit(query, "kept" if result["committed"] else "ok", results=len(result["results"]),
               duration_ms=result["duration_ms"], kept=result["committed"])
        return result


@blp.route("/databases")
class SqlDatabases(MethodView):
    """/api/v1/sql/databases: GET the databases on this installation's server (EA Explorer's own first)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The databases on this installation's server (EA Explorer's own first)"""
        if not sqlconsole.enabled():
            abort(404, message="The SQL window is turned off on this installation (EAX_SQL_CONSOLE_ENABLED=false).")
        dbs = sqlconsole.databases()
        return {"databases": dbs, "about": {d: sqlconsole.ABOUT_DATABASES.get(d, "") for d in dbs},
                "typed": sqlconsole.typed_login(), "username": sqlconsole.DEFAULT_USER}


@blp.route("/schema")
class SqlSchema(MethodView):
    """/api/v1/sql/schema: GET the tables of a schema with their columns and the joins between them, for the SQL
    window's database diagram: ?schema=core (models: the repository) or proj (architecture…"""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The tables of a schema with their columns and the joins between them, for the SQL window's database diagram:
        ?schema=core (models: the repository) or proj (architecture projects) (owner, 8 Nov 2026)"""
        from flask import request
        from sqlalchemy import text

        from ..db import get_projects_engine
        schema = request.args.get("schema") or "core"
        if schema not in ("core", "proj"):
            abort(400, message="The schema is core (models) or proj (projects).")
        eng = get_projects_engine() if schema == "proj" else get_engine()
        with eng.connect() as conn:
            cols = conn.execute(text("""SELECT c.table_name AS t, c.column_name AS c, c.data_type AS type, c.is_nullable = 'YES' AS nullable
                                          FROM information_schema.columns c JOIN information_schema.tables t
                                            ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
                                         WHERE c.table_schema = :s ORDER BY c.table_name, c.ordinal_position"""), {"s": schema}).mappings().all()
            pks = conn.execute(text("""SELECT tc.table_name AS t, kcu.column_name AS c FROM information_schema.table_constraints tc
                                         JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name
                                          AND kcu.table_schema = tc.table_schema
                                        WHERE tc.table_schema = :s AND tc.constraint_type = 'PRIMARY KEY'"""), {"s": schema}).mappings().all()
            fks = conn.execute(text("""SELECT cl.relname AS t, a.attname AS c, rn.nspname AS to_schema, rt.relname AS to_t, ra.attname AS to_c
                                         FROM pg_constraint k JOIN pg_class cl ON cl.oid = k.conrelid JOIN pg_namespace n ON n.oid = cl.relnamespace
                                         JOIN pg_class rt ON rt.oid = k.confrelid JOIN pg_namespace rn ON rn.oid = rt.relnamespace
                                         JOIN LATERAL unnest(k.conkey, k.confkey) AS u(a1, a2) ON true
                                         JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.a1
                                         JOIN pg_attribute ra ON ra.attrelid = k.confrelid AND ra.attnum = u.a2
                                        WHERE k.contype = 'f' AND n.nspname = :s"""), {"s": schema}).mappings().all()
        pk = {(r["t"], r["c"]) for r in pks}
        fk = {(r["t"], r["c"]): f"{'' if r['to_schema'] == schema else r['to_schema'] + '.'}{r['to_t']}.{r['to_c']}" for r in fks}
        tables: dict[str, list] = {}
        for r in cols:
            tables.setdefault(r["t"], []).append({"name": r["c"], "type": r["type"], "nullable": r["nullable"],
                                                  "pk": (r["t"], r["c"]) in pk, "fk": fk.get((r["t"], r["c"]))})
        return {"schema": schema, "tables": [{"name": t, "columns": c} for t, c in tables.items()],
                "joins": [{"from": r["t"], "column": r["c"], "to": r["to_t"], "to_column": r["to_c"],
                           "outside": r["to_schema"] != schema} for r in fks]}


# ---------------------------------------------------------------- the database workspace (R2.57)
def _login(data: dict) -> tuple[str, str, str]:
    if not sqlconsole.enabled():
        abort(404, message="The SQL window is turned off on this installation (EAX_SQL_CONSOLE_ENABLED=false).")
    return (str(data.get("database") or ""), *_creds(data))


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except sqlconsole.SqlConsoleError as exc:
        abort(exc.status, message=str(exc), errors=exc.details)


@blp.route("/browse")
class SqlBrowse(MethodView):
    """/api/v1/sql/browse: POST the tree of a database {database}: its schemas, tables and views
    that the login may read, with estimated rows and size (R2.57)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """The tree of a database {database}: its schemas, tables and views that the login may read,
        with estimated rows and size (R2.57)"""
        return _guard(sqlconsole.browse, *_login(data or {}))


@blp.route("/describe")
class SqlDescribe(MethodView):
    """/api/v1/sql/describe: POST a table's or view's structure {database, schema, table}:
    columns, indexes, constraints, size, rows, a view's definition (R2.57)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """A table's or view's structure {database, schema, table}: columns, indexes, constraints,
        size, rows, a view's definition (R2.57)"""
        data = data or {}
        return _guard(sqlconsole.describe, *_login(data), str(data.get("schema") or ""), str(data.get("table") or ""))


@blp.route("/rows")
class SqlRows(MethodView):
    """/api/v1/sql/rows: POST a page of a table's rows {..., schema, table, page, order, desc, column, contains}: 200
    a page, sorted and filtered, with the count; read only (R2.57)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """A page of a table's rows {..., schema, table, page, order, desc, column, contains}: 200 a page, sorted and
        filtered, with the count; read only (R2.57). In the audit trail"""
        data = data or {}
        out = _guard(sqlconsole.table_rows, *_login(data), str(data.get("schema") or ""), str(data.get("table") or ""),
                     int(data.get("page") or 0), str(data.get("order") or ""), bool(data.get("desc")),
                     str(data.get("column") or ""), str(data.get("contains") or ""))
        _audit({**data, "sql": f"rows of {data.get('schema')}.{data.get('table')}"}, "ok", kind="rows")
        return out


@blp.route("/explain")
class SqlExplain(MethodView):
    """/api/v1/sql/explain: POST a statement's query plan {..., sql, analyze}: EXPLAIN as JSON; with analyze it runs
    and is rolled back (R2.57)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def post(self, data):
        """A statement's query plan {..., sql, analyze}: EXPLAIN as JSON; with analyze it runs and is rolled back (R2.57)"""
        data = data or {}
        out = _guard(sqlconsole.explain, *_login(data), str(data.get("sql") or ""), bool(data.get("analyze")))
        _audit({**data, "sql": str(data.get("sql") or "")}, "ok", kind="explain", analyze=bool(data.get("analyze")))
        return out


@blp.route("/export")
class SqlExport(MethodView):
    """/api/v1/sql/export: POST a query's rows as a file {..., sql, format: csv|xlsx}: at most 100,000 rows, rolled
    back (R2.57)."""
    @blp.doc(security=[{"bearerAuth": []}])
    @blp.arguments(FreeIn)
    @require_auth("system.operate")
    def post(self, data):
        """A query's rows as a file {..., sql, format: csv|xlsx}: at most 100,000 rows, rolled back (R2.57)"""
        data = data or {}
        fmt = "xlsx" if data.get("format") == "xlsx" else "csv"
        body, name, mime = _guard(sqlconsole.export, *_login(data), str(data.get("sql") or ""), fmt)
        _audit({**data, "sql": str(data.get("sql") or "")}, "ok", kind="export", format=fmt)
        return Response(body, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
