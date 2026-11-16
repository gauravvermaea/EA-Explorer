"""Enterprise discovery (R5.5): discovery projects, their sources, and the runs the people's own AI makes through MCP.

The owner's design (15 Nov 2026, 20:11 to 20:28) leads: "EA explorer will only be source and sink of information. Let
MCP and LLm run this one". So EA Explorer keeps the configuration and takes back what the AI found; it never signs in
to a source at run time, never reads, extracts or transcribes anything, holds no AI key and runs nothing on a timer:

  a discovery project   a name, a target model (a child to review first, or the main model), the sources it covers,
                        the defaults of a run (only what is new or everything; mark or delete what is gone) and a
                        schedule that only marks when a run is due (the AI client's own scheduled task asks
                        `discovery projects due` and runs them; a run past its time shows as overdue)
  a source              its kind, where it is, what to include, whether attachments are read, and how it signs in:
                        a sign-in is typed to Test the link, used once, then forgotten (only the method is kept)
  a run                 started by the AI (its own MCP sign-in), "AI agent on behalf of" the person who set the project
                        up; the target model is tagged first and again at the end, so comparing the two tags shows
                        what the run changed, the metamodel first; the AI adds content with the usual tools, then says
                        where each element was found (Found in), what may be the same as an element already there,
                        what it skipped as NOT FOR AI USE (titles only), what is gone, and where each source got to

Who may do what: Discovery Admins and Super Admins set up projects and sources for any model; everyone who may read
a project's target model sees the project and its runs; the AI's writes go through the model's own rules (the AI's
sign-in needs a role that changes the target model's content, and one that commits it, or its commit is asked for).
Rules are here, never in the database (D248).
"""

from __future__ import annotations

import ftplib
import imaplib
import json
import socket
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from . import permissions as perms
from . import repository as repo
from .metamodel_edit import EditError

# every kind of source (owner, 20:26: "All of them in 5.5"): its label, what "where it is" means, and its usual port
KINDS: dict[str, dict] = {
    "mailbox": {"label": "Mailbox", "where": "imaps://mail.example.com/claims-team or a Microsoft 365 address", "port": 993},
    "folder": {"label": "Document folder or share", "where": "\\\\server\\share\\architecture or /mnt/docs", "port": 445},
    "ftp": {"label": "FTP", "where": "ftp://ftp.example.com/exports", "port": 21},
    "sftp": {"label": "SFTP", "where": "sftp://files.example.com/architecture", "port": 22},
    "sharepoint": {"label": "SharePoint", "where": "https://example.sharepoint.com/sites/architecture", "port": 443},
    "git": {"label": "Git repository", "where": "https://git.example.com/org/claims-service.git", "port": 443},
    "wiki": {"label": "Wiki (Confluence and the like)", "where": "https://wiki.example.com/spaces/ARCH", "port": 443},
    "tickets": {"label": "Ticket system or CMDB (Jira, ServiceNow)", "where": "https://example.service-now.com", "port": 443},
    "chat": {"label": "Teams or Slack channel", "where": "https://teams.microsoft.com/l/channel/...", "port": 443},
    "database": {"label": "Database schema (read only)", "where": "postgresql://db.example.com:5432/claims", "port": 5432},
    "cloud-storage": {"label": "Cloud storage (S3, Azure Blob, Google Drive, OneDrive)", "where": "https://bucket.s3.amazonaws.com/docs", "port": 443},
    "cloud-account": {"label": "Cloud account (AWS, Azure)", "where": "https://portal.azure.com subscription 1234 or an AWS account id", "port": 443},
    "recordings": {"label": "Recordings (meetings, walkthroughs)", "where": "https://video.example.com/channel/architecture", "port": 443},
}
SIGN_INS = {"none": "None (open, or reached by the AI's own access)", "key": "Key or token", "basic": "User name and password",
            "certificate": "Client certificate", "sso": "Single sign-on (OAuth, Microsoft 365): a token"}
SCHEDULES = ("none", "daily", "weekly", "monthly")
READ_MODES = {"new": "only what is new or changed since the last run", "all": "everything again"}
GONE_MODES = {"mark": "mark it as not found (since this run)", "delete": "delete it"}
NOT_FOR_AI = "NOT FOR AI USE OR AUTOMATED PROCESSING"
OVERDUE_AFTER = timedelta(hours=2)       # a due run not started within this is overdue
STALE_RUN = timedelta(hours=12)          # a run left running this long is abandoned when the next starts
TEST_TIMEOUT = 10
MAX_ROWS = 1000


def _rows(conn, sql: str, **p) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), p)]


def _one(conn, sql: str, **p) -> dict | None:
    r = conn.execute(text(sql), p).first()
    return dict(r._mapping) if r else None


def may_manage(user) -> bool:
    """Discovery Admins and Super Admins set up discovery projects and their sources, for any model."""
    return perms.allowed(getattr(user, "roles", ()) or (), "discovery.manage")


def _must_manage(user) -> None:
    if not may_manage(user):
        raise EditError("Setting up discovery needs the Discovery Admin role (or Super Admin). A User Admin gives it "
                        "(eax-discovery-admin in Keycloak).", 403)


# ---------------------------------------------------------------- the schedule: a marker of when a run is due
def _hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = (int(x) for x in str(value or "02:00").split(":")[:2])
    except ValueError:
        raise EditError("The time is HH:MM, for example 02:00.", 400) from None
    if not (0 <= h < 24 and 0 <= m < 60):
        raise EditError("The time is HH:MM, for example 02:00.", 400)
    return h, m


