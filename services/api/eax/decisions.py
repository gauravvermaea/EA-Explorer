"""Architecture decision records and dispensations (R5.5.1; owner, 15 Nov 2026, 18:20, with a feature specification;
agreed 20:31 to 20:34). They are governance records (eax/governance.py: the kinds "Architecture Decision Record" and
"Dispensation", numbered per year across the organisation, ADR-2026-001 and DISP-2026-001); this module adds:

  TEMPLATES          the two forms "as written" in the specification: each field, which are required
  links              both ways: a record to model elements, principles, standards, requirements and other records
                     (supersedes, depends on), and an element's "Linked decisions and dispensations"
  the organisation's own Governance Log   records with no project; the Architecture Board (a global role,
                     eax-architecture-board) accepts or rejects them; in a project its sign-off people do (as today)
  ending             a dispensation is warned of 30 days before its end (a setting) and on the end date it becomes
                     Expired, with a notice needing action to its owner, its sponsor, the project's Project Admins
                     and Lead Architects and the Architecture Board (the daily governance job; nothing in the database)
  the report         the rows of rpt.v_governance_decisions (copied by the same job, test data left out) and the
                     governance OData feed

Rows only (D248). Every change keeps its history in proj.gov_history as the rest of the governance log does.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from . import governance as gv
from . import projects as pj
from .metamodel_edit import EditError

_rows, _one = pj._rows, pj._one
ADR, DISP = "Architecture Decision Record", "Dispensation"
BOARD = "architecture-board"
WARN_DAYS = 30
ORG = {"id": None, "guid": None, "name": "Organisation", "status": "active"}

# the two templates, as written (owner, 20:34: "As written"): field, label, kind (text, long, list), required
TEMPLATES: dict[str, list[tuple[str, str, str, bool]]] = {
    ADR: [
        ("context", "Context and problem", "long", True),
        ("options", "Options considered, with their pros and cons", "long", True),
        ("decision", "The decision", "long", True),
        ("rationale", "Why", "long", True),
        ("consequences", "Consequences and trade-offs", "long", True),
    ],
    DISP: [
        ("waived", "The principle or standard waived", "text", True),
        ("systems", "The systems and projects it covers", "long", True),
        ("justification", "Justification", "long", True),
        ("impact", "Business impact", "long", False),
        ("risks", "Risks", "long", True),
        ("mitigations", "Mitigations", "long", False),
        ("remediation", "Remediation plan", "long", True),
    ],
}
# what else each template needs, outside its fields (the record's own columns)
NEEDS = {ADR: (("title", "a title"), ("record_type", "the record type"), ("owner", "its owner")),
         DISP: (("title", "a title"), ("owner", "its owner"), ("sponsor", "its sponsor"), ("expires_on", "its expiry date"))}
RECORD_TYPES = ("Architecture", "Business", "Data", "Application", "Technology", "Security", "Integration", "Other")
LINK_KINDS = ("element", "principle", "standard", "requirement", "record")
RELATIONS = {"element": ("affects",), "principle": ("governed-by",), "standard": ("governed-by",), "requirement": ("meets",),
             "record": ("supersedes", "depends-on")}


# ---------------------------------------------------------------- templates
def templates() -> dict:
    """The two forms, for the screens and the AI."""
    return {k: {"fields": [{"name": n, "label": lbl, "kind": kd, "required": req} for n, lbl, kd, req in v],
                "needs": [n for n, _w in NEEDS[k]]} for k, v in TEMPLATES.items()} | {"record_types": list(RECORD_TYPES),
                                                                                     "phases": list(gv.PHASES)}


def clean_fields(kind: str, fields: Any) -> dict:
    """A record's template fields: only the template's own, as text (other kinds keep none)."""
    if isinstance(fields, str):
        try:
            fields = json.loads(fields or "{}")
        except ValueError:
            fields = {}
    fields = fields if isinstance(fields, dict) else {}
    names = {n for n, _l, _k, _r in TEMPLATES.get(kind, [])}
    return {k: str(v).strip()[:8000] for k, v in fields.items() if k in names and v not in (None, "")}


def check_required(kind: str, rec: dict) -> None:
    """Refuses a record proposed or accepted without what its template requires, saying what is missing."""
    fields = clean_fields(kind, rec.get("fields"))
    missing = [lbl for n, lbl, _k, req in TEMPLATES.get(kind, []) if req and not fields.get(n)]
    missing += [what for col, what in NEEDS.get(kind, ()) if not rec.get(col)]
    if missing:
        k = kind.lower()
        raise EditError(f"{'An' if k[:1] in 'aeiou' else 'A'} {k} needs, before it is proposed: {', '.join(missing)}.")


# ---------------------------------------------------------------- the organisation's own Governance Log
def is_board(user) -> bool:
    """Whether the person accepts the organisation's records: the Architecture Board role, or a Super Admin."""
    roles = set(getattr(user, "roles", []) or [])
    return bool(roles & {BOARD, "super-admin"})


