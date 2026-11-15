"""Alerts (R5.9, D689: in EA Explorer, by webhook and by email; "add email with 1"): Nagios-like checks, our own.

Every minute (the job eax.alerts_run) each check gives a state, OK, WARNING, CRITICAL or UNKNOWN, as Nagios does:
  service:<name>   each service's health (eax/health.py: the API, the database, the job runner, Keycloak, Reports,
                   Documents, the backups' age, ...): down is CRITICAL, a warning WARNING
  disk             the fullest disk the installation uses (its data folders, Docker's): % used
  memory           the container nearest its memory limit: % of the limit
  certificate      days until the front door's certificate ends
  db_connections   the database's connections, % of its limit
  db_long_tx       the longest open transaction (or session idle in one), minutes
  web_errors       server errors (5xx) in the web log in the last hour
  self_test        the last finished self-test: failed is WARNING
  db_maintenance   the database maintenance check's findings (R5.12)
  custom:<key>     checks a person adds: an address answers (url) within a time, or a read-only query (sql) returns a
                   number under a level
Each check's warning and critical levels are set on System Admin > Alerts. A state counts only once it has held for
`hold` checks in a row (2 by default: no alert for one slow answer); flapping (4 or more changes in the last 10 checks)
is said once and not repeated until it settles.

An alert is raised when a check holds WARNING or CRITICAL: a notification for the IT Admins and Super Admins
(category system, so the webhooks hear it too) and an email to the addresses set (EAX_SMTP_*, through the
organisation's own mail server; email is sent for alerts only, D689). It is repeated every `repeat` minutes (60) until
acknowledged, escalated to the Super Admins (and the email again) when not acknowledged within 30 minutes, and its
recovery is said. Acknowledged (with a note), it stops repeating; silenced (a check or all of them, for a time) or in a
downtime, nothing is sent; EA Explorer's own maintenance (a restore, an update) and a self-test running are downtimes by
themselves. The history is kept 90 days. Tables only in the database (D248): core.alert_*, migration 0080.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import text

OK, WARNING, CRITICAL, UNKNOWN = "OK", "WARNING", "CRITICAL", "UNKNOWN"
RANK = {OK: 0, UNKNOWN: 1, WARNING: 2, CRITICAL: 3}
LINK = "#/admin/alerts"
HOLD, REPEAT_MIN, ESCALATE_MIN, KEEP_DAYS = 2, 60, 30, 90
FLAP_CHANGES, FLAP_WINDOW = 4, 10

# key: (what it measures, unit, warning, critical, higher is worse)
DEFAULTS: dict[str, tuple[str, str, float, float, bool]] = {
    "disk": ("The fullest disk the installation uses", "% used", 80, 90, True),
    "memory": ("The container nearest its memory limit", "% of its limit", 85, 95, True),
    "certificate": ("Days until the front door's certificate ends", "days", 21, 7, False),
    "db_connections": ("The database's connections", "% of its limit", 80, 90, True),
    "db_long_tx": ("The longest open transaction", "minutes", 30, 120, True),
    "web_errors": ("Server errors (5xx) in the last hour", "calls", 10, 50, True),
    "self_test": ("The last finished self-test", "checks failed", 1, 1000000, True),
    "db_maintenance": ("Database maintenance findings (R5.12)", "findings", 1, 5, True),
    "security": ("High or critical security findings the gate fails on (R5.17)", "findings", 1, 1000000, True),
}


# ---------------------------------------------------------------- states from values
def state_of(value: float | None, warning: float, critical: float, higher_is_worse: bool = True) -> str:
    """A check's state from its value: UNKNOWN when it could not be measured, else OK, WARNING or CRITICAL by its two
    levels (lower is worse for the certificate's days)."""
    if value is None:
        return UNKNOWN
    if higher_is_worse:
        return CRITICAL if value >= critical else WARNING if value >= warning else OK
    return CRITICAL if value <= critical else WARNING if value <= warning else OK


def step(row: dict | None, seen: str, hold: int = HOLD) -> dict:
    """The next state of one check from what it saw now (pure, so it is tested alone): the state shown changes only
    once `seen` has held `hold` times in a row; the last changes are kept to notice flapping."""
    row = dict(row or {"state": OK, "pending": OK, "streak": 0, "changes": []})
    streak = row["streak"] + 1 if seen == row.get("pending") else 1
    row.update(pending=seen, streak=streak)
    changed = False
    if seen != row["state"] and streak >= hold:
        row["state"], changed = seen, True
    row["changes"] = ((row.get("changes") or []) + [1 if changed else 0])[-FLAP_WINDOW:]
    row["changed"] = changed
    row["flapping"] = sum(row["changes"]) >= FLAP_CHANGES
    return row


# ---------------------------------------------------------------- the checks
def _ops(path: str, timeout: int = 20) -> dict:
    url, token = os.environ.get("EAX_OPS_URL", "http://ops:8090"), os.environ.get("EAX_OPS_TOKEN", "")
    req = urllib.request.Request(f"{url}{path}", headers={"X-Ops-Token": token})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def measure_disk() -> tuple[float | None, str]:
    """The fullest file system the installation uses, in per cent used, as the operations helper sees it."""
    fs = _ops("/stats").get("filesystems") or []
    worst = max(fs, key=lambda f: float(f.get("used_percent") or f.get("percent") or 0), default=None)
    if not worst:
        return None, "no file system seen"
    pct = float(worst.get("used_percent") or worst.get("percent") or 0)
    return pct, f"{worst.get('name') or worst.get('mount') or worst.get('path')}: {pct:.0f}% used"


def measure_memory() -> tuple[float | None, str]:
    """The container nearest its memory limit, in per cent of that limit."""
    rows = _ops("/stats").get("containers") or []
    best, name = None, ""
    for c in rows:
        p = c.get("mem_percent")
        if p is not None and (best is None or float(p) > best):
            best, name = float(p), c.get("service") or c.get("name") or ""
    return best, (f"{name}: {best:.0f}% of its memory limit" if best is not None else "no container measured")


def measure_certificate() -> tuple[float | None, str]:
    """Days until the front door's certificate ends, read from the certificate the proxy presents."""
    from cryptography import x509
    host = os.environ.get("EAX_PROXY_HOST", "proxy")
    pem = ssl.get_server_certificate((host, 443), timeout=10)
    cert = x509.load_pem_x509_certificate(pem.encode())
    end = cert.not_valid_after_utc
    days = (end - datetime.now(UTC)).total_seconds() / 86400
    return round(days, 1), f"ends {end:%Y-%m-%d} ({days:.0f} days)"


def measure_db(conn) -> dict[str, tuple[float | None, str]]:
    """The database's connections (per cent of its limit) and its longest open transaction (minutes), both in one look."""
    used, limit = conn.execute(text("SELECT (SELECT count(*) FROM pg_stat_activity), current_setting('max_connections')::int")).one()
    longest = conn.execute(text("""SELECT coalesce(max(extract(epoch FROM now() - xact_start)) / 60, 0) FROM pg_stat_activity
                                    WHERE xact_start IS NOT NULL AND pid <> pg_backend_pid()""")).scalar()
    pct = 100.0 * used / max(1, limit)
    return {"db_connections": (round(pct, 1), f"{used} of {limit} connections"),
            "db_long_tx": (round(float(longest), 1), f"the longest transaction has been open {float(longest):.0f} minutes")}


def measure_web_errors() -> tuple[float | None, str]:
    """Server errors (5xx) in the web log over the last hour."""
    now = datetime.now(UTC)
    since = (now - timedelta(hours=1)).strftime("%H:%M")
    out = _ops(f"/logs/web?day={now:%Y-%m-%d}&status=5xx&since={since}")
    return float(out.get("total") or 0), f"{out.get('total') or 0} server errors in the last hour"


def measure_self_test() -> tuple[float | None, str]:
    """How many checks failed in the newest finished self-test."""
    from .testing import store
    with store.engine().connect() as tconn:
        runs = [r for r in store.runs(tconn, 5) if r.get("status") in ("passed", "failed")]
    if not runs:
        return None, "no finished self-test yet"
    r = runs[0]
    failed = int((r.get("counts") or {}).get("failed") or r.get("failed") or 0)
    return float(failed), f"run {r.get('id')}: {r.get('status')} ({failed} failed)"


def measure_security() -> tuple[float | None, str]:
    """The newest security gate (R5.17): how many high or critical findings it failed on (0 when it passed)."""
    import re as _re

    from .testing import security_gate, store
    with store.engine().connect() as tconn:
        row = tconn.execute(text("""SELECT run_id, outcome, detail FROM tests.test_results WHERE name = :n
                                     ORDER BY id DESC LIMIT 1"""), {"n": security_gate.GATE}).mappings().first()
    if not row:
        return None, "no security gate yet (the weekly security test makes one)"
    if row["outcome"] != "failed":
        return 0.0, f"run {row['run_id']}: {row['outcome']}"
    m = _re.match(r"(\d+)", row["detail"] or "")
    return float(m.group(1) if m else 1), f"run {row['run_id']}: {(row['detail'] or '')[:200]}"


def measure_db_maintenance(conn) -> tuple[float | None, str]:
    """How many warning or critical findings the last database check had (R5.12)."""
    from . import dbmaint
    last = dbmaint.last_check(conn)
    if not last:
        return None, "no database check yet"
    n = len([f for f in last.get("findings") or [] if f.get("level") in ("warning", "critical")])
    return float(n), f"{n} findings at the check of {last.get('at')}"


def measure_custom(conn, c: dict) -> tuple[float | None, str]:
    """A custom check's value: a URL's answer time in milliseconds (999999 when it fails), or a SQL query's single
    number."""
    if c["kind"] == "url":
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(c["target"], timeout=20) as r:
                ms = (time.perf_counter() - started) * 1000
                return (round(ms), f"answered {r.status} in {ms:.0f} ms") if r.status < 400 else (999999, f"answered {r.status}")
        except Exception as exc:  # noqa: BLE001
            return 999999, f"did not answer: {str(exc)[:120]}"
    from .db import get_engine
    with get_engine().connect() as ro:          # its own connection, read only, rolled back
        tx = ro.begin()
        try:
            ro.execute(text("SET TRANSACTION READ ONLY"))
            ro.execute(text("SET LOCAL statement_timeout = '20s'"))
            v = ro.execute(text(c["target"])).scalar()
        finally:
            tx.rollback()
    return (float(v) if v is not None else None), f"the query returned {v}"


def config(conn) -> dict[str, dict]:
    """Every built-in check's levels, hold and whether it is on: the defaults with what an admin changed on top."""
    rows = {r["key"]: dict(r) for r in conn.execute(text("SELECT * FROM core.alert_config")).mappings()}
    out = {}
    for k, (what, unit, w, c, hi) in DEFAULTS.items():
        r = rows.get(k, {})
        out[k] = {"key": k, "what": what, "unit": unit,
                  "warning": float(r["warning"]) if r.get("warning") is not None else float(w),
                  "critical": float(r["critical"]) if r.get("critical") is not None else float(c), "higher_is_worse": hi,
                  "enabled": r.get("enabled", True), "hold": int(r.get("hold") or HOLD), "custom": False}
    for r in conn.execute(text("SELECT * FROM core.alert_custom ORDER BY key")).mappings():
        out[f"custom:{r['key']}"] = {"key": f"custom:{r['key']}", "what": r["name"], "unit": "ms" if r["kind"] == "url" else "",
                                     "warning": float(r["warning"]), "critical": float(r["critical"]), "higher_is_worse": True,
                                     "enabled": r["enabled"], "hold": int(r["hold"] or HOLD), "custom": True,
                                     "kind": r["kind"], "target": r["target"]}
    return out


def seen_now(conn, cfg: dict[str, dict]) -> dict[str, dict]:
    """What every check sees now: {key: {state, value, message, what}}."""
    out: dict[str, dict] = {}

    def put(key, value, message):
        c = cfg.get(key)
        if not c or not c["enabled"]:
            return
        out[key] = {"state": state_of(value, c["warning"], c["critical"], c["higher_is_worse"]), "value": value,
                    "message": message, "what": c["what"]}

    from . import health
    try:
        for s in health.check_all()["services"]:
            if s["status"] == "off":
                continue
            st = {"down": CRITICAL, "warning": WARNING, "up": OK}.get(s["status"], UNKNOWN)
            out[f"service:{s['name']}"] = {"state": st, "value": s.get("response_ms"), "message": s.get("detail") or "",
                                           "what": f"{s['name']} ({s.get('kind') or 'service'})"}
    except Exception as exc:  # noqa: BLE001
        out["service:health"] = {"state": UNKNOWN, "value": None, "message": str(exc)[:200], "what": "Service health"}
    measures = [("disk", measure_disk), ("memory", measure_memory), ("certificate", measure_certificate),
                ("web_errors", measure_web_errors), ("self_test", measure_self_test), ("security", measure_security)]
    for key, fn in measures:
        if not cfg.get(key, {}).get("enabled", True):
            continue
        try:
            put(key, *fn())
        except Exception as exc:  # noqa: BLE001 - a check that cannot be made is UNKNOWN, never an error
            put(key, None, f"could not be checked: {str(exc)[:160]}")
    try:
        for key, (v, m) in measure_db(conn).items():
            put(key, v, m)
    except Exception as exc:  # noqa: BLE001
        put("db_connections", None, str(exc)[:160])
    try:
        put("db_maintenance", *measure_db_maintenance(conn))
    except Exception as exc:  # noqa: BLE001
        put("db_maintenance", None, str(exc)[:160])
    for key, c in cfg.items():
        if c.get("custom") and c["enabled"]:
            try:
                put(key, *measure_custom(conn, c))
            except Exception as exc:  # noqa: BLE001
                put(key, None, str(exc)[:160])
    return out


# ---------------------------------------------------------------- silences and downtime
def silenced(conn, key: str, now: datetime | None = None) -> str:
    """Why nothing is sent for a check now ("" when it is sent): a silence, a downtime, maintenance or a self-test."""
    now = now or datetime.now(UTC)
    row = conn.execute(text("""SELECT reason, until FROM core.alert_silences WHERE until > :n AND (check_key = '*' OR check_key = :k)
                                ORDER BY until DESC LIMIT 1"""), {"n": now, "k": key}).mappings().first()
    if row:
        return f"silenced until {row['until']:%Y-%m-%d %H:%M} ({row['reason'] or 'no reason given'})"
    try:
        from . import maintenance
        if maintenance.state():
            return "EA Explorer's own maintenance (a restore or an update)"
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import test_lock
        from .testing import store
        with store.engine().connect() as tconn:
            if test_lock.active(tconn):
                return "a self-test is running"
    except Exception:  # noqa: BLE001
        pass
    return ""


# ---------------------------------------------------------------- telling people
def people(conn, super_only: bool = False) -> list[str]:
    """The Super Admins and IT Admins to tell of an alert (only the Super Admins for an escalation)."""
    roles = "'super-admin' = ANY (roles)" if super_only else "'super-admin' = ANY (roles) OR 'it-admin' = ANY (roles)"
    return [r[0] for r in conn.execute(text(f"SELECT lower(username) FROM core.known_users WHERE {roles}"))]


def email_settings() -> dict:
    """The mail server for alert emails, from the config file's EAX_SMTP_* settings."""
    return {"host": os.environ.get("EAX_SMTP_HOST", ""), "port": int(os.environ.get("EAX_SMTP_PORT") or 587),
            "user": os.environ.get("EAX_SMTP_USER", ""), "password": os.environ.get("EAX_SMTP_PASSWORD", ""),
            "sender": os.environ.get("EAX_SMTP_FROM", "") or "ea-explorer@localhost",
            "security": (os.environ.get("EAX_SMTP_SECURITY") or "starttls").lower()}


def recipients_of(conn, escalated: bool = False) -> list[str]:
    """The email addresses an alert goes to (the setting alerts_email_to, plus alerts_email_escalate for an escalation)."""
    from . import settings as st
    v = st.values(conn)
    raw = v.get("alerts_email_to") or ""
    if escalated:
        raw += "," + (v.get("alerts_email_escalate") or "")
    return sorted({a.strip() for a in raw.replace(";", ",").split(",") if "@" in a})


def send_email(to: list[str], subject: str, body: str, smtp=None) -> str:
    """One email through the organisation's mail server. Returns "" when sent, else why not."""
    s = email_settings()
    if not to:
        return "no address to send to (System Admin > Alerts)"
    if not s["host"]:
        return "no mail server set (EAX_SMTP_HOST in the config file)"
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject[:200], s["sender"], ", ".join(to)
    msg.set_content(body)
    try:
        if smtp is None:
            cls = smtplib.SMTP_SSL if s["security"] == "ssl" else smtplib.SMTP
            smtp = cls(s["host"], s["port"], timeout=20)
            if s["security"] == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if s["user"]:
                smtp.login(s["user"], s["password"])
        smtp.send_message(msg)
        smtp.quit()
        return ""
    except Exception as exc:  # noqa: BLE001
        return f"the mail server refused: {str(exc)[:200]}"


def tell(conn, kind: str, key: str, row: dict, seen: dict, escalated: bool = False) -> None:
    """Tells people of an alert raised, still open, escalated or recovered: a notification, an email when a mail server
    is set, and an audit line."""
    from . import audit, notify
    words = {"raised": "Alert", "reminder": "Still", "escalated": "Not acknowledged", "recovered": "Recovered"}[kind]
    title = f"{words}: {seen.get('what') or key} is {row['state']}" + (f" ({seen.get('message')})" if seen.get("message") else "")
    notify.create(conn, kind=f"alert.{kind}", category="system", title=title[:300], body=str(seen.get("message") or ""),
                  link=LINK, actor="system", recipients=people(conn, super_only=escalated), needs_action=kind != "recovered")
    host = os.environ.get("EAX_HOSTNAME", "EA Explorer")
    why = send_email(recipients_of(conn, escalated), f"[EA Explorer {host}] {title}",
                     f"{title}\n\nCheck: {key}\nState: {row['state']}\nSince: {row.get('since')}\n\n"
                     f"See System Admin > Alerts: https://{host}/{LINK}\n")
    audit.record(conn, actor="system", action=f"alert.{kind}", object_type="alert", object_id=key,
                 details={"state": row["state"], "message": seen.get("message"), "email": why or "sent"})


# ---------------------------------------------------------------- one run
def run(conn, now: datetime | None = None, seen: dict | None = None) -> dict:
    """Every check once: states updated, the history written, people told. Returns what happened."""
    now = now or datetime.now(UTC)
    cfg = config(conn)
    seen = seen if seen is not None else seen_now(conn, cfg)
    rows = {r["check_key"]: dict(r) for r in conn.execute(text("SELECT * FROM core.alert_checks")).mappings()}
    told: list[tuple[str, str]] = []
    for key, s in seen.items():
        prev = rows.get(key)
        row = step({"state": prev["state"], "pending": prev["pending"], "streak": prev["streak"],
                    "changes": prev["changes"] or []} if prev else None, s["state"], cfg.get(key, {}).get("hold", HOLD))
        since = now if row["changed"] or not prev else prev["since"]
        acked_by = None if row["changed"] else (prev or {}).get("acked_by")
        last = None if row["changed"] else (prev or {}).get("last_notified_at")
        escalated = False if row["changed"] else bool((prev or {}).get("escalated"))
        flapped_said = bool((prev or {}).get("flapping")) and row["flapping"]
        if row["changed"]:
            conn.execute(text("INSERT INTO core.alert_history (check_key, state, value, message, at) VALUES (:k, :s, :v, :m, :a)"),
                         {"k": key, "s": row["state"], "v": s.get("value"), "m": str(s.get("message") or "")[:500], "a": now})
        quiet = silenced(conn, key, now)
        if not quiet and not flapped_said:
            bad = row["state"] in (WARNING, CRITICAL)
            if row["changed"] and bad:
                kind = "raised"
            elif row["changed"] and prev and RANK.get(prev["state"], 0) >= 2 and row["state"] == OK:
                kind = "recovered"
            elif bad and not acked_by and last and now - last >= timedelta(minutes=REPEAT_MIN):
                kind = "reminder"
            else:
                kind = ""
            if bad and not acked_by and not escalated and now - since >= timedelta(minutes=ESCALATE_MIN) and not row["changed"]:
                tell(conn, "escalated", key, row | {"since": since}, s, escalated=True)
                escalated = True
                told.append((key, "escalated"))
            if kind:
                tell(conn, kind, key, row | {"since": since}, s)
                last = now
                told.append((key, kind))
        conn.execute(text("""
            INSERT INTO core.alert_checks (check_key, what, state, pending, streak, changes, since, value, message,
                   acked_by, last_notified_at, escalated, flapping, checked_at)
            VALUES (:k, :w, :s, :p, :n, CAST(:c AS jsonb), :since, :v, :m, :ab, :ln, :e, :f, :now)
            ON CONFLICT (check_key) DO UPDATE SET what = EXCLUDED.what, state = EXCLUDED.state, pending = EXCLUDED.pending,
                   streak = EXCLUDED.streak, changes = EXCLUDED.changes, since = EXCLUDED.since, value = EXCLUDED.value,
                   message = EXCLUDED.message, acked_by = EXCLUDED.acked_by,
                   acked_at = CASE WHEN EXCLUDED.acked_by IS NULL THEN NULL ELSE core.alert_checks.acked_at END,
                   ack_note = CASE WHEN EXCLUDED.acked_by IS NULL THEN NULL ELSE core.alert_checks.ack_note END,
                   last_notified_at = EXCLUDED.last_notified_at, escalated = EXCLUDED.escalated,
                   flapping = EXCLUDED.flapping, checked_at = EXCLUDED.checked_at"""),
            {"k": key, "w": s.get("what") or key, "s": row["state"], "p": row["pending"], "n": row["streak"],
             "c": json.dumps(row["changes"]), "since": since, "v": s.get("value"), "m": str(s.get("message") or "")[:500],
             "ab": acked_by, "ln": last, "e": escalated, "f": row["flapping"], "now": now})
    conn.execute(text("DELETE FROM core.alert_history WHERE at < :c"), {"c": now - timedelta(days=KEEP_DAYS)})
    conn.execute(text("DELETE FROM core.alert_silences WHERE until < :c"), {"c": now - timedelta(days=KEEP_DAYS)})
    return {"checks": len(seen), "told": told}


# ---------------------------------------------------------------- the page and MCP
def overview(conn) -> dict:
    """Everything System Admin > Alerts shows: every check (the open ones first), the counts, the silences, the levels
    and the email settings without the password."""
    rows = [dict(r) for r in conn.execute(text("SELECT * FROM core.alert_checks ORDER BY check_key")).mappings()]
    rows.sort(key=lambda r: (-RANK.get(r["state"], 0), r["check_key"]))
    silences = [dict(r) for r in conn.execute(text("SELECT * FROM core.alert_silences WHERE until > now() ORDER BY until")).mappings()]
    open_ = [r for r in rows if r["state"] in (WARNING, CRITICAL)]
    return {"checks": rows, "open": len(open_), "critical": sum(1 for r in open_ if r["state"] == CRITICAL),
            "unacknowledged": sum(1 for r in open_ if not r["acked_by"]), "silences": silences, "config": list(config(conn).values()),
            "email": {k: v for k, v in email_settings().items() if k != "password"} | {"to": recipients_of(conn)}}


def acknowledge(conn, key: str, by: str, note: str) -> dict:
    """Marks an open alert as seen by someone, with a note; reminders stop until it changes."""
    n = conn.execute(text("""UPDATE core.alert_checks SET acked_by = :b, acked_at = now(), ack_note = :n
                              WHERE check_key = :k AND state IN ('WARNING', 'CRITICAL')"""), {"k": key, "b": by, "n": note[:500]}).rowcount
    if not n:
        raise ValueError(f"No open alert {key}.")
    return {"check": key, "acknowledged_by": by}


def silence(conn, key: str, minutes: int, by: str, reason: str) -> dict:
    """Silences one check (or every check, key empty) for 1 minute to 14 days, with a reason."""
    if not 1 <= int(minutes) <= 60 * 24 * 14:
        raise ValueError("Silence for 1 minute to 14 days.")
    until = datetime.now(UTC) + timedelta(minutes=int(minutes))
    conn.execute(text("INSERT INTO core.alert_silences (check_key, until, reason, created_by) VALUES (:k, :u, :r, :b)"),
                 {"k": key or "*", "u": until, "r": reason[:300], "b": by})
    return {"check": key or "*", "until": until.isoformat()}


def set_config(conn, key: str, body: dict) -> dict:
    """Changes a check's warning and critical levels, hold and whether it is on (a built-in check or a custom one)."""
    if key.startswith("custom:"):
        k = key.split(":", 1)[1]
        conn.execute(text("""UPDATE core.alert_custom SET warning = coalesce(:w, warning), critical = coalesce(:c, critical),
                                 enabled = coalesce(:e, enabled), hold = coalesce(:h, hold) WHERE key = :k"""),
                     {"k": k, "w": body.get("warning"), "c": body.get("critical"), "e": body.get("enabled"), "h": body.get("hold")})
    elif key in DEFAULTS:
        conn.execute(text("""INSERT INTO core.alert_config (key, warning, critical, enabled, hold) VALUES (:k, :w, :c, coalesce(:e, true), :h)
                             ON CONFLICT (key) DO UPDATE SET warning = coalesce(EXCLUDED.warning, core.alert_config.warning),
                                 critical = coalesce(EXCLUDED.critical, core.alert_config.critical),
                                 enabled = EXCLUDED.enabled, hold = coalesce(EXCLUDED.hold, core.alert_config.hold)"""),
                     {"k": key, "w": body.get("warning"), "c": body.get("critical"), "e": body.get("enabled"), "h": body.get("hold")})
    else:
        raise ValueError(f"No check {key}.")
    return config(conn)[key]


def add_custom(conn, body: dict, by: str) -> dict:
    """Adds a custom check: a URL that must answer, or a SQL query returning one number, with its levels."""
    import re
    key = re.sub(r"[^a-z0-9_-]", "-", str(body.get("key") or "").lower())[:40].strip("-")
    kind = body.get("kind")
    if not key or kind not in ("url", "sql"):
        raise ValueError("A key (letters, digits, -) and a kind: url or sql.")
    target = str(body.get("target") or "").strip()
    if kind == "url" and not target.startswith(("http://", "https://")):
        raise ValueError("A url check needs an address starting with http:// or https://.")
    if kind == "sql" and not re.match(r"(?is)^\s*select\b", target):
        raise ValueError("A sql check is one SELECT that returns a number.")
    conn.execute(text("""INSERT INTO core.alert_custom (key, name, kind, target, warning, critical, created_by)
                         VALUES (:k, :n, :t, :g, :w, :c, :b)"""),
                 {"k": key, "n": str(body.get("name") or key)[:120], "t": kind, "g": target[:2000],
                  "w": float(body.get("warning") or 0), "c": float(body.get("critical") or 0), "b": by})
    return config(conn)[f"custom:{key}"]


def history_csv(conn, days: int = 90) -> str:
    """The alerts' history over the last `days` days as CSV: when, which check, its state, value and message."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["at", "check", "state", "value", "message"])
    for r in conn.execute(text("SELECT at, check_key, state, value, message FROM core.alert_history WHERE at > now() - make_interval(days => :d) "
                               "ORDER BY at DESC"), {"d": int(days)}):
        w.writerow([r[0].isoformat(), r[1], r[2], r[3], r[4]])
    return buf.getvalue()