def next_due(schedule: str, day: int, at: str, after: datetime) -> datetime | None:
    """When the next run is due after `after` (pure): every day at a time, every week on a weekday (1 Monday to 7
    Sunday), or every month on a day (1 to 28); none without a schedule."""
    if schedule not in SCHEDULES:
        raise EditError(f"The schedule is one of {', '.join(SCHEDULES)}.", 400)
    if schedule == "none":
        return None
    h, m = _hhmm(at)
    base = after.astimezone(UTC)
    cand = base.replace(hour=h, minute=m, second=0, microsecond=0)
    if schedule == "daily":
        return cand if cand > base else cand + timedelta(days=1)
    if schedule == "weekly":
        if not 1 <= int(day) <= 7:
            raise EditError("A weekly run is on a day from 1 (Monday) to 7 (Sunday).", 400)
        cand += timedelta(days=(int(day) - 1 - cand.weekday()) % 7)
        return cand if cand > base else cand + timedelta(days=7)
    if not 1 <= int(day) <= 28:
        raise EditError("A monthly run is on a day from 1 to 28.", 400)
    cand = cand.replace(day=int(day))
    if cand > base:
        return cand
    y, mo = (cand.year + 1, 1) if cand.month == 12 else (cand.year, cand.month + 1)
    return cand.replace(year=y, month=mo)


def due_state(next_at: datetime | None, running: bool, now: datetime) -> str:
    """'' (not due), 'due', 'overdue' (due and not started within two hours) or 'running' (pure)."""
    if running:
        return "running"
    if next_at is None or next_at > now:
        return ""
    return "overdue" if now - next_at > OVERDUE_AFTER else "due"


def schedule_text(p: dict) -> str:
    """The schedule in words."""
    s = p.get("schedule") or "none"
    if s == "none":
        return "No schedule: runs when someone asks their AI"
    at = p.get("schedule_time") or "02:00"
    if s == "daily":
        return f"Every day at {at}"
    if s == "weekly":
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return f"Every {days[int(p.get('schedule_day') or 1) - 1]} at {at}"
    return f"Every month on day {int(p.get('schedule_day') or 1)} at {at}"


# ---------------------------------------------------------------- projects
def _visible(conn, user, p: dict) -> bool:
    if may_manage(user) or (p.get("set_up_by") or "").lower() == (getattr(user, "username", "") or "").lower():
        return True
    return bool(conn.execute(text("SELECT 1 FROM core.models WHERE guid = :g"), {"g": str(p["target_model"])}).first())


def _project_row(conn, ref: Any) -> dict:
    g = repo._as_guid(ref)
    p = _one(conn, "SELECT * FROM core.discovery_projects WHERE guid = :g", g=str(g)) if g else \
        _one(conn, "SELECT * FROM core.discovery_projects WHERE lower(name) = lower(:n)", n=str(ref or "").strip())
    if not p:
        raise EditError(f"No discovery project {ref!r}.", 404)
    return p


def _model_name(conn, guid: Any) -> str:
    r = _one(conn, "SELECT name FROM core.models WHERE guid = :g", g=str(guid))
    return r["name"] if r else "(a model you may not read, or one deleted)"


def _running(conn, pid: int) -> dict | None:
    return _one(conn, "SELECT * FROM core.discovery_runs WHERE project_id = :p AND status = 'running' ORDER BY number DESC LIMIT 1", p=pid)


def _out(conn, user, p: dict, now: datetime) -> dict:
    last = _one(conn, "SELECT * FROM core.discovery_runs WHERE project_id = :p ORDER BY number DESC LIMIT 1", p=p["id"])
    n = conn.execute(text("SELECT count(*) FROM core.discovery_resources WHERE project_id = :p"), {"p": p["id"]}).scalar()
    return {"id": str(p["guid"]), "name": p["name"], "purpose": p["purpose"],
            "target_model": {"id": str(p["target_model"]), "name": _model_name(conn, p["target_model"])},
            "set_up_by": p["set_up_by"], "read_default": p["read_default"], "gone_default": p["gone_default"],
            "schedule": p["schedule"], "schedule_day": p["schedule_day"], "schedule_time": p["schedule_time"],
            "schedule_text": schedule_text(p), "next_due_at": p["next_due_at"],
            "due": due_state(p["next_due_at"], bool(last and last["status"] == "running"), now),
            "resources": int(n or 0), "may_edit": may_manage(user),
            "last_run": _run_out(last) if last else None}


def listing(conn, user, now: datetime | None = None) -> dict:
    """The discovery projects you may see, with what a source and a schedule may be."""
    now = now or datetime.now(UTC)
    rows = _rows(conn, "SELECT * FROM core.discovery_projects ORDER BY lower(name)")
    return {"projects": [_out(conn, user, p, now) for p in rows if _visible(conn, user, p)],
            "may_edit": may_manage(user), "kinds": [{"code": k, **v} for k, v in KINDS.items()],
            "sign_ins": [{"code": k, "label": v} for k, v in SIGN_INS.items()],
            "read_modes": READ_MODES, "gone_modes": GONE_MODES, "schedules": list(SCHEDULES)}


def detail(conn, user, ref: Any, now: datetime | None = None) -> dict:
    """One discovery project: its setup, its sources and its runs (newest first)."""
    now = now or datetime.now(UTC)
    p = _project_row(conn, ref)
    if not _visible(conn, user, p):
        raise EditError(f"No discovery project {ref!r}.", 404)
    out = _out(conn, user, p, now)
    out["sources"] = [_resource_out(r) for r in
                      _rows(conn, "SELECT * FROM core.discovery_resources WHERE project_id = :p ORDER BY lower(name)", p=p["id"])]
    out["runs"] = [_run_out(r) for r in
                   _rows(conn, "SELECT * FROM core.discovery_runs WHERE project_id = :p ORDER BY number DESC LIMIT 50", p=p["id"])]
    return out


def target_refused(m: dict) -> str:
    """Why a model may not be a discovery project's target ("" when it may): only a live working model, never a
    library model or a root metamodel, nor one frozen, archived, read-only or locked (owner, 16 Nov 2026, 13:58)."""
    if m.get("kind") == "template":
        return f"{m['name']} is a root metamodel: it holds no content. Choose a working model, or make one with New model."
    if m.get("kind") != "project":
        return f"{m['name']} is a library model, read only: choose a working model, or make one with New model."
    if m.get("frozen_at") or (m.get("lifecycle") or "active") != "active":
        return f"{m['name']} is frozen or archived: choose a working model, or make one with New model."
    if m.get("is_locked") or (m.get("lock_level") or "none") != "none":
        return f"{m['name']} is locked or read only: choose a working model, or make one with New model."
    return ""


