"""Connectivity: every connection EA Explorer depends on, made the way the product makes it (owner, 23 Nov 2026: "In
smoke and full tests please build a test api check which tests all connectivity also this should be in heartbeat";
D894).

Health (eax/health.py) asks each service whether it answers. That is not enough: on 23 Nov 2026, in certificate mode,
Documents answered its own page while the API could not sign in to Documents' database, so nothing could use it and
the start-up status said "waiting" for hours (D893). Here each link is used as the product uses it, with the login, the
certificate, the key or the token it uses:

  API -> database, as each login the API uses (eax_app, eax_migrator, eax_report), and each database part it serves
  API -> Documents' database (mayan, its API key) and Documents' API with that key
  API -> Documents' queue (Valkey, its password)
  API -> Keycloak: the service account's token, and the keys that check sign-in tokens
  API -> the library and the drawn views services with their keys (each reads its own database to answer)
  API -> the operations helper with its token; Reports; draw.io; the job queue; the backups folder

Each link: {name, from, to, how, status (up | down | off), detail, ms}. A link whose part is switched off is "off".
All run at once with short time limits. check() runs them now (the signed-in page, the self-test's smoke and full
runs); summary() is the public heartbeat's: the last result kept for CACHE_SECONDS and refreshed in the background, so
the heartbeat never waits for it, and it names no detail (counts only). Rules here (D248); nothing is changed.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from . import httpopen

TIMEOUT = 5
CACHE_SECONDS = 60
NIL = "00000000-0000-0000-0000-000000000000"


def _first(exc: BaseException) -> str:
    return (str(exc).splitlines() or [exc.__class__.__name__])[0][:240] or exc.__class__.__name__


def _link(name: str, to: str, how: str, fn: Callable[[], str | None], part: str = "") -> Callable[[], dict]:
    """A link checked by fn: it returns a short note when the link works, raises when it does not, or returns None when
    its part is switched off."""
    def run() -> dict:
        t0 = time.perf_counter()
        if part:
            from . import services
            if not services.enabled(part):
                return {"name": name, "from": "API", "to": to, "how": how, "status": "off", "detail": "switched off", "ms": 0}
        try:
            note = fn()
            status, detail = ("off", "switched off") if note is None else ("up", note or "works")
        except Exception as exc:  # noqa: BLE001 - said, never raised
            status, detail = "down", _first(exc)
        return {"name": name, "from": "API", "to": to, "how": how, "status": status, "detail": detail,
                "ms": round((time.perf_counter() - t0) * 1000)}
    return run


# ---------------------------------------------------------------- the database
def _login(user_env: str, default_user: str, password_env: str) -> str:
    """Signs in to the repository database as one login (its password in password mode; in certificate mode libpq
    takes the API's certificate from PGSSLCERT, and the password is not used)."""
    import psycopg

    from .config import get_settings
    s = get_settings()
    user = os.environ.get(user_env, default_user)
    pw = os.environ.get(password_env, "")
    q = lambda v: "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"   # noqa: E731 - a conninfo value
    with psycopg.connect(f"host={s.db_host} port={s.db_port} dbname={s.db_name} user={q(user)} password={q(pw)} "
                         f"connect_timeout={TIMEOUT}") as c:
        c.execute("SELECT 1")
    return f"signed in as {user}"


def _app() -> str:
    from sqlalchemy import text

    from .db import get_engine
    with get_engine().connect() as c:
        c.execute(text("SELECT 1"))
    return "signed in as the API's login"


def _part(key: str) -> Callable[[], str]:
    def go() -> str:
        from sqlalchemy import text

        from . import databases
        with databases.engine_for(key).connect() as c:
            c.execute(text("SELECT 1"))
        return "its own database" if databases.setting(databases.BY_KEY[key]) else "in the repository database"
    return go


# ---------------------------------------------------------------- Documents
def _dms_db() -> str:
    from . import mayan
    mayan._db_token()
    return "its API key read as the login mayan"


def _dms_api() -> str:
    from . import mayan
    why = mayan.why_not_up()
    if why:
        raise RuntimeError(why)
    return "answered with its API key"


def _dms_queue() -> str:
    from . import health
    r = health.check_dms_broker()
    if r["status"] == "off":
        return None  # type: ignore[return-value]
    if r["status"] != "up":
        raise RuntimeError(r.get("detail") or r["status"])
    return r.get("detail") or "AUTH and PING answered"


# ---------------------------------------------------------------- Keycloak
def _kc_token() -> str:
    from . import keycloak_admin
    keycloak_admin._token["value"] = None            # a new token, not the one kept
    keycloak_admin._service_token()
    return "the service account's token issued"


def _kc_keys() -> str:
    from .config import get_settings
    with httpopen.urlopen(get_settings().jwks_url, timeout=TIMEOUT) as r:  # noqa: S310 - inside the network
        n = len(__import__("json").loads(r.read() or b"{}").get("keys") or [])
    if not n:
        raise RuntimeError("no signing keys published")
    return f"{n} signing keys read"


# ---------------------------------------------------------------- our own services, with their keys
def _library() -> str | None:
    from . import library_client as lc
    if not lc.service_on():
        return None
    lc.export_project(NIL)                           # a keyed call that reads its database; nothing there, nothing sent
    return "a keyed call answered (its database read)"


def _views() -> str | None:
    from . import views_client as vc
    if not vc.service_on():
        return None
    vc.list_views(NIL)
    return "a keyed call answered (its database read)"


def _ops() -> str:
    url, token = os.environ.get("EAX_OPS_URL", "http://ops:8090").rstrip("/"), os.environ.get("EAX_OPS_TOKEN", "")
    req = urllib.request.Request(f"{url}/alerts", headers={"X-Ops-Token": token, "Accept": "application/json"})
    try:
        with httpopen.urlopen(req, timeout=TIMEOUT):  # noqa: S310 - inside the network
            pass
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"answered {exc.code}" + (": its token was refused" if exc.code in (401, 403) else "")) from exc
    return "answered with its token"


