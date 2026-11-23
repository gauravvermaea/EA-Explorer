"""Architecture in sprints, for a project of the Agile type (Release 12, R12.2; D858, D879; TOGAF Series Guide: Applying
the TOGAF ADM using Agile Sprints, G210).

Only a project made from the Agile template has sprints (D858: "this will be only available if the project type is
agile during project setup"). Its **backlog** is drawn from the requirements in its models (requirements and security
requirements, epics and features), with deliverables and items added by hand; nothing is taken in by itself, the
architect fills the backlog when they choose (D880). Each **sprint** picks backlog items and agrees the ADM phases it
runs, the steps and the deliverables (the minimum viable architecture for that sprint), and who accepts them (named
per sprint, D879). The project sets the usual sprint length (14 days unless its template says otherwise); each sprint
can change its own dates. At the **review** each of the sprint's items is accepted or not: what is accepted is done,
what is not goes back to the backlog (counted as returned).

Rules here, rows in proj.agile_settings, proj.sprints, proj.backlog_items and proj.sprint_decisions (D248).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from . import projects as pj
from .metamodel_edit import EditError

AGILE = "agile"
DEFAULT_DAYS = 14
BACKLOG_TYPES = ("Requirement", "SecurityRequirement", "Epic", "Feature")
KINDS = ("requirement", "deliverable", "item")
PHASES = ("P", "A", "B", "C", "C-D", "C-A", "D", "E", "F", "G", "H", "RM")

_rows, _one = pj._rows, pj._one


def _project(pc, project: Any, user, what: str = "read") -> dict:
    """The project, if it is of the Agile type and the person may do what they ask."""
    p = pj.project_row(pc, project)
    pj._need(pc, p, user, what)
    if (p.get("template_code") or "") != AGILE:
        raise EditError(f"{p['name']} is not an Agile project: sprints are only for a project made from the Agile template.", 409)
    return p


def is_agile(p: dict) -> bool:
    """Whether a project has sprints (it was made from the Agile template)."""
    return (p.get("template_code") or "") == AGILE


def _text(v: Any, limit: int = 500) -> str:
    return str(v or "").strip()[:limit]


def _date(v: Any, what: str) -> date:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError as exc:
        raise EditError(f"{what} is a date (YYYY-MM-DD).") from exc


# ---------------------------------------------------------------- the sprint length
def template_days(pc) -> int:
    """The Agile template's usual sprint length (its spec's agile.sprint_days), else 14."""
    r = _one(pc, "SELECT spec FROM proj.project_templates WHERE code = :c", c=AGILE)
    spec = (r or {}).get("spec") or {}
    if isinstance(spec, str):
        spec = json.loads(spec or "{}")
    try:
        return max(1, int((spec.get("agile") or {}).get("sprint_days") or DEFAULT_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_DAYS


def sprint_days(pc, p: dict) -> int:
    """The project's usual sprint length: its own, else the template's."""
    r = _one(pc, "SELECT sprint_days FROM proj.agile_settings WHERE project_id = :p", p=p["id"])
    return int(r["sprint_days"]) if r else template_days(pc)


def set_sprint_days(pc, project: Any, user, days: Any) -> dict:
    """The project's usual sprint length, 1 to 90 days; each sprint can still change its own dates."""
    p = _project(pc, project, user, "admin")
    try:
        n = int(days)
    except (TypeError, ValueError) as exc:
        raise EditError("A sprint length is a whole number of days.") from exc
    if not 1 <= n <= 90:
        raise EditError("A sprint is 1 to 90 days long.")
    pc.execute(text("""INSERT INTO proj.agile_settings (project_id, sprint_days, changed_by) VALUES (:p, :d, :u)
                       ON CONFLICT (project_id) DO UPDATE SET sprint_days = :d, changed_by = :u, changed_at = now()"""),
               {"p": p["id"], "d": n, "u": user.username})
    return {"sprint_days": n, "message": f"Sprints in {p['name']} are usually {n} days."}