def _clean_project(conn, data: dict, old: dict | None) -> dict:
    d = {**(old or {}), **{k: v for k, v in (data or {}).items() if v is not None}}
    name = str(d.get("name") or "").strip()
    if not name:
        raise EditError("Give the discovery project a name.", 400)
    if len(name) > 200:
        raise EditError("The name is at most 200 characters.", 400)
    target = d.get("target_model")
    if isinstance(target, dict):
        target = target.get("id")
    if not target:
        raise EditError("Choose the target model the AI commits into.", 400)
    m = repo.get_model(conn, target)
    if not old or str(target) != str(old.get("target_model")):     # a project already set up keeps its target
        why = target_refused(m)
        if why:
            raise EditError(why, 400)
    if d.get("read_default", "new") not in READ_MODES or d.get("gone_default", "mark") not in GONE_MODES:
        raise EditError("Read 'new' or 'all'; what is gone is 'mark' or 'delete'.", 400)
    schedule = d.get("schedule") or "none"
    day, at = int(d.get("schedule_day") or 1), str(d.get("schedule_time") or "02:00")
    next_due(schedule, day, at, datetime.now(UTC))       # checks the schedule
    return {"name": name, "purpose": str(d.get("purpose") or ""), "target_model": str(m["id"]),
            "read_default": d.get("read_default") or "new", "gone_default": d.get("gone_default") or "mark",
            "schedule": schedule, "schedule_day": day, "schedule_time": "{:02d}:{:02d}".format(*_hhmm(at))}


def create(conn, user, data: dict, now: datetime | None = None) -> dict:
    """A new discovery project (Discovery Admins and Super Admins), set up on your behalf."""
    _must_manage(user)
    now = now or datetime.now(UTC)
    d = _clean_project(conn, data, None)
    if _one(conn, "SELECT 1 AS x FROM core.discovery_projects WHERE lower(name) = lower(:n)", n=d["name"]):
        raise EditError(f"There is already a discovery project called {d['name']!r}.", 409)
    p = _one(conn, """INSERT INTO core.discovery_projects (name, purpose, target_model, set_up_by, read_default, gone_default,
                                                           schedule, schedule_day, schedule_time, next_due_at, updated_by)
                      VALUES (:name, :purpose, :target_model, :u, :read_default, :gone_default, :schedule, :schedule_day,
                              :schedule_time, :nd, :u) RETURNING *""",
              **d, u=user.username, nd=next_due(d["schedule"], d["schedule_day"], d["schedule_time"], now))
    return {**_out(conn, user, p, now), "message": f"Discovery project {d['name']} set up."}


def update(conn, user, ref: Any, data: dict, now: datetime | None = None) -> dict:
    """Change a discovery project's setup; a new schedule sets when the next run is due."""
    _must_manage(user)
    now = now or datetime.now(UTC)
    p = _project_row(conn, ref)
    d = _clean_project(conn, data, {k: p[k] for k in ("name", "purpose", "read_default", "gone_default", "schedule",
                                                      "schedule_day", "schedule_time")} | {"target_model": str(p["target_model"])})
    if d["name"].lower() != p["name"].lower() and _one(conn, "SELECT 1 AS x FROM core.discovery_projects WHERE lower(name) = lower(:n)", n=d["name"]):
        raise EditError(f"There is already a discovery project called {d['name']!r}.", 409)
    moved = (d["schedule"], d["schedule_day"], d["schedule_time"]) != (p["schedule"], p["schedule_day"], p["schedule_time"])
    nd = next_due(d["schedule"], d["schedule_day"], d["schedule_time"], now) if moved else p["next_due_at"]
    if d["schedule"] == "none":
        nd = None
    p = _one(conn, """UPDATE core.discovery_projects SET name = :name, purpose = :purpose, target_model = :target_model,
                             read_default = :read_default, gone_default = :gone_default, schedule = :schedule,
                             schedule_day = :schedule_day, schedule_time = :schedule_time, next_due_at = :nd,
                             updated_at = now(), updated_by = :u WHERE id = :id RETURNING *""",
              **d, nd=nd, u=user.username, id=p["id"])
    return {**_out(conn, user, p, now), "message": "Saved."}


def delete(conn, user, ref: Any) -> dict:
    """Delete a discovery project with its sources and runs (what the runs added stays in the model)."""
    _must_manage(user)
    p = _project_row(conn, ref)
    if _running(conn, p["id"]):
        raise EditError("A run of this project is under way: wait for it to finish.", 409)
    conn.execute(text("DELETE FROM core.discovery_projects WHERE id = :i"), {"i": p["id"]})
    return {"message": f"Discovery project {p['name']} deleted. What its runs added stays in the model (with Found in)."}


# ---------------------------------------------------------------- sources
def _resource_out(r: dict) -> dict:
    return {"id": r["id"], "kind": r["kind"], "kind_label": KINDS.get(r["kind"], {}).get("label", r["kind"]),
            "name": r["name"], "location": r["location"], "include": r["include"], "attachments": r["attachments"],
            "sign_in": r["sign_in"], "enabled": r["enabled"], "tested_at": r["tested_at"], "test_ok": r["test_ok"],
            "test_note": r["test_note"], "position": r["position"], "position_at": r["position_at"]}


def _clean_resource(data: dict, old: dict | None) -> dict:
    d = {**(old or {}), **{k: v for k, v in (data or {}).items() if v is not None}}
    if d.get("kind") not in KINDS:
        raise EditError(f"The kind of source is one of: {', '.join(KINDS)}.", 400)
    if not str(d.get("name") or "").strip():
        raise EditError("Give the source a name.", 400)
    if not str(d.get("location") or "").strip():
        raise EditError(f"Say where it is, for example {KINDS[d['kind']]['where']}.", 400)
    if d.get("sign_in", "none") not in SIGN_INS:
        raise EditError(f"Sign-in is one of: {', '.join(SIGN_INS)}.", 400)
    return {"kind": d["kind"], "name": str(d["name"]).strip()[:200], "location": str(d["location"]).strip()[:1000],
            "include": str(d.get("include") or "")[:2000], "attachments": bool(d.get("attachments", True)),
            "sign_in": d.get("sign_in") or "none", "enabled": bool(d.get("enabled", True))}