def _from_health(fn_name: str) -> Callable[[], str | None]:
    def go() -> str | None:
        from . import health
        r = getattr(health, fn_name)()
        if r["status"] == "off":
            return None
        if r["status"] == "down":
            raise RuntimeError(r.get("detail") or "down")
        return r.get("detail") or "answering"
    return go


def links() -> list[Callable[[], dict]]:
    """Every link, in the order the page shows them."""
    from . import databases
    out = [
        _link("Database as the API", "Database", "the API's login (eax_app)", _app),
        _link("Database as the migrations", "Database", "the migrations' login (eax_migrator)",
              lambda: _login("EAX_DB_MIGRATOR_USER", "eax_migrator", "EAX_DB_MIGRATOR_PASSWORD")),
        _link("Database as reports", "Database", "the read-only reporting login (eax_report)",
              lambda: _login("EAX_DB_REPORT_USER", "eax_report", "EAX_DB_REPORT_PASSWORD")),
    ]
    for d in [d for d in databases.DATABASES if d.kind == "url"]:      # the API's own parts; the others are the services' below
        out.append(_link(f"Database part: {d.key}", "Database", f"the {d.key} part the API serves", _part(d.key)))
    out += [
        _link("Documents' database", "Documents", "its API key, read as the login mayan", _dms_db, part="documents"),
        _link("Documents", "Documents", "its API with that key", _dms_api, part="documents"),
        _link("Documents' queue", "Document queue", "AUTH and PING with its password", _dms_queue, part="documents"),
        _link("Keycloak service account", "Keycloak", "a token for the API's service account (client credentials)", _kc_token),
        _link("Keycloak signing keys", "Keycloak", "the keys that check every sign-in token", _kc_keys),
        _link("Library service", "Library", "a call with the library key", _library),
        _link("Drawn views service", "Drawn views", "a call with the views key", _views),
        _link("Operations helper", "Operations helper", "a call with its token", _ops),
        _link("Reports", "Reports", "its health", _from_health("check_reports")),
        _link("draw.io", "draw.io", "its page", _from_health("check_drawio")),
        _link("Job queue", "Job runner", "waiting and failed jobs", _from_health("check_jobs")),
        _link("Backups folder", "Backups", "the folder backups are written to", _from_health("check_backup")),
    ]
    return out


def check() -> dict:
    """Every link now, all at once: {status ok | degraded, up, down, off, links, time, duration_ms}."""
    t0 = time.perf_counter()
    fns = links()
    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        found = list(pool.map(lambda f: f(), fns))
    down = [x for x in found if x["status"] == "down"]
    out = {"status": "degraded" if down else "ok", "time": datetime.now(UTC).isoformat(),
           "duration_ms": round((time.perf_counter() - t0) * 1000),
           "up": sum(1 for x in found if x["status"] == "up"), "down": len(down),
           "off": sum(1 for x in found if x["status"] == "off"), "links": found}
    _kept.update(result=out, at=time.monotonic())
    return out


# ---------------------------------------------------------------- the heartbeat's summary, never waited for
_kept: dict = {"result": None, "at": 0.0, "running": False}
_lock = threading.Lock()


def summary() -> dict:
    """For the public heartbeat: the last result's counts (no detail), refreshed in the background when older than
    CACHE_SECONDS. Before the first result: {"status": "checking"}."""
    with _lock:
        stale = not _kept["result"] or time.monotonic() - _kept["at"] > CACHE_SECONDS
        if stale and not _kept["running"]:
            _kept["running"] = True
            threading.Thread(target=_refresh, daemon=True, name="connectivity").start()
    r = _kept["result"]
    if not r:
        return {"status": "checking"}
    return {"status": r["status"], "up": r["up"], "down": r["down"], "off": r["off"], "checked_at": r["time"]}


def _refresh() -> None:
    try:
        check()
    except Exception:  # noqa: BLE001, S110 - the next heartbeat tries again
        pass
    finally:
        _kept["running"] = False