# ---------------------------------------------------------------- the backlog
def _item_out(r: dict) -> dict:
    return {"id": str(r["guid"]), "kind": r["kind"], "title": r["title"], "priority": r["priority"], "status": r["status"],
            "returned": r["returned"], "model": str(r["model_guid"]) if r.get("model_guid") else None,
            "entity": str(r["entity_guid"]) if r.get("entity_guid") else None, "item": r.get("item_id"),
            "sprint": r.get("sprint_seq"), "added_by": r["added_by"]}


def _items(pc, p: dict, where: str = "", **params) -> list[dict]:
    return _rows(pc, f"""SELECT b.*, s.seq AS sprint_seq FROM proj.backlog_items b LEFT JOIN proj.sprints s ON s.id = b.sprint_id
                          WHERE b.project_id = :p {where} ORDER BY b.priority DESC, b.id""", p=p["id"], **params)


def offered(pc, project: Any, user) -> list[dict]:
    """The requirements, security requirements, epics and features in the project's models that are not in the backlog
    yet: offered, for the architect to take in (nothing is taken in by itself, D880)."""
    p = _project(pc, project, user)
    guids = [r["g"] for r in _rows(pc, "SELECT model_guid::text AS g FROM proj.project_models WHERE project_id = :p", p=p["id"])]
    if not guids:
        return []
    have = {str(r["entity_guid"]) for r in _items(pc, p, "AND b.entity_guid IS NOT NULL")}
    core = pj.core(pc)
    rows = _rows(core, """SELECT e.guid::text AS entity, m.guid::text AS model, m.name AS model_name, t.code AS type, e.name
                            FROM core.entities e JOIN core.entity_types t ON t.id = e.entity_type_id
                            JOIN core.models m ON m.id = e.model_id
                           WHERE m.guid::text = ANY(CAST(:g AS text[])) AND t.code = ANY(CAST(:t AS text[])) AND NOT e.is_deleted
                           ORDER BY m.name, t.code, e.name""", g=guids, t=list(BACKLOG_TYPES))
    return [r for r in rows if r["entity"] not in have]


def add_to_backlog(pc, project: Any, user, d: dict) -> dict:
    """Adds to the backlog: requirements from the project's models (entities: their guids, as offered lists them), a
    deliverable of the project (item: its id), or an item by its title alone."""
    p = _project(pc, project, user, "contribute")
    added = []
    priority = int(d.get("priority") or 0)
    if d.get("entities"):
        offer = {o["entity"]: o for o in offered(pc, p["guid"], user)}
        for g in d["entities"]:
            o = offer.get(str(g))
            if not o:
                raise EditError(f"{g} is not a requirement, epic or feature in this project's models, or is in the backlog already.")
            added.append(_insert(pc, p, user, "requirement", o["name"], priority, model=o["model"], entity=o["entity"]))
    if d.get("item"):
        it = _one(pc, "SELECT id, name FROM proj.items WHERE project_id = :p AND id = :i", p=p["id"], i=int(d["item"]))
        if not it:
            raise EditError("No such deliverable in this project.", 404)
        if _items(pc, p, "AND b.item_id = :i", i=it["id"]):
            raise EditError(f"{it['name']} is in the backlog already.", 409)
        added.append(_insert(pc, p, user, "deliverable", it["name"], priority, item=it["id"]))
    if d.get("title"):
        added.append(_insert(pc, p, user, "item", _text(d["title"], 300), priority))
    if not added:
        raise EditError("Choose what to add: requirements from the models, a deliverable, or a title.")
    return {"added": added, "message": f"{len(added)} added to the backlog of {p['name']}."}