def add_resource(conn, user, ref: Any, data: dict) -> dict:
    """Add a source to a discovery project. Nothing secret is kept: only how it signs in."""
    _must_manage(user)
    p = _project_row(conn, ref)
    d = _clean_resource(data, None)
    r = _one(conn, """INSERT INTO core.discovery_resources (project_id, kind, name, location, include, attachments, sign_in,
                                                            enabled, created_by)
                      VALUES (:p, :kind, :name, :location, :include, :attachments, :sign_in, :enabled, :u) RETURNING *""",
              p=p["id"], u=user.username, **d)
    return {**_resource_out(r), "message": f"Source {d['name']} added."}


def _resource_row(conn, p: dict, rid: Any) -> dict:
    r = _one(conn, "SELECT * FROM core.discovery_resources WHERE id = :i AND project_id = :p", i=int(rid), p=p["id"])
    if not r:
        raise EditError(f"No source {rid} in {p['name']}.", 404)
    return r


def update_resource(conn, user, ref: Any, rid: Any, data: dict) -> dict:
    """Change a source; where the last run got to is kept unless reset (reset_position: true)."""
    _must_manage(user)
    p = _project_row(conn, ref)
    r = _resource_row(conn, p, rid)
    d = _clean_resource(data, {k: r[k] for k in ("kind", "name", "location", "include", "attachments", "sign_in", "enabled")})
    r = _one(conn, f"""UPDATE core.discovery_resources SET kind = :kind, name = :name, location = :location, include = :include,
                              attachments = :attachments, sign_in = :sign_in, enabled = :enabled
                              {", position = '', position_at = NULL" if (data or {}).get("reset_position") else ""}
                        WHERE id = :i RETURNING *""", i=r["id"], **d)
    return {**_resource_out(r), "message": "Saved."}


def remove_resource(conn, user, ref: Any, rid: Any) -> dict:
    """Take a source out of a discovery project (Found in keeps its name)."""
    _must_manage(user)
    p = _project_row(conn, ref)
    r = _resource_row(conn, p, rid)
    conn.execute(text("DELETE FROM core.discovery_resources WHERE id = :i"), {"i": r["id"]})
    return {"message": f"Source {r['name']} removed."}


# ---------------------------------------------------------------- Test the link: the sign-in used once, then forgotten
def _host_port(location: str, default_port: int) -> tuple[str, int]:
    loc = location.strip()
    if loc.startswith("\\\\"):
        return loc[2:].split("\\")[0], default_port
    u = urllib.parse.urlsplit(loc if "://" in loc else f"x://{loc}")
    if not u.hostname:
        raise EditError("Say where it is with a host name, for example https://host/path.", 400)
    return u.hostname, u.port or default_port


def _http(url: str, sign_in: str, secret: dict) -> tuple[bool, str]:
    headers = {"User-Agent": "EA-Explorer-discovery-test"}
    ctx = ssl.create_default_context()
    files = []
    try:
        if sign_in in ("key", "sso") and secret.get("token"):
            headers["Authorization"] = f"Bearer {secret['token']}"
        if sign_in == "basic" and secret.get("username"):
            import base64
            pair = f"{secret['username']}:{secret.get('password') or ''}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(pair).decode()
        if sign_in == "certificate" and secret.get("certificate"):
            for part in ("certificate", "private_key"):
                f = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=True)  # noqa: SIM115 - closed below
                f.write(secret.get(part) or "")
                f.flush()
                files.append(f)
            ctx.load_cert_chain(files[0].name, files[1].name if secret.get("private_key") else None)
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=TEST_TIMEOUT, context=ctx) as resp:  # noqa: S310 - a Discovery Admin's own test
                return True, f"It answered ({resp.status})."
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                return False, f"It answered but refused the sign-in ({exc.code}): check the {SIGN_INS[sign_in].lower()}."
            if exc.code < 500:
                return True, f"It answered ({exc.code}); the address may need a path the AI will use."
            return False, f"It answered with a server error ({exc.code})."
    finally:
        for f in files:
            f.close()


def test_link(user, kind: str, location: str, sign_in: str = "none", secret: dict | None = None) -> dict:
    """Whether a source answers, signing in with what was typed. The sign-in is used once and never kept or logged;
    at run time the AI client brings its own access (owner, 20:28: "Test, then forget")."""
    _must_manage(user)
    if kind not in KINDS:
        raise EditError(f"The kind of source is one of: {', '.join(KINDS)}.", 400)
    if sign_in not in SIGN_INS:
        raise EditError(f"Sign-in is one of: {', '.join(SIGN_INS)}.", 400)
    secret = dict(secret or {})
    loc = (location or "").strip()
    try:
        if loc.lower().startswith(("http://", "https://")):
            ok, note = _http(loc, sign_in, secret)
        elif kind == "ftp" or loc.lower().startswith("ftp://"):
            host, port = _host_port(loc, 21)
            with ftplib.FTP() as f:
                f.connect(host, port, timeout=TEST_TIMEOUT)
                f.login(secret.get("username") or "anonymous", secret.get("password") or "")
                ok, note = True, "It answered and the sign-in was accepted."
        elif kind == "mailbox" and loc.lower().startswith("imaps://") and sign_in == "basic":
            host, port = _host_port(loc, 993)
            m = imaplib.IMAP4_SSL(host, port, timeout=TEST_TIMEOUT)
            try:
                m.login(secret.get("username") or "", secret.get("password") or "")
                ok, note = True, "It answered and the sign-in was accepted."
            finally:
                try:
                    m.logout()
                except Exception:  # noqa: BLE001
                    pass
        else:
            host, port = _host_port(loc, KINDS[kind]["port"])
            with socket.create_connection((host, port), timeout=TEST_TIMEOUT):
                pass
            ok, note = True, (f"{host} answered on port {port}. The sign-in itself is checked by the AI's own tools at run "
                              "time." if sign_in != "none" else f"{host} answered on port {port}.")
    except EditError:
        raise
    except (ftplib.error_perm, imaplib.IMAP4.error) as exc:
        ok, note = False, f"It answered but refused the sign-in: {str(exc)[:200]}"
    except (OSError, ValueError, ssl.SSLError) as exc:
        ok, note = False, f"It did not answer: {str(exc)[:200]}"
    finally:
        secret.clear()                                  # forgotten
    return {"ok": ok, "note": note, "kept": "Nothing but the sign-in method: the details you typed are forgotten."}