def board_members(core_conn) -> list[str]:
    """The Architecture Board's members: the people with the global role (known users)."""
    try:
        return [r["u"] for r in _rows(core_conn, "SELECT DISTINCT lower(username) AS u FROM core.known_users "
                                                 "WHERE roles && ARRAY['architecture-board'] ORDER BY 1")]
    except Exception:  # noqa: BLE001 - before the users are known
        return []


def _org_row(conn, rid: str) -> dict:
    try:
        uuid.UUID(str(rid))
    except ValueError as exc:
        raise EditError("No such record in the organisation's Governance Log.", 404) from exc
    r = _one(conn, "SELECT * FROM proj.gov_records WHERE project_id IS NULL AND guid = CAST(:g AS uuid)", g=rid)
    if not r:
        raise EditError("No such record in the organisation's Governance Log.", 404)
    return r


def _shape(r: dict) -> dict:
    out = dict(r)
    for k in ("raised_on", "expires_on", "warned_on", "ended_on"):
        if k in out:
            out[k] = str(out[k])[:10] if out[k] else ""
    for k in ("approved_at", "created_at", "modified_at"):
        if hasattr(out.get(k), "isoformat"):
            out[k] = out[k].isoformat()
    for k in ("fields", "found_in"):
        if isinstance(out.get(k), str):
            out[k] = json.loads(out[k])
    return out


def org_listing(conn, user) -> dict:
    """The organisation's own Governance Log: its ADRs and dispensations (everyone signed in reads it)."""
    rows = _rows(conn, """SELECT g.guid::text AS id, g.kind, g.ref, g.title, g.html, g.status, g.owner, g.sponsor, g.raised_on,
                                 g.expires_on, g.phase, g.record_type, g.fields, g.found_in, g.approval, g.approved_by,
                                 g.approved_at, g.approval_note, g.created_by,
                                 coalesce(g.modified_by, g.created_by) AS modified_by,
                                 (SELECT count(*) FROM proj.gov_links l WHERE l.record_id = g.id) AS links
                            FROM proj.gov_records g WHERE g.project_id IS NULL ORDER BY g.raised_on DESC, g.id DESC""")
    out = [_shape(r) for r in rows]
    today = date.today().isoformat()
    for r in out:
        r["overdue"] = bool(r["expires_on"] and r["expires_on"] < today)
    return {"records": out, "kinds": [k for k in gv.kinds(conn, ORG) if k["name"] in (ADR, DISP)],
            "may_edit": is_board(user), "may_accept": is_board(user), "templates": templates()}