def _insert(pc, p: dict, user, kind: str, title: str, priority: int, model=None, entity=None, item=None) -> dict:
    r = _one(pc, """INSERT INTO proj.backlog_items (project_id, kind, model_guid, entity_guid, item_id, title, priority, added_by)
                    VALUES (:p, :k, CAST(:m AS uuid), CAST(:e AS uuid), :i, :t, :pr, :u) RETURNING *""",
             p=p["id"], k=kind, m=model, e=entity, i=item, t=title or "(untitled)", pr=priority, u=user.username)
    return _item_out(r)


def prioritise(pc, project: Any, user, item: str, priority: Any) -> dict:
    """Sets a backlog item's priority (higher comes first)."""
    p = _project(pc, project, user, "contribute")
    r = _one(pc, """UPDATE proj.backlog_items SET priority = :pr WHERE project_id = :p AND guid = CAST(:g AS uuid) RETURNING *""",
             p=p["id"], g=str(item), pr=int(priority))
    if not r:
        raise EditError("No such backlog item.", 404)
    return _item_out(r)


def remove_from_backlog(pc, project: Any, user, item: str) -> dict:
    """Takes an item out of the backlog (only while it waits in the backlog, never once a sprint has it)."""
    p = _project(pc, project, user, "contribute")
    r = _one(pc, """DELETE FROM proj.backlog_items WHERE project_id = :p AND guid = CAST(:g AS uuid) AND status = 'backlog'
                    RETURNING title""", p=p["id"], g=str(item))
    if not r:
        raise EditError("No such item waiting in the backlog (an item in a sprint stays until the review).", 404)
    return {"message": f"{r['title']} taken out of the backlog."}


# ---------------------------------------------------------------- sprints
def _sprint_out(pc, s: dict) -> dict:
    items = _rows(pc, """SELECT b.*, d.accepted, d.note AS decision_note, d.accepted_by FROM proj.backlog_items b
                           LEFT JOIN proj.sprint_decisions d ON d.backlog_id = b.id AND d.sprint_id = :s
                          WHERE b.sprint_id = :s OR d.sprint_id = :s ORDER BY b.priority DESC, b.id""", s=s["id"])
    steps = list(s["steps"] or [])
    return {"id": str(s["guid"]), "seq": s["seq"], "name": s["name"] or f"Sprint {s['seq']}", "goal": s["goal"],
            "starts_on": s["starts_on"].isoformat(), "ends_on": s["ends_on"].isoformat(), "phases": list(s["phases"] or []),
            "steps": steps, "accepter": s["accepter"], "status": s["status"], "review_note": s["review_note"],
            "reviewed_by": s.get("reviewed_by"), "items": [{**_item_out(i), "accepted": i.get("accepted"),
                                                            "decision_note": i.get("decision_note") or ""} for i in items]}


def _sprint(pc, p: dict, sprint: Any) -> dict:
    s = _one(pc, "SELECT * FROM proj.sprints WHERE project_id = :p AND (guid::text = :g OR seq::text = :g)", p=p["id"], g=str(sprint))
    if not s:
        raise EditError("No such sprint.", 404)
    return s


def overview(pc, project: Any, user) -> dict:
    """The project's backlog, its sprints (newest first), the usual sprint length and what the models offer."""
    p = _project(pc, project, user)
    sprints = _rows(pc, "SELECT * FROM proj.sprints WHERE project_id = :p ORDER BY seq DESC", p=p["id"])
    backlog = [_item_out(r) for r in _items(pc, p, "AND b.status = 'backlog'")]
    done = sum(1 for _ in _items(pc, p, "AND b.status = 'accepted'"))
    return {"project": p["name"], "sprint_days": sprint_days(pc, p), "backlog": backlog, "accepted": done,
            "sprints": [_sprint_out(pc, s) for s in sprints], "offered": len(offered(pc, p["guid"], user)), "phases": list(PHASES)}