def record_test(conn, user, ref: Any, rid: Any, result: dict) -> dict:
    """Keep a source's last test: when, whether it answered, what it said (never the sign-in)."""
    _must_manage(user)
    p = _project_row(conn, ref)
    r = _resource_row(conn, p, rid)
    conn.execute(text("UPDATE core.discovery_resources SET tested_at = now(), test_ok = :o, test_note = :n WHERE id = :i"),
                 {"o": bool(result.get("ok")), "n": str(result.get("note") or "")[:500], "i": r["id"]})
    return result


# ---------------------------------------------------------------- runs, through MCP
def _run_out(r: dict) -> dict:
    return {"id": str(r["guid"]), "number": r["number"], "status": r["status"], "run_by": r["run_by"],
            "who": f"AI agent on behalf of {r['on_behalf_of']}", "on_behalf_of": r["on_behalf_of"], "ai_client": r["ai_client"],
            "read_mode": r["read_mode"], "gone_mode": r["gone_mode"], "start_tag": str(r["start_tag"]) if r["start_tag"] else None,
            "end_tag": str(r["end_tag"]) if r["end_tag"] else None, "summary": r["summary"], "counts": r["counts"] or {},
            "started_at": r["started_at"], "finished_at": r["finished_at"]}


def due(conn, user, now: datetime | None = None) -> list[dict]:
    """The discovery projects you may see whose run is due or overdue now (what an AI client's scheduled task asks)."""
    now = now or datetime.now(UTC)
    out = []
    for p in _rows(conn, "SELECT * FROM core.discovery_projects WHERE next_due_at IS NOT NULL AND next_due_at <= :n ORDER BY next_due_at", n=now):
        if not _visible(conn, user, p):
            continue
        state = due_state(p["next_due_at"], bool(_running(conn, p["id"])), now)
        if state in ("due", "overdue"):
            out.append({"name": p["name"], "id": str(p["guid"]), "due_at": p["next_due_at"], "state": state,
                        "target_model": _model_name(conn, p["target_model"]), "schedule": schedule_text(p)})
    return out


def overdue_count(conn, now: datetime | None = None) -> int:
    """How many discovery projects are overdue (for the alerts)."""
    now = now or datetime.now(UTC)
    n = 0
    for p in _rows(conn, "SELECT id, next_due_at FROM core.discovery_projects WHERE next_due_at IS NOT NULL AND next_due_at < :n", n=now):
        if due_state(p["next_due_at"], bool(_running(conn, p["id"])), now) == "overdue":
            n += 1
    return n


RUN_GUIDE = """How to run this discovery (EA Explorer keeps the setup and takes back what you found; you do the reading):
1. Reach each source below with your own tools and access. Read only what `include` says (empty: everything shared),
   and attachments when `attachments` is true. Read mode "new": only what is new or changed since `position`.
2. Never read or use a file, mail or attachment marked "NOT FOR AI USE OR AUTOMATED PROCESSING": report its title,
   place and date with discovery_report_skipped, and nothing else about it.
3. Fit what you find to the target model's metamodel (get_metamodel, describe_entity_type, allowed_relationships).
   Where nothing fits, change the metamodel (start_metamodel_draft and the draft tools) and say so in the summary.
4. Match what you find to the elements already there (search_entities). Where sure, update the element
   (update_entity); where unsure, add yours and record "may be the same as" the other in discovery_record_found.
5. Add the content with add_entities and add_relationships (as your uncommitted changes in the target model).
6. For every element and relationship you added or changed, call discovery_record_found with where it was found:
   the source, the item (mail, file, page, ticket, commit), where in it (page, line, slide, moment) and a link.
7. Decision records and dispensations you find in the sources: log them with discovery_log_decision (as Drafts the
   Architecture Board accepts or rejects), with where each was found.
8. Finish with discovery_finish_run: where each source got to, what is gone (elements whose source item is no
   longer there), and a short summary. It commits your changes as "AI agent on behalf of" the person who set the
   project up, tags the model again, and reports back. Show the person the report."""