def org_add(conn, user, d: dict) -> dict:
    """A record in the organisation's own Governance Log (the Architecture Board or a Super Admin)."""
    if not is_board(user) and not d.get("_ai"):
        raise EditError("Only the Architecture Board (or a Super Admin) adds to the organisation's Governance Log.", 403)
    if d.get("kind") not in (ADR, DISP):
        raise EditError("The organisation's Governance Log holds architecture decision records and dispensations.")
    v = gv._vals(conn, ORG, d)
    ref = gv.yearly_ref(conn, v["prefix"], v["raised_on"])
    g = conn.execute(text("""INSERT INTO proj.gov_records (project_id, kind, ref, title, html, status, owner, raised_on, expires_on,
                                                           related, created_by, phase, record_type, sponsor, fields, found_in)
                             VALUES (NULL, :kind, :ref, :title, :html, :status, :owner, :raised_on, :expires_on, :related, :u,
                                     :phase, :record_type, :sponsor, CAST(:fields AS jsonb), CAST(:found_in AS jsonb))
                             RETURNING guid::text"""),
                     {**v, "ref": ref, "u": user.username, "found_in": json.dumps(d["found_in"]) if d.get("found_in") else None}).scalar()
    gv._history(conn, _org_row(conn, g), user, "logged")
    return {"id": g, "ref": ref, "message": f"{ref} {v['title']} logged in the organisation's Governance Log."}


def org_update(conn, user, rid: str, d: dict) -> dict:
    """Changes a record of the organisation's Governance Log; an accepted one is a draft again (its history kept)."""
    if not is_board(user) and not d.get("_ai"):
        raise EditError("Only the Architecture Board (or a Super Admin) changes the organisation's Governance Log.", 403)
    r = _org_row(conn, rid)
    base = {k: r[k] for k in ("kind", "title", "html", "status", "owner", "raised_on", "expires_on", "related", "phase",
                              "record_type", "sponsor", "fields")}
    v = gv._vals(conn, ORG, {**base, **d, "kind": r["kind"]})
    conn.execute(text("""UPDATE proj.gov_records SET title = :title, html = :html, status = :status, owner = :owner,
                                raised_on = :raised_on, expires_on = :expires_on, related = :related, phase = :phase,
                                record_type = :record_type, sponsor = :sponsor, fields = CAST(:fields AS jsonb),
                                warned_on = CASE WHEN expires_on IS DISTINCT FROM :expires_on THEN NULL ELSE warned_on END,
                                ended_on = CASE WHEN expires_on IS DISTINCT FROM :expires_on THEN NULL ELSE ended_on END,
                                found_in = coalesce(CAST(:found_in AS jsonb), found_in),
                                modified_by = :u, modified_at = now() WHERE id = :i"""),
                 {**v, "u": user.username, "i": r["id"], "found_in": json.dumps(d["found_in"]) if d.get("found_in") else None})
    gv._history(conn, r, user, "changed", "", snapshot=True)
    return {"id": rid, "message": f"{r['ref']} saved."}


def org_decide(conn, user, rid: str, decision: str, comment: str = "") -> dict:
    """The Architecture Board accepts or rejects a record of the organisation's Governance Log (a rejection says why)."""
    from . import notify
    if not is_board(user):
        raise EditError("Only the Architecture Board (or a Super Admin) accepts or rejects these.", 403)
    r = _org_row(conn, rid)
    if decision not in ("approved", "rejected"):
        raise EditError("Accept or reject.")
    if decision == "rejected" and not (comment or "").strip():
        raise EditError("Say why it is rejected.")
    if decision == "approved":
        check_required(r["kind"], {**r, "fields": r.get("fields") or {}})
    word, status = ("Approved", "Accepted") if decision == "approved" else ("Rejected", "Rejected")
    conn.execute(text("""UPDATE proj.gov_records SET approval = :w, status = :s,
                                approved_by = CASE WHEN :w = 'Approved' THEN :u ELSE NULL END,
                                approved_at = CASE WHEN :w = 'Approved' THEN now() ELSE NULL END, approval_note = :n
                          WHERE id = :i"""),
                 {"w": word, "s": status, "u": user.username, "n": (comment or "").strip(), "i": r["id"]})
    gv._history(conn, {**r, "approval": word, "status": status}, user, f"{status.lower()} by the Architecture Board",
                comment or "", snapshot=True)
    notify.create(pj.core(conn), kind=f"governance.{status.lower()}", category="request", actor=user.username,
                  title=f"{r['ref']} {r['title']} is {status.lower()}",
                  body=f"The Architecture Board ({user.username}) {status.lower()} it.{(' ' + comment) if comment else ''}",
                  link="#/governance", recipients=[x for x in (r["owner"], r["created_by"], r["sponsor"]) if x],
                  include_actor=False)
    return {"message": f"{r['ref']} {status.lower()}."}