def plan(pc, project: Any, user, d: dict) -> dict:
    """A new sprint: its goal, its dates (from the usual length unless given), the ADM phases it runs, the steps and
    deliverables agreed, who accepts them, and the backlog items it picks."""
    p = _project(pc, project, user, "contribute")
    if _one(pc, "SELECT 1 AS x FROM proj.sprints WHERE project_id = :p AND status <> 'reviewed'", p=p["id"]):
        raise EditError("A sprint is still open in this project: review it first.", 409)
    seq = int(_one(pc, "SELECT coalesce(max(seq), 0) + 1 AS n FROM proj.sprints WHERE project_id = :p", p=p["id"])["n"])
    start = _date(d.get("starts_on") or date.today().isoformat(), "The start")
    end = _date(d["ends_on"], "The end") if d.get("ends_on") else start + timedelta(days=sprint_days(pc, p) - 1)
    if end < start:
        raise EditError("A sprint ends on or after the day it starts.")
    phases = [x for x in (d.get("phases") or []) if x in PHASES]
    if not phases:
        raise EditError(f"Agree the ADM phases the sprint runs: one or more of {', '.join(PHASES)}.")
    ids = [int(x) for x in d.get("steps") or []]
    steps = []
    if ids:
        found = _rows(pc, """SELECT id, phase, name FROM proj.steps WHERE project_id = :p AND id = ANY(CAST(:ids AS bigint[])) AND NOT removed
                              ORDER BY phase, seq""", p=p["id"], ids=ids)
        if {r["id"] for r in found} != set(ids):
            raise EditError("A step chosen is not one of this project's steps.")
        steps = [f"{r['phase']}: {r['name']}" for r in found]
    accepter = _text(d.get("accepter"), 200)
    if not accepter:
        raise EditError("Name who accepts the sprint's deliverables (D879: named per sprint).")
    s = _one(pc, """INSERT INTO proj.sprints (project_id, seq, name, goal, starts_on, ends_on, phases, steps, accepter, status, created_by)
                    VALUES (:p, :q, :n, :g, :a, :b, CAST(:ph AS text[]), CAST(:st AS text[]), :ac, 'open', :u) RETURNING *""",
             p=p["id"], q=seq, n=_text(d.get("name"), 200), g=_text(d.get("goal"), 2000), a=start, b=end, ph=phases, st=steps,
             ac=accepter, u=user.username)
    for it in d.get("deliverables") or []:          # a deliverable agreed for the sprint comes in through the backlog
        try:
            add_to_backlog(pc, p["guid"], user, {"item": it})
        except EditError as exc:
            if exc.status != 409:
                raise
    picks = [str(x) for x in d.get("items") or []]
    picks += [str(r["guid"]) for r in _items(pc, p, "AND b.status = 'backlog' AND b.item_id = ANY(CAST(:i AS bigint[]))",
                                             i=[int(x) for x in d.get("deliverables") or []])]
    taken = 0
    for g in dict.fromkeys(picks):
        r = _one(pc, """UPDATE proj.backlog_items SET status = 'planned', sprint_id = :s
                         WHERE project_id = :p AND guid = CAST(:g AS uuid) AND status = 'backlog' RETURNING id""",
                 s=s["id"], p=p["id"], g=g)
        if not r:
            raise EditError("An item picked is not waiting in the backlog.")
        taken += 1
    if not taken:
        raise EditError("Pick at least one backlog item or deliverable for the sprint.")
    return {**_sprint_out(pc, s), "message": f"Sprint {seq} planned: {taken} item(s), phases {', '.join(phases)}, "
                                             f"{start.isoformat()} to {end.isoformat()}, accepted by {accepter}."}