def start_run(conn, user, ref: Any, read: str = "", gone: str = "", ai_client: str = "",
              now: datetime | None = None) -> dict:
    """Start a run of a discovery project (the AI, with its own MCP sign-in). Without read or gone, asks which (the
    project's defaults suggested). The target model is tagged first; the answer holds the sources and the guide."""
    now = now or datetime.now(UTC)
    p = _project_row(conn, ref)
    if not _visible(conn, user, p):
        raise EditError(f"No discovery project {ref!r}.", 404)
    if read not in READ_MODES or gone not in GONE_MODES:
        return {"ask": True, "project": p["name"],
                "question": "Before the run starts, choose with the person (or by the project's defaults on a scheduled run):",
                "read": {"choices": READ_MODES, "default": p["read_default"], "chosen": read or None},
                "gone": {"choices": GONE_MODES, "default": p["gone_default"], "chosen": gone or None},
                "next": "Call run_discovery_project again with read and gone."}
    old = _running(conn, p["id"])
    if old:
        if now - old["started_at"] < STALE_RUN:
            raise EditError(f"Run {old['number']} of {p['name']} is still under way (started {old['started_at']:%d %b %H:%M}): "
                            "finish it with discovery_finish_run first.", 409)
        conn.execute(text("UPDATE core.discovery_runs SET status = 'abandoned', finished_at = :n, summary = :s WHERE id = :i"),
                     {"n": now, "s": "Left unfinished: abandoned when the next run started.", "i": old["id"]})
    from . import tags as tg
    number = int(conn.execute(text("SELECT coalesce(max(number), 0) + 1 FROM core.discovery_runs WHERE project_id = :p"),
                              {"p": p["id"]}).scalar())
    rg = uuid.uuid4()                     # its tags carry it: a project deleted and set up again starts at run 1 again
    tag = tg.create_tag(conn, str(p["target_model"]), user, f"Discovery {p['name']} run {number} {str(rg)[:8]} (before)",
                        f"Before run {number} of discovery project {p['name']}, AI agent on behalf of {p['set_up_by']}")
    r = _one(conn, """INSERT INTO core.discovery_runs (guid, project_id, number, run_by, on_behalf_of, ai_client, read_mode,
                                                       gone_mode, start_tag, started_at)
                      VALUES (:rg, :p, :n, :u, :b, :c, :r, :g, :t, :at) RETURNING *""",
             rg=str(rg), p=p["id"], n=number, u=user.username, b=p["set_up_by"], c=str(ai_client or "")[:200], r=read, g=gone,
             t=tag["id"], at=now)
    sources = [{"id": s["id"], "kind": s["kind"], "kind_label": KINDS[s["kind"]]["label"], "name": s["name"],
                "location": s["location"], "include": s["include"] or "everything the source shares",
                "attachments": s["attachments"], "sign_in": s["sign_in"],
                "position": (s["position"] or "(none: read everything)") if read == "new" else "(read everything again)"}
               for s in _rows(conn, "SELECT * FROM core.discovery_resources WHERE project_id = :p AND enabled ORDER BY id", p=p["id"])]
    return {"run": str(r["guid"]), "number": number, "project": p["name"],
            "target_model": {"id": str(p["target_model"]), "name": _model_name(conn, p["target_model"])},
            "who": f"AI agent on behalf of {p['set_up_by']}", "read": read, "gone": gone,
            "tagged": tag["name"], "sources": sources, "not_for_ai": NOT_FOR_AI, "guide": RUN_GUIDE}


def _run_row(conn, user, run: Any, open_only: bool = False) -> tuple[dict, dict]:
    g = repo._as_guid(run)
    r = _one(conn, "SELECT * FROM core.discovery_runs WHERE guid = :g", g=str(g)) if g else None
    if not r:
        raise EditError(f"No discovery run {run!r}.", 404)
    p = _one(conn, "SELECT * FROM core.discovery_projects WHERE id = :i", i=r["project_id"])
    if not p or not _visible(conn, user, p):
        raise EditError(f"No discovery run {run!r}.", 404)
    if open_only and r["status"] != "running":
        raise EditError(f"Run {r['number']} of {p['name']} is {r['status']}: start a new run.", 409)
    if open_only and (r["run_by"] or "").lower() != (user.username or "").lower() and perms.SUPER_ADMIN not in user.roles:
        raise EditError(f"Run {r['number']} was started by {r['run_by']}: only that AI sign-in reports into it.", 403)
    return r, p


def _resource_by(conn, pid: int, ref: Any) -> dict | None:
    if ref in (None, ""):
        return None
    if str(ref).isdigit():
        r = _one(conn, "SELECT * FROM core.discovery_resources WHERE project_id = :p AND id = :i", p=pid, i=int(ref))
        if r:
            return r
    return _one(conn, "SELECT * FROM core.discovery_resources WHERE project_id = :p AND lower(name) = lower(:n)", p=pid, n=str(ref))


def record_found(conn, user, run: Any, items: list[dict]) -> dict:
    """Where each element or relationship the run added or changed was found, and what may be the same as one already
    there: items [{element, kind: entity|relationship, source, item, place, link, may_be_same, note}]."""
    r, p = _run_row(conn, user, run, open_only=True)
    if len(items or []) > MAX_ROWS:
        raise EditError(f"Send at most {MAX_ROWS} at a time.", 400)
    found = same = 0
    for it in items or []:
        ref = str(it.get("element") or "").strip()
        if not ref:
            raise EditError("Each item names its element (its name, display ID or guid).", 400)
        kind = it.get("kind") or "entity"
        if kind not in ("entity", "relationship"):
            raise EditError("kind is entity or relationship.", 400)
        src = _resource_by(conn, p["id"], it.get("source"))
        conn.execute(text("""INSERT INTO core.discovery_found_in (run_id, model_guid, element_kind, element_ref, element_name,
                                                                   resource_id, resource_name, item, place, link)
                             VALUES (:r, :m, :k, :e, :en, :s, :sn, :i, :pl, :l)"""),
                     {"r": r["id"], "m": str(p["target_model"]), "k": kind, "e": ref[:500], "en": ref[:500],
                      "s": src["id"] if src else None, "sn": (src["name"] if src else str(it.get("source") or ""))[:200],
                      "i": str(it.get("item") or "")[:1000], "pl": str(it.get("place") or "")[:500],
                      "l": str(it.get("link") or "")[:2000]})
        found += 1
        if it.get("may_be_same"):
            conn.execute(text("""INSERT INTO core.discovery_maybe_same (run_id, model_guid, element_ref, other_ref, note)
                                 VALUES (:r, :m, :e, :o, :n)"""),
                         {"r": r["id"], "m": str(p["target_model"]), "e": ref[:500], "o": str(it["may_be_same"])[:500],
                          "n": str(it.get("note") or "")[:1000]})
            same += 1
    return {"recorded": found, "may_be_same": same}