def org_history(conn, user, rid: str) -> dict:
    """A record's history in the organisation's Governance Log: each change, link and decision, newest first."""
    r = _org_row(conn, rid)
    rows = _rows(conn, "SELECT at, by_user, action, note, snapshot FROM proj.gov_history WHERE record_id = :r ORDER BY at DESC, id DESC",
                 r=r["id"])
    for x in rows:
        x["at"] = x["at"].isoformat() if hasattr(x["at"], "isoformat") else x["at"]
        if isinstance(x["snapshot"], str):
            x["snapshot"] = json.loads(x["snapshot"])
    return {"ref": r["ref"], "title": r["title"], "history": rows}


# ---------------------------------------------------------------- finding a record, wherever it is
def record(conn, user, rid: str, write: bool = False) -> tuple[dict, dict]:
    """(the record, its project or ORG), checking the person may read it (or change it, write)."""
    try:
        uuid.UUID(str(rid))
    except ValueError as exc:
        raise EditError("No such governance record.", 404) from exc
    r = _one(conn, "SELECT * FROM proj.gov_records WHERE guid = CAST(:g AS uuid)", g=rid)
    if not r:
        raise EditError("No such governance record.", 404)
    if r["project_id"] is None:
        if write and not is_board(user):
            raise EditError("Only the Architecture Board (or a Super Admin) changes the organisation's Governance Log.", 403)
        return r, ORG
    p = _one(conn, "SELECT * FROM proj.projects WHERE id = :i", i=r["project_id"])
    pj._need(conn, p, user, "contribute" if write else "read")
    return r, p


# ---------------------------------------------------------------- links both ways
def _element(core_conn, model: str, element: str) -> dict:
    try:
        uuid.UUID(str(model))
        uuid.UUID(str(element))
    except ValueError as exc:
        raise EditError("An element is linked by its model's and its own id.", 400) from exc
    e = _one(core_conn, """SELECT e.guid::text AS id, e.name, t.name AS type, m.guid::text AS model, m.name AS model_name
                             FROM core.entities e JOIN core.models m ON m.id = e.model_id
                             JOIN core.entity_types t ON t.id = e.entity_type_id
                            WHERE m.guid = CAST(:m AS uuid) AND e.guid = CAST(:e AS uuid) AND NOT e.is_deleted""",
             m=model, e=element)
    if not e:
        raise EditError("No such element in that model (or you may not read it).", 404)
    return e


def _target_label(conn, kind: str, target: str, p: dict, model: str | None) -> tuple[str, str | None]:
    """The linked thing's name (and an element's model), checking it is there. A stakeholder requirement is an element
    of a model (a Requirement), linked with its model as an element is."""
    if kind in ("element", "requirement"):
        e = _element(pj.core(conn), model or "", target)
        return f"{e['name']} ({e['type']}, {e['model_name']})", e["model"]
    try:
        uuid.UUID(str(target))
    except ValueError as exc:
        raise EditError(f"A {kind} is linked by its id.", 400) from exc
    sql = {"record": "SELECT ref || ' ' || title AS name FROM proj.gov_records WHERE guid = CAST(:g AS uuid)",
           "principle": "SELECT name FROM proj.principles WHERE guid = CAST(:g AS uuid)",
           "standard": "SELECT name FROM proj.standards WHERE guid = CAST(:g AS uuid)"}[kind]
    x = _one(conn, sql, g=target)
    if not x:
        raise EditError(f"No such {kind}.", 404)
    return x["name"], None