def change_dates(pc, project: Any, user, sprint: Any, starts_on: Any = None, ends_on: Any = None) -> dict:
    """A sprint's own dates, while it is open."""
    p = _project(pc, project, user, "contribute")
    s = _sprint(pc, p, sprint)
    if s["status"] == "reviewed":
        raise EditError("A reviewed sprint keeps its dates.", 409)
    a = _date(starts_on, "The start") if starts_on else s["starts_on"]
    b = _date(ends_on, "The end") if ends_on else s["ends_on"]
    if b < a:
        raise EditError("A sprint ends on or after the day it starts.")
    s = _one(pc, "UPDATE proj.sprints SET starts_on = :a, ends_on = :b WHERE id = :s RETURNING *", a=a, b=b, s=s["id"])
    return _sprint_out(pc, s)


def _may_accept(pc, p: dict, user, s: dict) -> None:
    """The sprint's accepter decides; when the accepter is a member of the project (by username), only they or a
    project admin may record the decisions; a named person outside the application is recorded by a contributor."""
    members = {r["u"] for r in _rows(pc, "SELECT lower(username) AS u FROM proj.members WHERE project_id = :p", p=p["id"])}
    who = s["accepter"].strip().lower()
    if who in members and user.username.lower() != who:
        pj._need(pc, p, user, "admin")


def review(pc, project: Any, user, sprint: Any, decisions: dict, note: str = "") -> dict:
    """The sprint review: each of its items accepted or not ({item: true|false} or {item: {accepted, note}}). Every
    item needs a decision. Accepted items are done; the others go back to the backlog."""
    p = _project(pc, project, user, "contribute")
    s = _sprint(pc, p, sprint)
    if s["status"] == "reviewed":
        raise EditError(f"Sprint {s['seq']} was reviewed already.", 409)
    _may_accept(pc, p, user, s)
    items = _rows(pc, "SELECT * FROM proj.backlog_items WHERE sprint_id = :s", s=s["id"])
    want = {str(k): (v if isinstance(v, dict) else {"accepted": v}) for k, v in (decisions or {}).items()}
    missing = [i["title"] for i in items if str(i["guid"]) not in want]
    if missing:
        raise EditError("Decide every item of the sprint: " + "; ".join(missing[:5]) + ("..." if len(missing) > 5 else ""))
    yes = back = 0
    for i in items:
        dec = want[str(i["guid"])]
        ok = bool(dec.get("accepted"))
        pc.execute(text("""INSERT INTO proj.sprint_decisions (sprint_id, backlog_id, accepted, note, accepted_by, decided_by)
                           VALUES (:s, :b, :a, :n, :ac, :u)"""),
                   {"s": s["id"], "b": i["id"], "a": ok, "n": _text(dec.get("note"), 1000), "ac": s["accepter"], "u": user.username})
        if ok:
            pc.execute(text("UPDATE proj.backlog_items SET status = 'accepted' WHERE id = :b"), {"b": i["id"]})
            yes += 1
        else:
            pc.execute(text("""UPDATE proj.backlog_items SET status = 'backlog', sprint_id = NULL, returned = returned + 1
                               WHERE id = :b"""), {"b": i["id"]})
            back += 1
    s = _one(pc, """UPDATE proj.sprints SET status = 'reviewed', review_note = :n, reviewed_by = :u, reviewed_at = now()
                     WHERE id = :s RETURNING *""", n=_text(note, 2000), u=user.username, s=s["id"])
    return {**_sprint_out(pc, s), "message": f"Sprint {s['seq']} reviewed: {yes} accepted, {back} back to the backlog."}


def count(pc, p: dict) -> dict | None:
    """For the project page: the sprints and the backlog in numbers, for an Agile project (None for any other)."""
    if not is_agile(p):
        return None
    r = _one(pc, """SELECT (SELECT count(*) FROM proj.sprints WHERE project_id = :p) AS sprints,
                           (SELECT count(*) FROM proj.backlog_items WHERE project_id = :p AND status = 'backlog') AS backlog,
                           (SELECT count(*) FROM proj.backlog_items WHERE project_id = :p AND status = 'accepted') AS accepted""",
             p=p["id"])
    return {"sprints": int(r["sprints"]), "backlog": int(r["backlog"]), "accepted": int(r["accepted"])}
