"""The service desk (R5.11, D692: the catalogue as proposed, editable, "add more defaults as needed").

People ask for things from a **service catalogue**: each request type has its own form, a team that works on it, an
optional approval (and by whom) and a target time. A **ticket** (REQ-<n>) moves through: new, waiting for approval,
approved, in progress, waiting for the requester, done, declined, cancelled; with a priority, who raised it, who it is
assigned to, comments both ways, small attachments, the history of every change, and what it is about (a model, a
project). Teams:
  a global role   super-admin, it-admin, user-admin, model-creator, library-admin: anyone with it works the queue
  model-admins    the Model Admins of the ticket's model
  project-admins  the Project Admins of the ticket's project
Approving runs the matching wizard where one exists: access to a model is given at once (as the approver, so the
database's own rules still decide); for the others the approver is taken to the wizard with the request's details.
Super Admins add, change and switch off request types (System Admin > Service catalogue). Notifications go to the team
and the requester at each step (category request). Tables only in the database (D248): core.service_*, migration 0082.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from . import permissions as P

STATUSES = ("new", "waiting-approval", "approved", "in-progress", "waiting-requester", "done", "declined", "cancelled")
OPEN = ("new", "waiting-approval", "approved", "in-progress", "waiting-requester")
PRIORITIES = ("low", "normal", "high", "urgent")
TEAMS = (P.SUPER_ADMIN, P.IT_ADMIN, P.USER_ADMIN, P.MODEL_CREATOR, P.LIBRARY_ADMIN, "model-admins", "project-admins")
FIELD_KINDS = ("text", "textarea", "model", "project", "person", "model-role", "project-role", "global-role", "date", "choice", "number")
MAX_FILE = 10 * 1024 * 1024
LINK = "#/service-desk"


class DeskError(Exception):
    """A service desk request refused, with the HTTP status to answer."""
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _rows(conn, sql: str, **p) -> list[dict]:
    return [dict(r) for r in conn.execute(text(sql), p).mappings()]


def _one(conn, sql: str, **p) -> dict | None:
    r = conn.execute(text(sql), p).mappings().first()
    return dict(r) if r else None


# ---------------------------------------------------------------- the catalogue
def clean_type(body: dict) -> dict:
    """A request type checked: its key, area, name, form and team."""
    key = re.sub(r"[^a-z0-9-]", "-", str(body.get("key") or "").lower()).strip("-")[:40]
    if not key:
        raise DeskError("key: a short name (letters, digits, -).")
    name = str(body.get("name") or "").strip()[:120]
    if not name:
        raise DeskError("name: what people ask for.")
    team = str(body.get("team") or P.SUPER_ADMIN)
    approval = str(body.get("approval") or "")
    if team not in TEAMS or (approval and approval not in TEAMS):
        raise DeskError(f"team and approval: one of {', '.join(TEAMS)} (approval may be empty).")
    fields = []
    for f in body.get("form") or []:
        kind = f.get("kind") or "text"
        if kind not in FIELD_KINDS:
            raise DeskError(f"A field's kind: one of {', '.join(FIELD_KINDS)}.")
        fname = re.sub(r"[^a-z0-9_]", "_", str(f.get("name") or "").lower())[:40]
        if not fname:
            raise DeskError("Each field needs a name.")
        fields.append({"name": fname, "label": str(f.get("label") or fname)[:120], "kind": kind,
                       "required": bool(f.get("required")), "choices": [str(c) for c in f.get("choices") or []][:50],
                       "help": str(f.get("help") or "")[:300]})
    hours = int(body.get("target_hours") or 24)
    if not 1 <= hours <= 24 * 90:
        raise DeskError("target_hours: 1 to 2,160.")
    return {"key": key, "area": str(body.get("area") or "Help")[:40], "name": name, "about": str(body.get("about") or "")[:500],
            "form": fields, "team": team, "approval": approval, "target_hours": hours,
            "wizard": str(body.get("wizard") or "")[:200], "enabled": body.get("enabled", True) is not False,
            "sort": int(body.get("sort") or 100)}


def catalogue(conn, everything: bool = False) -> list[dict]:
    """The service catalogue (the switched-off types too when asked)."""
    rows = _rows(conn, "SELECT * FROM core.service_types" + ("" if everything else " WHERE enabled") + " ORDER BY area, sort, name")
    return rows


def type_of(conn, key: str) -> dict:
    """One request type."""
    t = _one(conn, "SELECT * FROM core.service_types WHERE key = :k", k=key)
    if not t:
        raise DeskError(f"No request type {key}.", 404)
    return t


def save_type(conn, body: dict, by: str) -> dict:
    """Saves a request type, new or changed."""
    t = clean_type(body)
    conn.execute(text("""INSERT INTO core.service_types (key, area, name, about, form, team, approval, target_hours, wizard, enabled,
                                sort, modified_by)
                         VALUES (:key, :area, :name, :about, CAST(:form AS jsonb), :team, :approval, :target_hours, :wizard,
                                 :enabled, :sort, :by)
                         ON CONFLICT (key) DO UPDATE SET area = EXCLUDED.area, name = EXCLUDED.name, about = EXCLUDED.about,
                             form = EXCLUDED.form, team = EXCLUDED.team, approval = EXCLUDED.approval,
                             target_hours = EXCLUDED.target_hours, wizard = EXCLUDED.wizard, enabled = EXCLUDED.enabled,
                             sort = EXCLUDED.sort, modified_by = EXCLUDED.modified_by, modified_at = now()"""),
                 {**t, "form": json.dumps(t["form"]), "by": by})
    return type_of(conn, t["key"])


# ---------------------------------------------------------------- who works on what
def _model_admins(conn, model_guid: str | None) -> set[str]:
    if not model_guid:
        return set()
    return {r["username"] for r in _rows(conn, """SELECT u.username FROM core.model_users u JOIN core.models m ON m.id = u.model_id
                                                   WHERE m.guid = CAST(:g AS uuid) AND u.role = 'model-admin'""", g=model_guid)}


def _project_admins(conn, project_guid: str | None) -> set[str]:
    if not project_guid:
        return set()
    try:
        return {r["username"] for r in _rows(conn, """SELECT m.username FROM proj.members m JOIN proj.projects p ON p.id = m.project_id
                                                       WHERE p.guid = CAST(:g AS uuid) AND m.role = 'project-admin'""", g=project_guid)}
    except Exception:  # noqa: BLE001 - the projects part off or elsewhere
        return set()


def in_team(conn, team: str, username: str, roles, ticket: dict) -> bool:
    """Whether the person is on the team a request goes to."""
    roles = set(roles or [])
    if P.SUPER_ADMIN in roles:
        return True
    if team == "model-admins":
        return username.lower() in _model_admins(conn, ticket.get("model_guid"))
    if team == "project-admins":
        return username.lower() in _project_admins(conn, ticket.get("project_guid"))
    return team in roles


def team_people(conn, team: str, ticket: dict) -> list[str]:
    """Who works on (or approves) a request; the Super Admins when the team has nobody (a model with no Model Admin).
    Service accounts (svc-, the self-test's) are never told."""
    if team == "model-admins":
        found = _model_admins(conn, ticket.get("model_guid"))
    elif team == "project-admins":
        found = _project_admins(conn, ticket.get("project_guid"))
    else:
        found = {r["u"] for r in _rows(conn, "SELECT lower(username) AS u FROM core.known_users WHERE :r = ANY (roles)", r=team)}
    found = {u for u in found if not u.startswith("svc-")}
    if not found and team != P.SUPER_ADMIN:
        return team_people(conn, P.SUPER_ADMIN, ticket)
    return sorted(found)


# ---------------------------------------------------------------- tickets
def _shape(conn, t: dict, me: str = "", roles=()) -> dict:
    t = dict(t)
    t["number"] = f"REQ-{t['id']}"
    now = datetime.now(UTC)
    t["overdue"] = bool(t["status"] in OPEN and t.get("due_at") and t["due_at"] < now)
    for k in ("created_at", "updated_at", "closed_at", "due_at", "approved_at"):
        if t.get(k):
            t[k] = t[k].isoformat()
    if me:
        t["mine"] = t["raised_by"] == me.lower()
        t["can_work"] = in_team(conn, t["team"], me, roles, t)
        t["can_approve"] = bool(t["approval"]) and t["status"] == "waiting-approval" and in_team(conn, t["approval"], me, roles, t)
    return t


def get(conn, ident, me: str, roles) -> dict:
    """One request (REQ-n) with its history, for its requester or its team."""
    n = int(str(ident).upper().removeprefix("REQ-"))
    t = _one(conn, "SELECT * FROM core.service_tickets WHERE id = :i", i=n)
    if not t:
        raise DeskError(f"No request REQ-{n}.", 404)
    s = _shape(conn, t, me, roles)
    if not (s["mine"] or s["can_work"] or (t["approval"] and in_team(conn, t["approval"], me, roles, t))
            or t.get("assigned_to") == me.lower() or P.AUDITOR in set(roles or [])):
        raise DeskError("This request is not yours to see.", 403)
    s["events"] = [{**e, "at": e["at"].isoformat()} for e in _rows(conn, """SELECT id, at, by_whom, kind, body, data FROM core.service_ticket_events
                                                                           WHERE ticket_id = :t ORDER BY at, id""", t=n)]
    s["files"] = _rows(conn, "SELECT id, name, mime, size, added_by, added_at FROM core.service_ticket_files WHERE ticket_id = :t ORDER BY id", t=n)
    s["type"] = _one(conn, "SELECT key, name, form, wizard FROM core.service_types WHERE key = :k", k=t["type_key"])
    return s


def _event(conn, ticket_id: int, by: str, kind: str, body: str = "", data: dict | None = None) -> None:
    conn.execute(text("""INSERT INTO core.service_ticket_events (ticket_id, by_whom, kind, body, data)
                         VALUES (:t, :b, :k, :x, CAST(:d AS jsonb))"""),
                 {"t": ticket_id, "b": by, "k": kind, "x": body[:4000], "d": json.dumps(data or {}, default=str)})
    conn.execute(text("UPDATE core.service_tickets SET updated_at = now() WHERE id = :t"), {"t": ticket_id})


def _tell(conn, t: dict, people, title: str, actor: str, needs_action: bool = False) -> None:
    from . import notify
    try:
        notify.create(conn, kind="servicedesk", category="request", title=f"REQ-{t['id']}: {title}"[:300],
                      body=str(t.get("title") or ""), link=f"{LINK}/REQ-{t['id']}", actor=actor,
                      recipients=sorted({p for p in people if p}), needs_action=needs_action)
    except Exception:  # noqa: BLE001 - a notification never stops a request
        pass


def check_fields(conn, ty: dict, fields: dict) -> dict:
    """A request's fields checked against its type's form."""
    out = {}
    for f in ty["form"] or []:
        v = (fields or {}).get(f["name"])
        if v in (None, "") and f.get("required"):
            raise DeskError(f"{f['label']}: please fill it in.")
        if v in (None, ""):
            continue
        if f["kind"] == "choice" and f.get("choices") and str(v) not in f["choices"]:
            raise DeskError(f"{f['label']}: one of {', '.join(f['choices'])}.")
        if f["kind"] == "model-role" and v not in P.MODEL_ROLES:
            raise DeskError(f"{f['label']}: one of {', '.join(P.MODEL_ROLES)}.")
        if f["kind"] == "global-role" and v not in P.GLOBAL_ROLES:
            raise DeskError(f"{f['label']}: one of {', '.join(P.GLOBAL_ROLES)}.")
        out[f["name"]] = str(v)[:4000] if not isinstance(v, (int, float)) else v
    return out


def raise_ticket(conn, me: str, body: dict) -> dict:
    """Raises a request from the catalogue; its team is told."""
    ty = type_of(conn, str(body.get("type") or ""))
    if not ty["enabled"]:
        raise DeskError(f"{ty['name']} cannot be asked for now.")
    fields = check_fields(conn, ty, body.get("fields") or {})
    model = fields.get("model") or body.get("model_guid") or None
    project = fields.get("project") or body.get("project_guid") or None
    priority = body.get("priority") or "normal"
    if priority not in PRIORITIES:
        raise DeskError(f"priority: one of {', '.join(PRIORITIES)}.")
    title = str(body.get("title") or ty["name"]).strip()[:200]
    status = "waiting-approval" if ty["approval"] else "new"
    row = _one(conn, """INSERT INTO core.service_tickets (type_key, title, fields, status, priority, raised_by, team, approval,
                               model_guid, project_guid, due_at)
                        VALUES (:k, :t, CAST(:f AS jsonb), :s, :p, :u, :team, :a, CAST(:m AS uuid), CAST(:pr AS uuid),
                                now() + make_interval(hours => :h))
                        RETURNING *""",
               k=ty["key"], t=title, f=json.dumps(fields), s=status, p=priority, u=me.lower(), team=ty["team"], a=ty["approval"],
               m=model, pr=project, h=int(ty["target_hours"]))
    _event(conn, row["id"], me, "raised", str(body.get("note") or ""), {"fields": fields})
    who = team_people(conn, ty["approval"] or ty["team"], row)
    _tell(conn, row, who, ("Approve: " if ty["approval"] else "New: ") + title, me, needs_action=True)
    return _shape(conn, row, me, ())


def listing(conn, me: str, roles, view: str = "mine", status: str = "open", q: str = "") -> dict:
    """The requests the person sees (theirs, their team's queue, or all), filtered."""
    rows = _rows(conn, "SELECT * FROM core.service_tickets ORDER BY id DESC LIMIT 2000")
    out = []
    for t in rows:
        s = _shape(conn, t, me, roles)
        if view == "mine" and not s["mine"]:
            continue
        if view == "queue" and not (s["can_work"] or s["can_approve"] or t.get("assigned_to") == me.lower()):
            continue
        if view == "all" and not (P.SUPER_ADMIN in set(roles or []) or P.AUDITOR in set(roles or [])):
            continue
        if status == "open" and t["status"] not in OPEN or status not in ("open", "all") and t["status"] != status:
            continue
        if q and q.lower() not in f"{s['number']} {t['title']} {t['raised_by']} {t['type_key']}".lower():
            continue
        out.append(s)
    counts = {st: sum(1 for t in out if t["status"] == st) for st in STATUSES}
    return {"tickets": out, "counts": counts, "overdue": sum(1 for t in out if t["overdue"])}


def act(conn, ident, me: str, roles, action: str, body: dict) -> dict:
    """comment, assign (to me or {to}), status {status}, approve, decline, cancel (the requester), priority {priority}."""
    t = get(conn, ident, me, roles)
    tid, note = int(t["id"]), str(body.get("note") or body.get("body") or "")
    if action == "comment":
        if not note.strip():
            raise DeskError("Write something.")
        _event(conn, tid, me, "comment", note)
        others = ({t["raised_by"]} | ({t["assigned_to"]} if t.get("assigned_to") else set())) - {me.lower()}
        if t["mine"] and not t.get("assigned_to"):
            others |= set(team_people(conn, t["team"], t))
        _tell(conn, t, others, f"{me} wrote: {note[:120]}", me)
    elif action == "cancel":
        if not t["mine"] or t["status"] not in OPEN:
            raise DeskError("Only the person who asked cancels an open request.", 403)
        _set_status(conn, t, "cancelled", me, note)
    elif action in ("approve", "decline"):
        if not t["can_approve"]:
            raise DeskError("You do not approve this request (or it is not waiting for approval).", 403)
        conn.execute(text("UPDATE core.service_tickets SET approved_by = :b, approved_at = now() WHERE id = :t"), {"b": me, "t": tid})
        _set_status(conn, t, "approved" if action == "approve" else "declined", me, note)
        if action == "approve":
            _tell(conn, t, team_people(conn, t["team"], t), f"Approved by {me}: work on it", me, needs_action=True)
    elif action == "assign":
        if not t["can_work"]:
            raise DeskError("Only the team that works on it assigns it.", 403)
        to = str(body.get("to") or me).lower()
        conn.execute(text("UPDATE core.service_tickets SET assigned_to = :a WHERE id = :t"), {"a": to, "t": tid})
        _event(conn, tid, me, "assigned", note, {"to": to})
        if t["status"] in ("new", "approved"):
            _set_status(conn, {**t, "assigned_to": to}, "in-progress", me, "")
        _tell(conn, t, {to, t["raised_by"]} - {me.lower()}, f"Assigned to {to}", me, needs_action=to != me.lower())
    elif action == "status":
        new = str(body.get("status") or "")
        if new not in STATUSES or new in ("waiting-approval", "approved", "cancelled"):
            raise DeskError("status: in-progress, waiting-requester, done or declined.")
        if not t["can_work"]:
            raise DeskError("Only the team that works on it changes its status.", 403)
        if t["approval"] and not t.get("approved_by") and new == "done":
            raise DeskError("It needs its approval first.", 409)
        _set_status(conn, t, new, me, note)
    elif action == "priority":
        p = str(body.get("priority") or "")
        if p not in PRIORITIES or not t["can_work"]:
            raise DeskError(f"priority: one of {', '.join(PRIORITIES)} (the team sets it).")
        conn.execute(text("UPDATE core.service_tickets SET priority = :p WHERE id = :t"), {"p": p, "t": tid})
        _event(conn, tid, me, "priority", note, {"priority": p})
    else:
        raise DeskError(f"Unknown action {action}.")
    return get(conn, tid, me, roles)


def _set_status(conn, t: dict, new: str, me: str, note: str) -> None:
    closed = new in ("done", "declined", "cancelled")
    conn.execute(text("UPDATE core.service_tickets SET status = :s, closed_at = CASE WHEN :c THEN now() ELSE NULL END WHERE id = :t"),
                 {"s": new, "c": closed, "t": int(t["id"])})
    _event(conn, int(t["id"]), me, "status", note, {"from": t["status"], "to": new})
    if t["raised_by"] != me.lower():
        _tell(conn, t, {t["raised_by"]}, f"Now {new.replace('-', ' ')}" + (f": {note[:120]}" if note else ""), me,
              needs_action=new == "waiting-requester")


# ---------------------------------------------------------------- doing what was asked (the wizards)
def run_wizard(conn, ident, me: str, roles) -> dict:
    """What an approved request asks for, done where EA Explorer can do it at once (access to a model, as the person
    doing it, so the database's own rules decide), else the address of the wizard to finish it with its details."""
    t = get(conn, ident, me, roles)
    if not t["can_work"]:
        raise DeskError("Only the team that works on it does it.", 403)
    if t["approval"] and t["status"] not in ("approved", "in-progress"):
        raise DeskError("It needs its approval first.", 409)
    f = t["fields"] or {}
    wizard = (t.get("type") or {}).get("wizard") or ""
    if wizard == "model-access":
        m = _one(conn, "SELECT id FROM core.models WHERE guid = CAST(:g AS uuid)", g=f.get("model"))
        who = str(f.get("person") or t["raised_by"]).lower()
        role = f.get("role") or P.REPORT_VIEWER
        if not m or role not in P.MODEL_ROLES:
            raise DeskError("The request names no model or no model role.")
        conn.execute(text("""INSERT INTO core.model_users (model_id, username, role) VALUES (:m, :u, :r)
                             ON CONFLICT (model_id, username, role) DO NOTHING"""), {"m": m["id"], "u": who, "r": role})
        _event(conn, int(t["id"]), me, "done-by-wizard", f"{who} given {role}", {"model": f.get("model"), "role": role})
        _set_status(conn, t, "done", me, f"{who} now has {role} on the model.")
        return {"done": True, "message": f"{who} now has {role} on the model.", "ticket": get(conn, t["id"], me, roles)}
    if not wizard:
        return {"done": False, "message": "No wizard for this request: do it by hand, then mark it done."}
    from urllib.parse import urlencode
    params = {k: v for k, v in f.items() if isinstance(v, (str, int, float))} | {"request": f"REQ-{t['id']}"}
    sep = "&" if "?" in wizard else "?"
    return {"done": False, "link": f"{wizard}{sep}{urlencode(params)}", "message": "Open the wizard: the request's details are filled in."}


def add_file(conn, ident, me: str, roles, name: str, mime: str, data: bytes) -> dict:
    """Attaches a file (up to 10 MB) to a request."""
    t = get(conn, ident, me, roles)
    if len(data) > MAX_FILE:
        raise DeskError("A file of up to 10 MB.")
    fid = conn.execute(text("""INSERT INTO core.service_ticket_files (ticket_id, name, mime, size, content, added_by)
                               VALUES (:t, :n, :m, :s, :c, :b) RETURNING id"""),
                       {"t": int(t["id"]), "n": name[:200], "m": mime[:100], "s": len(data), "c": data, "b": me}).scalar()
    _event(conn, int(t["id"]), me, "file", name[:200], {"file": fid})
    return {"id": fid, "name": name, "size": len(data)}


def file_of(conn, ident, me: str, roles, fid: int) -> tuple[bytes, str, str]:
    """A request's attached file."""
    t = get(conn, ident, me, roles)
    r = _one(conn, "SELECT name, mime, content FROM core.service_ticket_files WHERE id = :f AND ticket_id = :t", f=int(fid), t=int(t["id"]))
    if not r:
        raise DeskError("No such file.", 404)
    return bytes(r["content"]), r["name"], r["mime"] or "application/octet-stream"


def overdue_reminders(conn, now: datetime | None = None) -> int:
    """Open requests past their target time, told to their team once (R5.11)."""
    n = 0
    for t in _rows(conn, """SELECT * FROM core.service_tickets WHERE status IN ('new', 'approved', 'in-progress')
                              AND due_at < :n AND NOT overdue_told""", n=now or datetime.now(UTC)):
        people = {t["assigned_to"]} if t.get("assigned_to") else set(team_people(conn, t["team"], t))
        _tell(conn, t, people, "Past its target time", "system", needs_action=True)
        conn.execute(text("UPDATE core.service_tickets SET overdue_told = true WHERE id = :t"), {"t": t["id"]})
        n += 1
    return n


def stats(conn, days: int = 30) -> dict:
    """For the board: open by team and status, done in the period, average time to done, overdue."""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = _rows(conn, "SELECT team, status, created_at, closed_at, due_at FROM core.service_tickets WHERE created_at > :s OR status = ANY(:o)",
                 s=since, o=list(OPEN))
    done = [r for r in rows if r["status"] == "done" and r["closed_at"]]
    hours = [(r["closed_at"] - r["created_at"]).total_seconds() / 3600 for r in done]
    return {"open": sum(1 for r in rows if r["status"] in OPEN),
            "by_team": {t: sum(1 for r in rows if r["team"] == t and r["status"] in OPEN) for t in {r["team"] for r in rows}},
            "done": len(done), "average_hours_to_done": round(sum(hours) / len(hours), 1) if hours else None,
            "met_target": sum(1 for r in done if r["due_at"] and r["closed_at"] <= r["due_at"])}


# ---------------------------------------------------------------- eax ticket (in the api container)
def main(argv: list[str]) -> int:
    """python -m eax.servicedesk list [open|all|<status>] | show REQ-n | comment REQ-n <text> | status REQ-n <status> [note]
    As the installation's operator ("eax", with a Super Admin's reach), every action in the request's history."""
    from .db import get_engine
    me, roles = "eax", [P.SUPER_ADMIN]
    cmd = argv[0] if argv else "list"
    try:
        with get_engine().begin() as conn:
            if cmd == "list":
                out = listing(conn, me, roles, "all", argv[1] if len(argv) > 1 else "open")
                for t in out["tickets"]:
                    flag = " OVERDUE" if t["overdue"] else ""
                    print(f"{t['number']:>8}  {t['status']:<17} {t['priority']:<7} {t['team']:<15} {t['raised_by']:<16} {t['title']}{flag}")
                print(f"{len(out['tickets'])} request(s), {out['overdue']} overdue.")
                return 0
            if cmd == "show" and len(argv) > 1:
                t = get(conn, argv[1], me, roles)
                print(f"{t['number']} {t['title']} ({t['type_key']}): {t['status']}, {t['priority']}; raised by {t['raised_by']}"
                      f"; team {t['team']}; assigned to {t.get('assigned_to') or 'nobody'}; due {t.get('due_at')}")
                for k, v in (t["fields"] or {}).items():
                    print(f"  {k}: {v}")
                for e in t["events"]:
                    print(f"  {e['at'][:16]} {e['by_whom']}: {e['kind']} {e['body']}")
                return 0
            if cmd == "comment" and len(argv) > 2:
                act(conn, argv[1], me, roles, "comment", {"note": " ".join(argv[2:])})
                print("Written.")
                return 0
            if cmd == "status" and len(argv) > 2:
                act(conn, argv[1], me, roles, "status", {"status": argv[2], "note": " ".join(argv[3:])})
                print(f"{argv[1].upper()} is now {argv[2]}.")
                return 0
    except (DeskError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(main.__doc__)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