def add_link(conn, user, rid: str, d: dict) -> dict:
    """Links a record to an element, principle, standard, requirement or another record (supersedes, depends on)."""
    r, p = record(conn, user, rid, write=True)
    kind = (d.get("kind") or "").strip()
    if kind not in LINK_KINDS:
        raise EditError(f"A link is to one of: {', '.join(LINK_KINDS)}.")
    relation = (d.get("relation") or RELATIONS[kind][0]).strip()
    if relation not in RELATIONS[kind]:
        raise EditError(f"A link to a {kind} is: {', '.join(RELATIONS[kind])}.")
    target = str(d.get("target") or "").strip()
    if kind == "record" and target == str(r["guid"]):
        raise EditError("A record cannot be linked to itself.")
    label, model = _target_label(conn, kind, target, p, d.get("model"))
    conn.execute(text("""INSERT INTO proj.gov_links (record_id, link_kind, relation, target, model_guid, label, created_by)
                         VALUES (:r, :k, :rel, :t, CAST(:m AS uuid), :l, :u)
                         ON CONFLICT (record_id, link_kind, relation, target) DO NOTHING"""),
                 {"r": r["id"], "k": kind, "rel": relation, "t": target, "m": model, "l": label[:300], "u": user.username})
    if kind == "record" and relation == "supersedes":   # the older record is superseded by this one
        conn.execute(text("""UPDATE proj.gov_records SET status = 'Superseded', modified_by = :u, modified_at = now()
                              WHERE guid = CAST(:g AS uuid) AND kind = :k AND status = 'Accepted'"""),
                     {"g": target, "k": ADR, "u": user.username})
    gv._history(conn, r, user, "linked", f"{relation} {kind}: {label}")
    return {"message": f"{r['ref']} {relation.replace('-', ' ')} {label}."}


def remove_link(conn, user, rid: str, link_id: int) -> dict:
    """Removes one of a record's links (whoever may change the record), the history saying which."""
    r, _p = record(conn, user, rid, write=True)
    x = _one(conn, "DELETE FROM proj.gov_links WHERE id = :i AND record_id = :r RETURNING link_kind, relation, label",
             i=int(link_id), r=r["id"])
    if not x:
        raise EditError("No such link.", 404)
    gv._history(conn, r, user, "unlinked", f"{x['relation']} {x['link_kind']}: {x['label']}")
    return {"message": "Link removed."}


def links(conn, user, rid: str) -> dict:
    """A record's links both ways: what it links to, and the records that link to it (superseded by, depended on by)."""
    r, _p = record(conn, user, rid)
    out = _rows(conn, """SELECT id, link_kind AS kind, relation, target, model_guid::text AS model, label, created_by
                           FROM proj.gov_links WHERE record_id = :r ORDER BY link_kind, label""", r=r["id"])
    back = _rows(conn, """SELECT l.relation, g.guid::text AS id, g.ref, g.title, g.status
                            FROM proj.gov_links l JOIN proj.gov_records g ON g.id = l.record_id
                           WHERE l.link_kind = 'record' AND l.target = :t""", t=str(r["guid"]))
    for b in back:
        b["relation"] = {"supersedes": "superseded-by", "depends-on": "depended-on-by"}.get(b["relation"], b["relation"])
    return {"ref": r["ref"], "links": out, "linked_from": back}