def record_skipped(conn, user, run: Any, items: list[dict]) -> dict:
    """What the run skipped because it is marked NOT FOR AI USE OR AUTOMATED PROCESSING: items [{source, title, place,
    date}] (the title, place and date only; never what it holds)."""
    r, _p = _run_row(conn, user, run, open_only=True)
    if len(items or []) > MAX_ROWS:
        raise EditError(f"Send at most {MAX_ROWS} at a time.", 400)
    for it in items or []:
        if not str(it.get("title") or "").strip():
            raise EditError("Each skipped item has its title.", 400)
        conn.execute(text("""INSERT INTO core.discovery_skipped (run_id, resource_name, title, place, item_date)
                             VALUES (:r, :s, :t, :p, :d)"""),
                     {"r": r["id"], "s": str(it.get("source") or "")[:200], "t": str(it["title"])[:500],
                      "p": str(it.get("place") or "")[:1000], "d": str(it.get("date") or "")[:50]})
    return {"recorded": len(items or [])}


def _entity_guid(conn, model_id: int, ref: str) -> tuple[str | None, str]:
    g = repo._as_guid(ref)
    row = _one(conn, f"""SELECT guid, name FROM core.entities WHERE model_id = :m AND NOT is_deleted AND
                         {'guid = :r' if g else '(lower(display_id) = lower(:r) OR lower(name) = lower(:r))'}
                         ORDER BY display_id LIMIT 1""", m=model_id, r=str(g) if g else ref)
    return (str(row["guid"]), row["name"]) if row else (None, "")


def finish_run(conn, user, run: Any, positions: dict | None = None, gone: list[dict] | None = None, summary: str = "",
               now: datetime | None = None) -> dict:
    """Finish a run: what is gone handled as the run chose (marked, or deleted), the AI's changes committed as "AI
    agent on behalf of" the person who set the project up (or their commit asked for), Found in tied to the elements,
    where each source got to kept, the model tagged again, and the next run's due time set. Returns the run's report."""
    from . import commits as cm
    from . import content as ct
    from . import tags as tg
    now = now or datetime.now(UTC)
    r, p = _run_row(conn, user, run, open_only=True)
    m = repo.get_model(conn, str(p["target_model"]))
    commits = cm.uses_commits(m)
    gone_done = []
    for it in gone or []:
        ref = str(it.get("element") or "").strip()
        guid, name = _entity_guid(conn, m["_id"], ref)
        if not guid:
            continue
        if r["gone_mode"] == "delete":
            if commits:
                cm.record(conn, str(m["id"]), user.username, "entity.delete", {"entity": guid})
            else:
                ct.delete_entity(conn, str(m["id"]), guid)
        conn.execute(text("""INSERT INTO core.discovery_not_found (run_id, model_guid, element_guid, element_name, resource_name, action)
                             VALUES (:r, :m, :g, :n, :s, :a)"""),
                     {"r": r["id"], "m": str(m["id"]), "g": guid, "n": name, "s": str(it.get("source") or "")[:200],
                      "a": "deleted" if r["gone_mode"] == "delete" else "marked"})
        gone_done.append(name)
    who = f"AI agent on behalf of {p['set_up_by']}"
    committed, note = 0, "Content saved as it was added (this model keeps no uncommitted changes)."
    if commits:
        try:
            pending = cm._changes_for(conn, m, user, None, None)
        except EditError:                 # none: the run found nothing new (it says so, it does not fail)
            pending = []
        if not pending:
            note = "Nothing to commit: the run found nothing new."
        elif cm.may_commit(conn, user, m):
            try:
                out = cm.commit(conn, str(m["id"]), user, message=f"{who}: discovery {p['name']} run {r['number']}")
                committed, note = len(pending), f"Committed {len(pending)} change(s) ({out.get('message') or 'done'})."
            except cm.CommitConflict as exc:
                note = f"Not committed: {exc} (the model's Changes tab)."
        else:
            cm.request_commit(conn, str(m["id"]), user, note=f"{who}: discovery {p['name']} run {r['number']}")
            note = (f"{len(pending)} change(s) waiting: the AI's sign-in may not commit in {m['name']}, so its committers "
                    "were asked to commit them.")
    for f in _rows(conn, "SELECT id, element_kind, element_ref FROM core.discovery_found_in WHERE run_id = :r AND element_guid IS NULL", r=r["id"]):
        if f["element_kind"] == "entity":
            g, name = _entity_guid(conn, m["_id"], f["element_ref"])
        else:
            g = repo._as_guid(f["element_ref"])
            g, name = (str(g), "") if g else (None, "")
        if g:
            conn.execute(text("UPDATE core.discovery_found_in SET element_guid = :g, element_name = coalesce(nullif(:n, ''), element_name) WHERE id = :i"),
                         {"g": g, "n": name, "i": f["id"]})
    for s in _rows(conn, "SELECT id, element_ref FROM core.discovery_maybe_same WHERE run_id = :r", r=r["id"]):
        a, _n = _entity_guid(conn, m["_id"], s["element_ref"])
        conn.execute(text("UPDATE core.discovery_maybe_same SET element_guid = :a WHERE id = :i"), {"a": a, "i": s["id"]})
    for s in _rows(conn, "SELECT id, other_ref FROM core.discovery_maybe_same WHERE run_id = :r", r=r["id"]):
        o, _n = _entity_guid(conn, m["_id"], s["other_ref"])
        conn.execute(text("UPDATE core.discovery_maybe_same SET other_guid = :o WHERE id = :i"), {"o": o, "i": s["id"]})
    for key, pos in (positions or {}).items():
        src = _resource_by(conn, p["id"], key)
        if src:
            conn.execute(text("UPDATE core.discovery_resources SET position = :pos, position_at = :n WHERE id = :i"),
                         {"pos": str(pos)[:2000], "n": now, "i": src["id"]})
    end = tg.create_tag(conn, str(m["id"]), user, f"Discovery {p['name']} run {r['number']} {str(r['guid'])[:8]} (after)",
                        f"After run {r['number']} of discovery project {p['name']}, {who}")
    counts = {k: int(conn.execute(text(f"SELECT count(*) FROM core.{t} WHERE run_id = :r"), {"r": r["id"]}).scalar() or 0)
              for k, t in (("found", "discovery_found_in"), ("skipped", "discovery_skipped"),
                           ("may_be_same", "discovery_maybe_same"), ("not_found", "discovery_not_found"))}
    counts["committed"] = committed
    conn.execute(text("""UPDATE core.discovery_runs SET status = 'finished', finished_at = :n, end_tag = :t, summary = :s,
                                counts = CAST(:c AS jsonb) WHERE id = :i"""),
                 {"n": now, "t": end["id"], "s": f"{(summary or '').strip()}\n\n{note}".strip()[:8000],
                  "c": json.dumps(counts), "i": r["id"]})
    nd = next_due(p["schedule"], p["schedule_day"], p["schedule_time"], now)
    conn.execute(text("UPDATE core.discovery_projects SET next_due_at = :d WHERE id = :i"), {"d": nd, "i": p["id"]})
    return {**report(conn, user, str(r["guid"])), "committing": note, "gone": gone_done}