def for_element(conn, user, model: str, element: str) -> dict:
    """An element's "Linked decisions and dispensations" tab: the records that affect it which the person may read, the
    active ones first and the waivers coming to an end marked."""
    _element(pj.core(conn), model, element)        # the person may read the element
    rows = _rows(conn, """SELECT g.guid::text AS id, g.kind, g.ref, g.title, g.status, g.approval, g.expires_on, g.project_id,
                                 p.guid::text AS project, p.name AS project_name, l.relation
                            FROM proj.gov_links l JOIN proj.gov_records g ON g.id = l.record_id
                            LEFT JOIN proj.projects p ON p.id = g.project_id
                           WHERE l.link_kind IN ('element', 'requirement') AND l.target = :e""", e=element)
    out, warn = [], _warn_days()
    today = date.today()
    seen_projects: dict[int, bool] = {}
    for r in rows:
        pid = r.pop("project_id")
        if pid is not None:
            if pid not in seen_projects:
                p = _one(conn, "SELECT * FROM proj.projects WHERE id = :i", i=pid)
                seen_projects[pid] = gv._may(conn, p, user, "read")
            if not seen_projects[pid]:
                continue
        exp = r["expires_on"]
        r["expires_on"] = str(exp)[:10] if exp else ""
        r["active"] = r["status"] == "Accepted"
        r["ending_soon"] = bool(r["kind"] == DISP and r["active"] and exp and today <= exp <= today + timedelta(days=warn))
        r["project_name"] = r["project_name"] or "Organisation"
        out.append(r)
    out.sort(key=lambda x: (not x["active"], not x["ending_soon"], x["ref"]))
    return {"records": out}


# ---------------------------------------------------------------- ending dispensations (the daily governance job)
def _warn_days() -> int:
    try:
        from . import settings as st
        return int(st.values().get("gov_dispensation_warn_days") or WARN_DAYS)
    except Exception:  # noqa: BLE001 - the default
        return WARN_DAYS


def _told(conn, r: dict) -> list[str]:
    """Who is told about a dispensation ending: its owner, its sponsor, the project's Project Admins and Lead
    Architects (or none, the organisation's) and the Architecture Board."""
    people = {x for x in (r.get("owner"), r.get("sponsor"), r.get("created_by")) if x}
    if r.get("project_id") is not None:
        people |= {x["u"] for x in _rows(conn, """SELECT lower(username) AS u FROM proj.members
                                                  WHERE project_id = :p AND role IN ('project-admin', 'lead-architect')""",
                                         p=r["project_id"])}
    people |= set(board_members(pj.core(conn)))
    return sorted(p.lower() for p in people if p)


def run_ending(conn, today: date | None = None) -> dict:
    """Dispensations accepted with an end: warned once, the setting's days before (30); on and after the end date,
    Expired with a notice needing action, once (owner, 20:32: "30 days before and on the day")."""
    from . import notify
    today = today or date.today()
    warn = _warn_days()
    warned, ended = [], []
    for r in _rows(conn, """SELECT g.*, p.guid::text AS project_guid, p.name AS project_name FROM proj.gov_records g
                              LEFT JOIN proj.projects p ON p.id = g.project_id
                             WHERE g.kind = :k AND g.status = 'Accepted' AND g.expires_on IS NOT NULL
                               AND (g.ended_on IS NULL OR g.warned_on IS NULL)""", k=DISP):
        where = f"project {r['project_name']}" if r["project_id"] is not None else "the organisation's Governance Log"
        link = f"#/projects/{r['project_guid']}/governance?kind={DISP}" if r["project_id"] is not None else "#/governance"
        if r["expires_on"] <= today and r["ended_on"] is None:
            conn.execute(text("""UPDATE proj.gov_records SET status = 'Expired', ended_on = :d, modified_by = 'system',
                                        modified_at = now() WHERE id = :i"""), {"d": today, "i": r["id"]})
            conn.execute(text("""INSERT INTO proj.gov_history (record_id, by_user, action, note)
                                 VALUES (:r, 'system', 'expired', :n)"""), {"r": r["id"], "n": f"ended on {r['expires_on']}"})
            notify.create(pj.core(conn), kind="governance.dispensation_ended", category="request", actor="system",
                          title=f"{r['ref']} {r['title']} has ended", needs_action=True, link=link,
                          body=f"The dispensation in {where} ended on {r['expires_on']} and is now Expired: remediate, "
                               "close it, or raise a new one.", recipients=_told(conn, r))
            ended.append(r["ref"])
        elif r["warned_on"] is None and today < r["expires_on"] <= today + timedelta(days=warn):
            conn.execute(text("UPDATE proj.gov_records SET warned_on = :d WHERE id = :i"), {"d": today, "i": r["id"]})
            days = (r["expires_on"] - today).days
            notify.create(pj.core(conn), kind="governance.dispensation_ending", category="request", actor="system",
                          title=f"{r['ref']} {r['title']} ends in {days} day{'s' if days != 1 else ''}", link=link,
                          body=f"The dispensation in {where} ends on {r['expires_on']}: plan its remediation or a renewal.",
                          recipients=_told(conn, r))
            warned.append(r["ref"])
    return {"warned": warned, "ended": ended}


def ending_soon(conn, user) -> list[dict]:
    """The accepted dispensations ending within the setting's days that the person may read (the governance dashboard)."""
    today, warn = date.today(), _warn_days()
    out = []
    for r in _rows(conn, """SELECT g.guid::text AS id, g.ref, g.title, g.expires_on, g.project_id, p.guid::text AS project,
                                   p.name AS project_name FROM proj.gov_records g LEFT JOIN proj.projects p ON p.id = g.project_id
                             WHERE g.kind = :k AND g.status = 'Accepted' AND g.expires_on BETWEEN :a AND :b
                             ORDER BY g.expires_on""", k=DISP, a=today, b=today + timedelta(days=warn)):
        if r["project_id"] is not None:
            p = _one(conn, "SELECT * FROM proj.projects WHERE id = :i", i=r["project_id"])
            if not gv._may(conn, p, user, "read"):
                continue
        r.pop("project_id")
        r["days_left"] = (r["expires_on"] - today).days
        r["expires_on"] = str(r["expires_on"])
        r["project_name"] = r["project_name"] or "Organisation"
        out.append(r)
    return out


# ---------------------------------------------------------------- the report's rows (the governance job)
def refresh_report(conn, today: date | None = None) -> int:
    """Copies every ADR and dispensation into core.governance_report (rpt.v_governance_decisions reads it), leaving out
    the self-test's projects and records; the repository's database is where Reports reads, whatever database holds the projects."""
    today = today or date.today()
    warn = _warn_days()
    rows = _rows(conn, """SELECT g.guid::text AS record_guid, g.ref, g.kind, g.title, g.status, g.approval,
                                 p.guid::text AS project_guid, coalesce(p.name, '') AS project_name, g.phase, g.owner, g.sponsor,
                                 g.raised_on, g.expires_on,
                                 (SELECT count(*) FROM proj.gov_links l WHERE l.record_id = g.id AND l.link_kind = 'element')
                                     AS linked_elements
                            FROM proj.gov_records g LEFT JOIN proj.projects p ON p.id = g.project_id
                           WHERE g.kind = ANY(:k) AND (p.id IS NULL OR p.name NOT LIKE 'self\\_test\\_%')
                             AND g.title NOT LIKE 'self\\_test\\_%'""",
                   k=[ADR, DISP, "Decision"])
    core = pj.core(conn)
    core.execute(text("DELETE FROM core.governance_report"))
    for r in rows:
        exp = r["expires_on"]
        r["days_left"] = (exp - today).days if (exp and r["kind"] == DISP) else None
        r["ending_soon"] = bool(r["kind"] == DISP and r["status"] == "Accepted" and exp and today <= exp <= today + timedelta(days=warn))
        core.execute(text("""INSERT INTO core.governance_report (record_guid, ref, kind, title, status, approval, project_guid,
                                 project_name, phase, owner, sponsor, raised_on, expires_on, days_left, ending_soon, linked_elements)
                             VALUES (CAST(:record_guid AS uuid), :ref, :kind, :title, :status, coalesce(:approval, ''),
                                     CAST(:project_guid AS uuid), :project_name, :phase, :owner, :sponsor, :raised_on, :expires_on,
                                     :days_left, :ending_soon, :linked_elements)"""), r)
    return len(rows)