def report(conn, user, run: Any) -> dict:
    """A run's report: who ran it and for whom, what it found and where, what it skipped as NOT FOR AI, what may be
    the same as an element already there, what was no longer found, and how to see what it changed (its two tags)."""
    r, p = _run_row(conn, user, run)
    mid = str(p["target_model"])
    compare = (f"#/compare?left=tag:{mid}:{r['start_tag']}&right=tag:{mid}:{r['end_tag']}" if r["end_tag"] else
               f"#/compare?left=tag:{mid}:{r['start_tag']}&right=model:{mid}" if r["start_tag"] else "")
    return {"project": {"id": str(p["guid"]), "name": p["name"]}, "run": _run_out(r),
            "target_model": {"id": mid, "name": _model_name(conn, mid)}, "compare": compare,
            "found": _rows(conn, """SELECT element_kind AS kind, element_ref, element_guid::text AS element_id, element_name,
                                           resource_name AS source, item, place, link
                                      FROM core.discovery_found_in WHERE run_id = :r ORDER BY id LIMIT 2000""", r=r["id"]),
            "skipped": _rows(conn, """SELECT resource_name AS source, title, place, item_date AS date, reason
                                        FROM core.discovery_skipped WHERE run_id = :r ORDER BY id""", r=r["id"]),
            "may_be_same": _rows(conn, """SELECT id, element_ref, element_guid::text AS element_id, other_ref,
                                                 other_guid::text AS other_id, note, resolved_by, resolved_at
                                            FROM core.discovery_maybe_same WHERE run_id = :r ORDER BY id""", r=r["id"]),
            "not_found": _rows(conn, """SELECT element_guid::text AS element_id, element_name, resource_name AS source, action
                                          FROM core.discovery_not_found WHERE run_id = :r ORDER BY id""", r=r["id"])}


def resolve_maybe_same(conn, user, run: Any, flag_id: int) -> dict:
    """Mark a "may be the same as" flag dealt with (merged with Dedupe, or kept apart)."""
    r, _p = _run_row(conn, user, run)
    n = conn.execute(text("""UPDATE core.discovery_maybe_same SET resolved_by = :u, resolved_at = now()
                              WHERE id = :i AND run_id = :r AND resolved_at IS NULL"""),
                     {"u": user.username, "i": int(flag_id), "r": r["id"]}).rowcount
    if not n:
        raise EditError("No such open flag in this run.", 404)
    return {"message": "Marked as dealt with."}


def found_in(conn, user, model: Any, entity: Any) -> dict:
    """Where an element was found by discovery runs (newest first), and whether a later run no longer found it."""
    m = repo.get_model(conn, model)
    e = repo._find_entity(conn, m, entity)
    rows = _rows(conn, """SELECT f.resource_name AS source, f.item, f.place, f.link, f.created_at, r.number AS run_number,
                                 r.guid::text AS run, r.on_behalf_of, p.name AS project, p.guid::text AS project_id
                            FROM core.discovery_found_in f
                            JOIN core.discovery_runs r ON r.id = f.run_id
                            JOIN core.discovery_projects p ON p.id = r.project_id
                           WHERE f.model_guid = :m AND f.element_guid = :e ORDER BY f.created_at DESC LIMIT 200""",
                 m=str(m["id"]), e=str(e["id"]))
    for x in rows:
        x["who"] = f"AI agent on behalf of {x.pop('on_behalf_of')}"
    gone = _one(conn, """SELECT r.number AS run_number, p.name AS project, n.action, r.finished_at
                           FROM core.discovery_not_found n JOIN core.discovery_runs r ON r.id = n.run_id
                           JOIN core.discovery_projects p ON p.id = r.project_id
                          WHERE n.model_guid = :m AND n.element_guid = :e ORDER BY n.id DESC LIMIT 1""",
                 m=str(m["id"]), e=str(e["id"]))
    return {"found_in": rows, "not_found_since": gone}


def log_decision(core_conn, proj_conn, user, run: Any, d: dict) -> dict:
    """A decision record or dispensation the AI found in a source, logged as a Draft in the organisation's Governance
    Log with where it was found; the Architecture Board accepts or rejects it (the AI drafts, the Board decides)."""
    from . import decisions as dec
    r, p = _run_row(core_conn, user, run, open_only=True)
    kind = {"adr": dec.ADR, "dispensation": dec.DISP}.get(str(d.get("kind") or "").strip().lower(), d.get("kind"))
    if kind not in (dec.ADR, dec.DISP):
        raise EditError("kind is ADR or Dispensation.", 400)
    keep = ("title", "owner", "sponsor", "phase", "record_type", "expires_on", "raised_on", "html", "fields")
    body = {k: d[k] for k in keep if d.get(k) not in (None, "")}
    body.update({"kind": kind, "status": "Draft", "_ai": True,
                 "found_in": {"project": p["name"], "run": r["number"], "who": f"AI agent on behalf of {p['set_up_by']}",
                              "source": str(d.get("source") or "")[:200], "item": str(d.get("item") or "")[:1000],
                              "place": str(d.get("place") or "")[:500], "link": str(d.get("link") or "")[:2000]}})
    out = dec.org_add(proj_conn, user, body)
    return {**out, "note": "Logged as a Draft: the Architecture Board accepts or rejects it on the Governance Log."}