def report_rows(conn, user) -> list[dict]:
    """The governance report as the person may read it (the OData feed and the screens' report): every ADR, decision
    and dispensation of the projects they may read and of the organisation."""
    today, warn = date.today(), _warn_days()
    out, may = [], {}
    for r in _rows(conn, """SELECT g.guid::text AS "Id", g.ref AS "Ref", g.kind AS "Kind", g.title AS "Title",
                                   g.status AS "Status", coalesce(g.approval, '') AS "Approval", g.project_id,
                                   coalesce(p.name, 'Organisation') AS "Project", g.phase AS "Phase", g.owner AS "Owner",
                                   g.sponsor AS "Sponsor", g.raised_on AS "RaisedOn", g.expires_on AS "ExpiresOn"
                              FROM proj.gov_records g LEFT JOIN proj.projects p ON p.id = g.project_id
                             WHERE g.kind = ANY(:k) AND (p.id IS NULL OR p.name NOT LIKE 'self\\_test\\_%')
                               AND g.title NOT LIKE 'self\\_test\\_%'
                             ORDER BY g.raised_on DESC, g.id DESC""", k=[ADR, DISP, "Decision"]):
        pid = r.pop("project_id")
        if pid is not None:
            if pid not in may:
                may[pid] = gv._may(conn, _one(conn, "SELECT * FROM proj.projects WHERE id = :i", i=pid), user, "read")
            if not may[pid]:
                continue
        exp = r["ExpiresOn"]
        r["DaysLeft"] = (exp - today).days if (exp and r["Kind"] == DISP) else None
        r["EndingSoon"] = bool(r["Kind"] == DISP and r["Status"] == "Accepted" and exp and today <= exp <= today + timedelta(days=warn))
        out.append(r)
    return out


REPORT_COLUMNS = [("Id", "Edm.Guid"), ("Ref", "Edm.String"), ("Kind", "Edm.String"), ("Title", "Edm.String"),
                  ("Status", "Edm.String"), ("Approval", "Edm.String"), ("Project", "Edm.String"), ("Phase", "Edm.String"),
                  ("Owner", "Edm.String"), ("Sponsor", "Edm.String"), ("RaisedOn", "Edm.Date"), ("ExpiresOn", "Edm.Date"),
                  ("DaysLeft", "Edm.Int64"), ("EndingSoon", "Edm.Boolean")]


def summary(rows: list[dict]) -> dict:
    """The standard governance report (pure): decisions by status and project, active dispensations by expiry date with
    those ending soon marked."""
    by_status: dict[str, int] = {}
    by_project: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["Kind"] == DISP:
            continue
        by_status[r["Status"]] = by_status.get(r["Status"], 0) + 1
        by_project.setdefault(r["Project"], {})[r["Status"]] = by_project.setdefault(r["Project"], {}).get(r["Status"], 0) + 1
    active = sorted([r for r in rows if r["Kind"] == DISP and r["Status"] == "Accepted"],
                    key=lambda r: (r["ExpiresOn"] is None, r["ExpiresOn"] or date.max))
    return {"decisions_by_status": by_status, "decisions_by_project": by_project,
            "active_dispensations": [{k: (str(v) if isinstance(v, date) else v) for k, v in r.items()} for r in active],
            "ending_soon": sum(1 for r in active if r["EndingSoon"])}
