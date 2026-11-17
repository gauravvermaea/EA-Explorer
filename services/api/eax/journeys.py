"""Customer journey maps in a project (R5.7-J1, D730; owner, 16 Nov 2026, from 15:58, and 17 Nov 13:50): first-class,
free-standing from the models like the Business Model Canvas (eax/canvases.py), on a Customer journeys tab beside it.

    a journey        its stages (columns) and, under each stage, its parts: steps (each with the emotion there, -2 to
                     +2), touchpoints, pain points, moments that matter and opportunities; personas for the whole
                     journey; kinds of part a project adds itself, with fields of its own (standard kinds may get extra
                     fields too). A project has any number: current state, target state, working copy or scenario;
                     draft or agreed
    links            a stage or a part links out to model elements of the project's models (capabilities, value
                     streams, business services, applications, data, actors and roles, or any other); the element's
                     name is kept with the link, so the journey reads even when the model is not at hand
    lineage          a stage and a part keep their lineage in every copy, so two journeys compare stage by stage and
                     part by part: added, changed (the old text and emotion kept), removed
    starter          a new journey starts blank or from the starter template's typical stages
    export           PDF, PowerPoint and draw.io (the drawn view for presentations), of a journey or of a comparison
    documents        what was used to build it (interviews, research): uploaded with it or a document of the project

Anyone on the project reads them; contributors change them; a change to an agreed journey makes it a draft again.
Every change is kept (journey_events). An opportunity is never turned into a requirement or work package by itself.
Rules are here, never in the database (D248).
"""

from __future__ import annotations

import io
import json
import re
import textwrap
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import text

from . import blank_files as bf
from . import project_work as pw
from . import projects as pj
from .metamodel_edit import EditError

_rows, _one = pj._rows, pj._one

# (code, label, what it holds: our own words)
PARTS = [
    ("step", "Steps", "What the person does at this stage"),
    ("touchpoint", "Touchpoints", "Where they meet us: a channel, a screen, a person, a letter"),
    ("pain_point", "Pain points", "What goes wrong or frustrates them"),
    ("moment", "Moments that matter", "Where the experience is won or lost"),
    ("opportunity", "Opportunities", "What we could do better (it may become a requirement or a work package)"),
]
PART_CODES = [p[0] for p in PARTS]
PERSONA = "persona"                     # for the whole journey, not a stage
KINDS = {"current": "Current state", "target": "Target state", "working": "Working copy", "scenario": "Scenario"}
STATUSES = {"draft": "Draft", "agreed": "Agreed"}
# the emotion at a step (owner, 17 Nov 2026, 13:50): -2 to +2 with faces, zero the line
FACES = {-2: ("😣", "Very unhappy"), -1: ("🙁", "Unhappy"), 0: ("😐", "Neutral"), 1: ("🙂", "Happy"), 2: ("😄", "Very happy")}
# the starter template (owner, 13:51): the typical stages people start from
STARTER = [("Become aware", "How they first hear of us"), ("Consider", "Compare, ask, decide"),
           ("Join or buy", "Sign up, pay, get started"), ("Use", "Everyday use of what they have"),
           ("Get help", "A question, a problem, a claim"), ("Stay or leave", "Renew, recommend, or go")]
TEMPLATES = {"blank": "Blank: no stages", "starter": "Starter: " + ", ".join(s for s, _ in STARTER)}
CODE = re.compile(r"^x-[a-z0-9][a-z0-9-]{0,38}$")
# the usual elements for a journey (owner, 16:00: capabilities, value streams, business services, applications, data,
# actors and roles), by type code in both metamodels (TOGAF and ArchiMate); "all" finds any type
LINK_TYPES = ["Capability", "ValueStream", "ValueStreamStage", "BusinessService", "Service", "Process", "Product",
              "ApplicationComponent", "LogicalApplicationComponent", "PhysicalApplicationComponent", "ApplicationService",
              "DataObject", "DataEntity", "BusinessObject", "BusinessActor", "Actor", "Role"]


def _clean(s: Any, n: int = 2000) -> str:
    return " ".join(str(s or "").split())[:n] if n <= 300 else str(s or "").strip()[:n]


def _score(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        n = int(v)
        if isinstance(v, float) and v != n:
            raise ValueError(v)
    except (TypeError, ValueError) as exc:
        raise EditError("The emotion is a whole number from -2 (very unhappy) to +2 (very happy).") from exc
    if n not in FACES:
        raise EditError("The emotion is from -2 (very unhappy) to +2 (very happy).")
    return n


# ---------------------------------------------------------------- the project's own kinds of part
def part_kinds(conn, p: dict) -> list[dict]:
    """The standard kinds (with any extra fields the project gave them) and the project's own."""
    own = {r["code"]: r for r in _rows(conn, """SELECT code, label, fields, note FROM proj.journey_part_kinds
                                                 WHERE project_id = :p ORDER BY sort_order, label""", p=p["id"])}
    out = [{"code": c, "label": label, "help": h, "standard": True, "fields": list((own.get(c) or {}).get("fields") or [])}
           for c, label, h in PARTS]
    out += [{"code": c, "label": r["label"], "help": r["note"], "standard": False, "fields": list(r["fields"] or [])}
            for c, r in own.items() if c not in PART_CODES]
    return out


def _codes(conn, p: dict) -> dict[str, dict]:
    return {k["code"]: k for k in part_kinds(conn, p)}


def set_part_kind(conn, project: Any, user, data: dict) -> dict:
    """A kind of part of the project's own {label, fields, note} (its code made from the label), or extra fields on a
    standard kind {code: step | touchpoint | ..., fields}."""
    p = _project(conn, project, user, "contribute")
    fields = [_clean(f, 60) for f in (data.get("fields") or []) if _clean(f, 60)]
    if len({f.lower() for f in fields}) != len(fields) or len(fields) > 12:
        raise EditError("At most 12 fields, each named once.")
    code = data.get("code") or ""
    if code in PART_CODES:
        label, note = dict((c, lb) for c, lb, _h in PARTS)[code], ""
    else:
        label = _clean(data.get("label"), 60)
        if not label:
            raise EditError("Name the kind of part.")
        code = code or "x-" + (re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:38] or "part")
        if not CODE.match(code):
            raise EditError("A kind of part of your own is named in letters and digits.")
        if label.lower() in {lb.lower() for _c, lb, _h in PARTS} | {"personas", "persona"}:
            raise EditError(f"{label} is a standard kind of part already.", 409)
        note = _clean(data.get("note"), 300)
    seq = _one(conn, "SELECT coalesce(max(sort_order), 0) + 1 AS n FROM proj.journey_part_kinds WHERE project_id = :p", p=p["id"])["n"]
    conn.execute(text("""INSERT INTO proj.journey_part_kinds (project_id, code, label, fields, note, sort_order, added_by)
                         VALUES (:p, :c, :l, CAST(:f AS jsonb), :n, :s, :u)
                         ON CONFLICT (project_id, code) DO UPDATE SET label = EXCLUDED.label, fields = EXCLUDED.fields,
                             note = EXCLUDED.note"""),
                 {"p": p["id"], "c": code, "l": label, "f": json.dumps(fields), "n": note, "s": seq, "u": user.username})
    return {"code": code, "message": f"{label}: {', '.join(fields) or 'no fields of its own'}."}


def remove_part_kind(conn, project: Any, user, code: str) -> dict:
    """A kind of part of the project's own goes when no journey uses it; a standard kind loses its extra fields."""
    p = _project(conn, project, user, "contribute")
    if code not in PART_CODES:
        used = _one(conn, """SELECT count(*) AS n FROM proj.journey_items i JOIN proj.journeys j ON j.id = i.journey_id
                              WHERE j.project_id = :p AND i.part = :c""", p=p["id"], c=code)["n"]
        if used:
            raise EditError(f"{used} part{'s' if used != 1 else ''} of this kind {'are' if used != 1 else 'is'} on journeys: remove them first.", 409)
    conn.execute(text("DELETE FROM proj.journey_part_kinds WHERE project_id = :p AND code = :c"), {"p": p["id"], "c": code})
    return {"code": code, "message": "Removed." if code not in PART_CODES else "Its extra fields are gone."}


# ---------------------------------------------------------------- reading
def _project(conn, project: Any, user, what: str) -> dict:
    p = pj.project_row(conn, project)
    pw.need(conn, p, user, what)
    return p


def _journey(conn, p: dict, jid: str) -> dict:
    j = _one(conn, "SELECT * FROM proj.journeys WHERE project_id = :p AND guid::text = :g", p=p["id"], g=str(jid))
    if not j:
        raise EditError("No such journey in this project.", 404)
    return j


def listing(conn, project: Any, user) -> dict:
    """A project's journeys with their stages, steps and average emotion, and what a journey is made of."""
    p = _project(conn, project, user, "read")
    rows = _rows(conn, """SELECT j.guid::text AS id, j.name, j.kind, j.status, j.description, j.persona, j.source_note,
                                 s.guid::text AS source, s.name AS source_name, j.created_by, j.created_at, j.changed_by, j.changed_at,
                                 (SELECT count(*) FROM proj.journey_stages t WHERE t.journey_id = j.id) AS stages,
                                 (SELECT count(*) FROM proj.journey_items i WHERE i.journey_id = j.id AND i.part = 'step') AS steps,
                                 (SELECT round(avg(i.score), 1) FROM proj.journey_items i WHERE i.journey_id = j.id AND i.score IS NOT NULL) AS emotion
                            FROM proj.journeys j LEFT JOIN proj.journeys s ON s.id = j.source_id
                           WHERE j.project_id = :p ORDER BY j.created_at, j.id""", p=p["id"])
    for r in rows:
        r["emotion"] = float(r["emotion"]) if r["emotion"] is not None else None
    return {"journeys": rows, "parts": part_kinds(conn, p), "kinds": KINDS, "statuses": STATUSES, "templates": TEMPLATES,
            "faces": {str(k): {"face": f, "label": lb} for k, (f, lb) in FACES.items()}, "link_types": LINK_TYPES}


def _stages(conn, jid: int) -> list[dict]:
    return _rows(conn, """SELECT id AS _id, guid::text AS id, sort_order, name, note, lineage::text AS lineage
                            FROM proj.journey_stages WHERE journey_id = :j ORDER BY sort_order, id""", j=jid)


def _items(conn, jid: int) -> list[dict]:
    rows = _rows(conn, """SELECT i.id AS _id, i.guid::text AS id, s.guid::text AS stage, i.part, i.sort_order, i.text, i.note, i.score,
                                 i.fields, i.lineage::text AS lineage, i.changed_by, i.changed_at
                            FROM proj.journey_items i LEFT JOIN proj.journey_stages s ON s.id = i.stage_id
                           WHERE i.journey_id = :j ORDER BY s.sort_order NULLS FIRST, i.part, i.sort_order, i.id""", j=jid)
    for r in rows:
        r["fields"] = r["fields"] or {}
    return rows


def _links(conn, jid: int) -> list[dict]:
    return _rows(conn, """SELECT l.guid::text AS id, s.guid::text AS stage, i.guid::text AS item, l.model_guid::text AS model,
                                 l.entity_guid::text AS entity, l.display_id, l.name, l.entity_type
                            FROM proj.journey_links l LEFT JOIN proj.journey_stages s ON s.id = l.stage_id
                            LEFT JOIN proj.journey_items i ON i.id = l.item_id
                           WHERE l.journey_id = :j ORDER BY l.entity_type, l.name""", j=jid)


def get(conn, project: Any, user, jid: str) -> dict:
    """One journey: its stages, each with its parts by kind and its linked elements; the personas; the emotion curve;
    the documents behind it and its history."""
    p = _project(conn, project, user, "read")
    j = _journey(conn, p, jid)
    src = _one(conn, "SELECT guid::text AS id, name FROM proj.journeys WHERE id = :i", i=j["source_id"]) if j["source_id"] else None
    items, links = _items(conn, j["id"]), _links(conn, j["id"])
    codes = [k["code"] for k in part_kinds(conn, p)]
    strip = lambda r: {k: v for k, v in r.items() if k != "_id"}  # noqa: E731
    stages = []
    for s in _stages(conn, j["id"]):
        mine = [i for i in items if i["stage"] == s["id"]]
        stages.append({**strip(s), "parts": {c: [strip(i) for i in mine if i["part"] == c] for c in codes},
                       "links": [x for x in links if x["stage"] == s["id"] and not x["item"]]})
    curve = [{"stage": s["id"], "step": i["id"], "text": i["text"], "score": i["score"]}
             for s in stages for i in s["parts"].get("step", [])]
    return {"id": str(j["guid"]), "name": j["name"], "kind": j["kind"], "status": j["status"], "description": j["description"],
            "persona": j["persona"], "source": src, "source_note": j["source_note"], "created_by": j["created_by"],
            "created_at": j["created_at"], "changed_by": j["changed_by"], "changed_at": j["changed_at"],
            "stages": stages, "personas": [strip(i) for i in items if i["part"] == PERSONA], "curve": curve,
            "item_links": [x for x in links if x["item"]],
            "documents": _rows(conn, """SELECT d.guid::text AS id, d.file_name, d.title, d.folder, d.versions, jd.note, jd.added_by, jd.added_at
                                          FROM proj.journey_documents jd JOIN proj.documents d ON d.id = jd.document_id
                                         WHERE jd.journey_id = :j ORDER BY jd.added_at""", j=j["id"]),
            "history": _rows(conn, "SELECT action, username, at, note FROM proj.journey_events WHERE journey_id = :j ORDER BY at, id", j=j["id"])}


# ---------------------------------------------------------------- journeys
def _event(conn, jid: int, user, action: str, note: str = "") -> None:
    conn.execute(text("INSERT INTO proj.journey_events (journey_id, action, username, note) VALUES (:j, :a, :u, :n)"),
                 {"j": jid, "a": action, "u": user.username, "n": _clean(note, 1000)})


def _touch(conn, j: dict, user, action: str, note: str = "") -> str:
    """A change: kept, and an agreed journey is a draft again."""
    again = j["status"] == "agreed"
    conn.execute(text("UPDATE proj.journeys SET changed_by = :u, changed_at = now(), status = 'draft' WHERE id = :i"),
                 {"u": user.username, "i": j["id"]})
    _event(conn, j["id"], user, action, note + (" (it was agreed: a draft again)" if again else ""))
    return " It was agreed: it is a draft again." if again else ""


def _new(conn, p: dict, user, name: str, kind: str, description: str = "", persona: str = "", source: dict | None = None,
         note: str = "") -> dict:
    name = _clean(name, 200)
    if not name:
        raise EditError("Name the journey.")
    if kind not in KINDS:
        raise EditError(f"A journey is one of: {', '.join(KINDS.values())}.")
    if _one(conn, "SELECT 1 AS x FROM proj.journeys WHERE project_id = :p AND lower(name) = lower(:n)", p=p["id"], n=name):
        raise EditError(f"The project has a journey called {name} already.", 409)
    j = _one(conn, """INSERT INTO proj.journeys (project_id, name, kind, description, persona, source_id, source_note, created_by)
                      VALUES (:p, :n, :k, :d, :pe, :s, :sn, :u) RETURNING *""",
             p=p["id"], n=name, k=kind, d=_clean(description), pe=_clean(persona, 200), s=source["id"] if source else None,
             sn=note, u=user.username)
    _event(conn, j["id"], user, "made", note)
    return j


def create(conn, project: Any, user, data: dict) -> dict:
    """Makes a journey in a project: blank, or from the starter template's typical stages."""
    p = _project(conn, project, user, "contribute")
    template = data.get("template") or "blank"
    if template not in TEMPLATES:
        raise EditError("Start blank or from the starter template.")
    j = _new(conn, p, user, data.get("name"), data.get("kind") or "current", data.get("description") or "",
             data.get("persona") or "", note="from the starter template" if template == "starter" else "")
    if template == "starter":
        for n, (name, note) in enumerate(STARTER, start=1):
            conn.execute(text("INSERT INTO proj.journey_stages (journey_id, sort_order, name, note) VALUES (:j, :s, :n, :o)"),
                         {"j": j["id"], "s": n, "n": name, "o": note})
    return {"id": str(j["guid"]), "message": f"Journey {j['name']} made" + (" with the starter's stages." if template == "starter" else ".")}


def change(conn, project: Any, user, jid: str, data: dict) -> dict:
    """Name, kind, status (draft | agreed), description or persona."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    name = _clean(data.get("name", j["name"]), 200)
    kind, status = data.get("kind", j["kind"]), data.get("status", j["status"])
    if not name:
        raise EditError("Name the journey.")
    if kind not in KINDS or status not in STATUSES:
        raise EditError("Unknown kind or status.")
    if name.lower() != j["name"].lower() and _one(conn, "SELECT 1 AS x FROM proj.journeys WHERE project_id = :p AND lower(name) = lower(:n)",
                                                  p=p["id"], n=name):
        raise EditError(f"The project has a journey called {name} already.", 409)
    conn.execute(text("""UPDATE proj.journeys SET name = :n, kind = :k, status = :s, description = :d, persona = :pe,
                                changed_by = :u, changed_at = now() WHERE id = :i"""),
                 {"n": name, "k": kind, "s": status, "d": _clean(data.get("description", j["description"])),
                  "pe": _clean(data.get("persona", j["persona"]), 200), "u": user.username, "i": j["id"]})
    what = [w for w, on in (("renamed", name != j["name"]), (f"now {KINDS[kind].lower()}", kind != j["kind"]),
                            ("agreed" if status == "agreed" else "a draft again", status != j["status"])) if on]
    _event(conn, j["id"], user, "changed", ", ".join(what))
    return {"id": jid, "message": f"{name}: {', '.join(what) or 'saved'}."}


def delete(conn, project: Any, user, jid: str) -> dict:
    """Removes a journey with its stages, parts, links and history."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    conn.execute(text("DELETE FROM proj.journeys WHERE id = :i"), {"i": j["id"]})
    return {"id": jid, "message": f"Journey {j['name']} removed."}


# ---------------------------------------------------------------- stages
def _stage(conn, p: dict, sid: str) -> tuple[dict, dict]:
    s = _one(conn, """SELECT s.* FROM proj.journey_stages s JOIN proj.journeys j ON j.id = s.journey_id
                       WHERE j.project_id = :p AND s.guid::text = :g""", p=p["id"], g=str(sid))
    if not s:
        raise EditError("No such stage on a journey of this project.", 404)
    return s, _one(conn, "SELECT * FROM proj.journeys WHERE id = :i", i=s["journey_id"])


def add_stage(conn, project: Any, user, jid: str, data: dict) -> dict:
    """A stage at the end, or after another {after: stage id}."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    name = _clean(data.get("name"), 120)
    if not name:
        raise EditError("Name the stage.")
    after = data.get("after")
    if after:
        a, _j = _stage(conn, p, after)
        seq = a["sort_order"] + 1
        conn.execute(text("UPDATE proj.journey_stages SET sort_order = sort_order + 1 WHERE journey_id = :j AND sort_order >= :s"),
                     {"j": j["id"], "s": seq})
    else:
        seq = _one(conn, "SELECT coalesce(max(sort_order), 0) + 1 AS n FROM proj.journey_stages WHERE journey_id = :j", j=j["id"])["n"]
    row = _one(conn, """INSERT INTO proj.journey_stages (journey_id, sort_order, name, note) VALUES (:j, :s, :n, :o)
                        RETURNING guid::text AS id""", j=j["id"], s=seq, n=name, o=_clean(data.get("note"), 1000))
    return {"id": row["id"], "message": f"Stage {name} added." + _touch(conn, j, user, "stage added", name)}


def change_stage(conn, project: Any, user, sid: str, data: dict) -> dict:
    """A stage's name or note."""
    p = _project(conn, project, user, "contribute")
    s, j = _stage(conn, p, sid)
    name = _clean(data.get("name", s["name"]), 120)
    if not name:
        raise EditError("Name the stage.")
    conn.execute(text("UPDATE proj.journey_stages SET name = :n, note = :o WHERE id = :i"),
                 {"n": name, "o": _clean(data.get("note", s["note"]), 1000), "i": s["id"]})
    return {"id": sid, "message": "Saved." + _touch(conn, j, user, "stage changed", s["name"] + (f" → {name}" if name != s["name"] else ""))}


def remove_stage(conn, project: Any, user, sid: str) -> dict:
    """The stage goes, with its parts and links."""
    p = _project(conn, project, user, "contribute")
    s, j = _stage(conn, p, sid)
    n = _one(conn, "SELECT count(*) AS n FROM proj.journey_items WHERE stage_id = :s", s=s["id"])["n"]
    conn.execute(text("DELETE FROM proj.journey_stages WHERE id = :i"), {"i": s["id"]})
    return {"id": sid, "message": f"Stage {s['name']} removed with its {n} part{'s' if n != 1 else ''}." +
            _touch(conn, j, user, "stage removed", s["name"])}


def reorder(conn, project: Any, user, jid: str, data: dict) -> dict:
    """The stages in the order given {stages: [ids]}, or one stage's parts of one kind {stage, part, ids}."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    if data.get("stages"):
        for n, g in enumerate(data["stages"], start=1):
            conn.execute(text("UPDATE proj.journey_stages SET sort_order = :s WHERE journey_id = :j AND guid::text = :g"),
                         {"s": n, "j": j["id"], "g": str(g)})
        return {"id": jid, "message": "Stages in order." + _touch(conn, j, user, "stages reordered")}
    for n, g in enumerate(data.get("ids") or [], start=1):
        conn.execute(text("UPDATE proj.journey_items SET sort_order = :s WHERE journey_id = :j AND guid::text = :g"),
                     {"s": n, "j": j["id"], "g": str(g)})
    return {"id": jid, "message": "Order saved."}


# ---------------------------------------------------------------- parts
def _item(conn, p: dict, iid: str) -> tuple[dict, dict]:
    it = _one(conn, """SELECT i.* FROM proj.journey_items i JOIN proj.journeys j ON j.id = i.journey_id
                        WHERE j.project_id = :p AND i.guid::text = :g""", p=p["id"], g=str(iid))
    if not it:
        raise EditError("No such part on a journey of this project.", 404)
    return it, _one(conn, "SELECT * FROM proj.journeys WHERE id = :i", i=it["journey_id"])


def _fields(kind: dict | None, given: Any, old: dict | None = None) -> dict:
    allowed = (kind or {}).get("fields") or []
    out = {k: v for k, v in (old or {}).items() if k in allowed}
    for k, v in (given or {}).items():
        if k not in allowed:
            raise EditError(f"{k} is not a field of this kind of part.")
        out[k] = _clean(v, 300)
    return {k: v for k, v in out.items() if v}


def add_item(conn, project: Any, user, jid: str, data: dict) -> dict:
    """A part: {stage, part, text, note, score (steps: -2 to +2), fields}; a persona {part: persona, text} has no stage."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    part, t = data.get("part"), _clean(data.get("text"), 300)
    codes = _codes(conn, p)
    if part != PERSONA and part not in codes:
        raise EditError("Choose the kind of part.")
    if not t:
        raise EditError("Write the part.")
    stage = None
    if part != PERSONA:
        s, sj = _stage(conn, p, data.get("stage") or "")
        if sj["id"] != j["id"]:
            raise EditError("That stage is on another journey.")
        stage = s["id"]
    score = _score(data.get("score")) if part == "step" else None
    seq = _one(conn, """SELECT coalesce(max(sort_order), 0) + 1 AS n FROM proj.journey_items
                         WHERE journey_id = :j AND part = :pt AND stage_id IS NOT DISTINCT FROM :s""", j=j["id"], pt=part, s=stage)["n"]
    row = _one(conn, """INSERT INTO proj.journey_items (journey_id, stage_id, part, sort_order, text, note, score, fields, changed_by, changed_at)
                        VALUES (:j, :s, :pt, :o, :t, :n, :sc, CAST(:f AS jsonb), :u, now()) RETURNING guid::text AS id""",
               j=j["id"], s=stage, pt=part, o=seq, t=t, n=_clean(data.get("note"), 2000), sc=score,
               f=json.dumps(_fields(codes.get(part), data.get("fields"))), u=user.username)
    label = codes[part]["label"] if part in codes else "Personas"
    return {"id": row["id"], "message": f"Added to {label}." + _touch(conn, j, user, "part added", f"{label}: {t}")}


def change_item(conn, project: Any, user, iid: str, data: dict) -> dict:
    """Its text, note, emotion (steps), fields, or its stage."""
    p = _project(conn, project, user, "contribute")
    it, j = _item(conn, p, iid)
    t = _clean(data.get("text", it["text"]), 300)
    if not t:
        raise EditError("Write the part (or remove it).")
    stage = it["stage_id"]
    if data.get("stage") and it["part"] != PERSONA:
        s, sj = _stage(conn, p, data["stage"])
        if sj["id"] != j["id"]:
            raise EditError("That stage is on another journey.")
        stage = s["id"]
    score = _score(data["score"]) if "score" in data and it["part"] == "step" else it["score"]
    codes = _codes(conn, p)
    conn.execute(text("""UPDATE proj.journey_items SET text = :t, note = :n, score = :sc, fields = CAST(:f AS jsonb), stage_id = :s,
                                changed_by = :u, changed_at = now() WHERE id = :i"""),
                 {"t": t, "n": _clean(data.get("note", it["note"]), 2000), "sc": score,
                  "f": json.dumps(_fields(codes.get(it["part"]), data.get("fields"), it["fields"])), "s": stage, "u": user.username, "i": it["id"]})
    what = it["text"] + (f" → {t}" if t != it["text"] else "") + (f" (emotion {it['score']} → {score})" if score != it["score"] else "")
    return {"id": iid, "message": "Saved." + _touch(conn, j, user, "part changed", what)}


def remove_item(conn, project: Any, user, iid: str) -> dict:
    """Removes a part from its journey."""
    p = _project(conn, project, user, "contribute")
    it, j = _item(conn, p, iid)
    conn.execute(text("DELETE FROM proj.journey_items WHERE id = :i"), {"i": it["id"]})
    return {"id": iid, "message": "Removed." + _touch(conn, j, user, "part removed", it["text"])}


# ---------------------------------------------------------------- links to model elements
def elements(conn, project: Any, user, q: str = "", types: list[str] | None = None, limit: int = 40) -> dict:
    """Elements of the project's models to link to: by name or code, of the types given (default: the usual ones for
    a journey; "all" for any)."""
    p = _project(conn, project, user, "read")
    models = [str(r["model_guid"]) for r in _rows(conn, "SELECT model_guid FROM proj.project_models WHERE project_id = :p", p=p["id"])]
    if p.get("home_model") and str(p["home_model"]) not in models:
        models.append(str(p["home_model"]))
    if not models:
        return {"elements": [], "message": "The project has no models yet."}
    any_type = types == ["all"]
    rows = _rows(pj.core(conn), """SELECT m.guid::text AS model, m.name AS model_name, e.guid::text AS entity, e.display_id, e.name,
                                          et.name AS entity_type
                                     FROM core.entities e JOIN core.entity_types et ON et.id = e.entity_type_id
                                     JOIN core.models m ON m.id = e.model_id
                                    WHERE m.guid::text = ANY (CAST(:m AS text[])) AND NOT e.is_deleted
                                      AND (:any OR et.code = ANY (CAST(:t AS text[])) OR replace(et.name, ' ', '') = ANY (CAST(:t AS text[])))
                                      AND (:q = '' OR e.name ILIKE '%' || :q || '%' OR e.display_id ILIKE :q || '%')
                                    ORDER BY et.name, e.name LIMIT :l""",
                 m=models, any=any_type, t=types or LINK_TYPES, q=_clean(q, 100), l=max(1, min(int(limit or 40), 200)))
    return {"elements": rows}


def link(conn, project: Any, user, jid: str, data: dict) -> dict:
    """Links a stage {stage} or a part {item} to an element of one of the project's models {entity}."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    stage = item = None
    if data.get("item"):
        it, ij = _item(conn, p, data["item"])
        if ij["id"] != j["id"]:
            raise EditError("That part is on another journey.")
        item = it["id"]
    elif data.get("stage"):
        s, sj = _stage(conn, p, data["stage"])
        if sj["id"] != j["id"]:
            raise EditError("That stage is on another journey.")
        stage = s["id"]
    else:
        raise EditError("Link a stage or a part.")
    e = _entity(conn, p, str(data.get("entity") or ""))
    if not e:
        raise EditError("Choose an element of one of the project's models.", 404)
    if _one(conn, """SELECT 1 AS x FROM proj.journey_links WHERE journey_id = :j AND entity_guid = CAST(:e AS uuid)
                      AND stage_id IS NOT DISTINCT FROM :s AND item_id IS NOT DISTINCT FROM :i""", j=j["id"], e=e["entity"], s=stage, i=item):
        return {"id": jid, "message": f"{e['name']} is linked already."}
    row = _one(conn, """INSERT INTO proj.journey_links (journey_id, stage_id, item_id, model_guid, entity_guid, display_id, name, entity_type, added_by)
                        VALUES (:j, :s, :i, CAST(:m AS uuid), CAST(:e AS uuid), :d, :n, :t, :u) RETURNING guid::text AS id""",
               j=j["id"], s=stage, i=item, m=e["model"], e=e["entity"], d=e["display_id"] or "", n=e["name"], t=e["entity_type"], u=user.username)
    return {"id": row["id"], "message": f"Linked to {e['entity_type']} {e['name']}." + _touch(conn, j, user, "linked", f"{e['entity_type']} {e['name']}")}


def _entity(conn, p: dict, guid: str) -> dict | None:
    models = [str(r["model_guid"]) for r in _rows(conn, "SELECT model_guid FROM proj.project_models WHERE project_id = :p", p=p["id"])]
    if p.get("home_model"):
        models.append(str(p["home_model"]))
    return _one(pj.core(conn), """SELECT m.guid::text AS model, e.guid::text AS entity, e.display_id, e.name, et.name AS entity_type
                                    FROM core.entities e JOIN core.entity_types et ON et.id = e.entity_type_id
                                    JOIN core.models m ON m.id = e.model_id
                                   WHERE e.guid::text = :g AND m.guid::text = ANY (CAST(:m AS text[])) AND NOT e.is_deleted""",
                g=guid, m=models or [""])


def unlink(conn, project: Any, user, lid: str) -> dict:
    """Takes a link to a model element off a stage or part."""
    p = _project(conn, project, user, "contribute")
    x = _one(conn, """SELECT l.*, j.status FROM proj.journey_links l JOIN proj.journeys j ON j.id = l.journey_id
                       WHERE j.project_id = :p AND l.guid::text = :g""", p=p["id"], g=str(lid))
    if not x:
        raise EditError("No such link.", 404)
    conn.execute(text("DELETE FROM proj.journey_links WHERE id = :i"), {"i": x["id"]})
    j = _one(conn, "SELECT * FROM proj.journeys WHERE id = :i", i=x["journey_id"])
    return {"id": lid, "message": f"{x['name']} is no longer linked." + _touch(conn, j, user, "unlinked", x["name"])}


# ---------------------------------------------------------------- copies
def _copy_into(conn, src: dict, dst: dict) -> int:
    """Every stage, part and link of src into dst, with the same lineage."""
    stage_map: dict[int, int] = {}
    for s in _rows(conn, "SELECT * FROM proj.journey_stages WHERE journey_id = :j ORDER BY sort_order, id", j=src["id"]):
        stage_map[s["id"]] = _one(conn, """INSERT INTO proj.journey_stages (journey_id, sort_order, name, note, lineage)
                                           VALUES (:j, :s, :n, :o, :l) RETURNING id""",
                                  j=dst["id"], s=s["sort_order"], n=s["name"], o=s["note"], l=s["lineage"])["id"]
    item_map: dict[int, int] = {}
    for it in _rows(conn, "SELECT * FROM proj.journey_items WHERE journey_id = :j ORDER BY id", j=src["id"]):
        item_map[it["id"]] = _one(conn, """INSERT INTO proj.journey_items (journey_id, stage_id, part, sort_order, text, note, score, fields, lineage)
                                           VALUES (:j, :s, :p, :o, :t, :n, :sc, CAST(:f AS jsonb), :l) RETURNING id""",
                                  j=dst["id"], s=stage_map.get(it["stage_id"]), p=it["part"], o=it["sort_order"], t=it["text"],
                                  n=it["note"], sc=it["score"], f=json.dumps(it["fields"] or {}), l=it["lineage"])["id"]
    for x in _rows(conn, "SELECT * FROM proj.journey_links WHERE journey_id = :j", j=src["id"]):
        conn.execute(text("""INSERT INTO proj.journey_links (journey_id, stage_id, item_id, model_guid, entity_guid, display_id, name, entity_type, added_by)
                             VALUES (:j, :s, :i, :m, :e, :d, :n, :t, :u)"""),
                     {"j": dst["id"], "s": stage_map.get(x["stage_id"]), "i": item_map.get(x["item_id"]), "m": x["model_guid"],
                      "e": x["entity_guid"], "d": x["display_id"], "n": x["name"], "t": x["entity_type"], "u": x["added_by"]})
    return len(item_map)


def copy(conn, project: Any, user, jid: str, data: dict) -> dict:
    """A copy in this project: a working copy by default, or any other kind (a target state from a current one)."""
    p = _project(conn, project, user, "contribute")
    src = _journey(conn, p, jid)
    kind = data.get("kind") or "working"
    if kind not in KINDS:
        raise EditError("Unknown kind.")
    j = _new(conn, p, user, data.get("name") or f"{src['name']} ({KINDS[kind].lower()})", kind, data.get("description") or src["description"],
             src["persona"], src, f"a {KINDS[kind].lower()} of {src['name']}")
    n = _copy_into(conn, src, j)
    return {"id": str(j["guid"]), "message": f"{j['name']} made from {src['name']} ({n} parts)."}


def copy_to(conn, project: Any, user, jid: str, target: str, data: dict) -> dict:
    """A copy in another project (read here, contribute there), with the same lineage. Its documents stay here; a part
    of a kind the other project lacks brings the kind with it."""
    p = _project(conn, project, user, "read")
    src = _journey(conn, p, jid)
    t = pj.project_row(conn, target)
    pw.need(conn, t, user, "contribute")
    if t["id"] == p["id"]:
        return copy(conn, project, user, jid, data)
    name = data.get("name") or src["name"]
    if _one(conn, "SELECT 1 AS x FROM proj.journeys WHERE project_id = :p AND lower(name) = lower(:n)", p=t["id"], n=name):
        name = f"{name} (from {p['name']})"
    j = _new(conn, t, user, name, data.get("kind") or src["kind"], src["description"], src["persona"], None,
             f"copied from {src['name']} in {p['name']}")
    conn.execute(text("""INSERT INTO proj.journey_part_kinds (project_id, code, label, fields, note, sort_order, added_by)
                         SELECT :t, k.code, k.label, k.fields, k.note, k.sort_order, :u FROM proj.journey_part_kinds k
                          WHERE k.project_id = :p AND k.code IN (SELECT DISTINCT part FROM proj.journey_items WHERE journey_id = :j)
                         ON CONFLICT (project_id, code) DO NOTHING"""), {"t": t["id"], "p": p["id"], "j": src["id"], "u": user.username})
    n = _copy_into(conn, src, j)
    _event(conn, src["id"], user, "copied", f"to {t['name']}")
    return {"id": str(j["guid"]), "project": str(t["guid"]), "message": f"{j['name']} is in {t['name']} ({n} parts)."}


# ---------------------------------------------------------------- the documents behind a journey
JOURNEY_FILES = "00_Project/Customer journeys"


def add_document(conn, project: Any, user, jid: str, data: dict, file_name: str = "", content: bytes = b"") -> dict:
    """Upload a document used to build the journey (interview notes, research), or link one of the project's."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    if content:
        doc = pw._store(conn, p, user, JOURNEY_FILES, file_name or "document", content, origin="journey", kind="Artifact")
        g = doc["id"]
    else:
        g = data.get("document") or ""
    d = _one(conn, "SELECT id, file_name, title FROM proj.documents WHERE project_id = :p AND guid::text = :g", p=p["id"], g=str(g))
    if not d:
        raise EditError("Choose a file to upload, or a document of this project.")
    conn.execute(text("""INSERT INTO proj.journey_documents (journey_id, document_id, note, added_by) VALUES (:j, :d, :n, :u)
                         ON CONFLICT (journey_id, document_id) DO UPDATE SET note = EXCLUDED.note"""),
                 {"j": j["id"], "d": d["id"], "n": _clean(data.get("note"), 1000), "u": user.username})
    _event(conn, j["id"], user, "document added", d["title"] or d["file_name"])
    return {"id": jid, "message": f"{d['title'] or d['file_name']} is with {j['name']}."}


def remove_document(conn, project: Any, user, jid: str, doc: str) -> dict:
    """Takes a document off the journey; it stays in the project's documents."""
    p = _project(conn, project, user, "contribute")
    j = _journey(conn, p, jid)
    d = _one(conn, "SELECT id, file_name, title FROM proj.documents WHERE project_id = :p AND guid::text = :g", p=p["id"], g=str(doc))
    if d:
        conn.execute(text("DELETE FROM proj.journey_documents WHERE journey_id = :j AND document_id = :d"), {"j": j["id"], "d": d["id"]})
        _event(conn, j["id"], user, "document taken off", d["title"] or d["file_name"])
    return {"id": jid, "message": "Taken off the journey (it stays in the project's documents)."}


# ---------------------------------------------------------------- compare
def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def _match(a_list: list[dict], b_list: list[dict], key) -> list[tuple[dict | None, dict | None]]:
    """Pairs by lineage, then by the same text; the rest added (b only) or removed (a only)."""
    by_lin = {x["lineage"]: x for x in a_list}
    used: set[str] = set()
    pairs, rest = [], []
    for b in b_list:
        a = by_lin.get(b["lineage"])
        if a and a["id"] not in used:
            used.add(a["id"])
            pairs.append((a, b))
        else:
            rest.append(b)
    for b in rest:
        a = next((x for x in a_list if x["id"] not in used and _norm(key(x)) == _norm(key(b))), None)
        if a:
            used.add(a["id"])
        pairs.append((a, b))
    return pairs + [(a, None) for a in a_list if a["id"] not in used]


def _row(a: dict | None, b: dict | None) -> dict:
    x = b or a
    if a and b:
        same = (a["text"], a.get("note") or "", a.get("score"), a.get("fields") or {}) == \
               (b["text"], b.get("note") or "", b.get("score"), b.get("fields") or {})
        state = "same" if same else "changed"
    else:
        state = "added" if b else "removed"
    return {"state": state, "text": x["text"], "note": x.get("note") or "", "score": x.get("score"),
            "was_text": a["text"] if a and b and a["text"] != b["text"] else "",
            "was_score": a.get("score") if a and b and a.get("score") != b.get("score") else None,
            "fields": x.get("fields") or {}, "lineage": x["lineage"]}


def diff(a: dict, b: dict) -> dict:
    """Journey B against A (both as get() gives them): stage by stage (added, removed, renamed) and in each stage, kind
    by kind, the parts the same, added, changed (old text and emotion kept) or removed; the personas; the links."""
    codes = list(dict.fromkeys(list(b["stages"][0]["parts"]) if b["stages"] else []) or
                 (list(a["stages"][0]["parts"]) if a["stages"] else PART_CODES))
    stages = []
    for sa, sb in _match(a["stages"], b["stages"], lambda s: s["name"]):
        x = sb or sa
        st = "same" if sa and sb else ("added" if sb else "removed")
        if sa and sb and sa["name"] != sb["name"]:
            st = "changed"
        parts = {}
        for c in codes:
            la, lb = (sa or {}).get("parts", {}).get(c, []), (sb or {}).get("parts", {}).get(c, [])
            rows = [_row(pa, pb) for pa, pb in _match(la, lb, lambda i: i["text"])]
            if not (sa and sb):
                for r in rows:
                    r["state"] = st
            parts[c] = rows
        ea = {x_["entity"]: x_ for x_ in (sa or {}).get("links", [])}
        eb = {x_["entity"]: x_ for x_ in (sb or {}).get("links", [])}
        links = [{**v, "state": "same" if k in ea and k in eb else ("added" if k in eb else "removed")} for k, v in {**ea, **eb}.items()]
        stages.append({"name": x["name"], "was_name": sa["name"] if st == "changed" else "", "state": st, "note": x.get("note") or "",
                       "parts": parts, "links": links})
    personas = [_row(pa, pb) for pa, pb in _match(a["personas"], b["personas"], lambda i: i["text"])]
    counts = {s: sum(1 for st in stages for rows in st["parts"].values() for r in rows if r["state"] == s) +
              sum(1 for r in personas if r["state"] == s) for s in ("same", "added", "changed", "removed")}
    return {"stages": stages, "personas": personas, "counts": counts, "parts": codes}


def compare(conn, project: Any, user, a: str, b: str) -> dict:
    """Two journeys compared, stage by stage and part by part."""
    ja, jb = get(conn, project, user, a), get(conn, project, user, b)
    out = diff(ja, jb)
    return {"a": {"id": a, "name": ja["name"], "kind": ja["kind"]}, "b": {"id": b, "name": jb["name"], "kind": jb["kind"]}, **out}


# ---------------------------------------------------------------- export: PDF, PowerPoint, draw.io
STYLE = {"same": ("FFFFFF", "8A96A3", "1F2328"), "added": ("DAFBE1", "1A7F37", "1A7F37"),
         "changed": ("FFF8C5", "BF8700", "7D4E00"), "removed": ("FFEBE9", "CF222E", "CF222E")}
SCORE_COLOUR = {-2: "CF222E", -1: "E16F24", 0: "8A96A3", 1: "4AA35C", 2: "1A7F37"}


def view(conn, project: Any, user, jid: str, other: str = "") -> dict:
    """What an export draws: a journey, or the comparison of two: stages as columns, a row per kind of part, the
    emotion curve, the personas and the linked elements."""
    p = _project(conn, project, user, "read")
    labels = {k["code"]: k["label"] for k in part_kinds(conn, p)}
    if other:
        cmp = compare(conn, project, user, jid, other)
        return {"title": f"{cmp['a']['name']} → {cmp['b']['name']}",
                "subtitle": "Comparison: green added, amber changed, red crossed out removed",
                "stages": cmp["stages"], "personas": cmp["personas"], "labels": labels, "parts": cmp["parts"], "persona": ""}
    j = get(conn, project, user, jid)
    stages = [{"name": s["name"], "was_name": "", "state": "same", "note": s["note"],
               "parts": {c: [{**i, "state": "same", "was_text": "", "was_score": None} for i in rows] for c, rows in s["parts"].items()},
               "links": [{**x, "state": "same"} for x in s["links"]]} for s in j["stages"]]
    return {"title": j["name"], "subtitle": f"{KINDS[j['kind']]} · {STATUSES[j['status']]}" + (f" · for {j['persona']}" if j["persona"] else ""),
            "stages": stages, "personas": [{**i, "state": "same", "was_text": ""} for i in j["personas"]], "labels": labels,
            "parts": list(labels), "persona": j["persona"]}


def export(conn, project: Any, user, jid: str, fmt: str, other: str = "") -> tuple[bytes, str, str]:
    """A journey (or two compared) as PDF, PowerPoint or draw.io, with its file name and type."""
    v = view(conn, project, user, jid, other)
    name = bf.file_name(v["title"].replace("→", "to"), {"pdf": "pdf", "pptx": "pptx", "drawio": "drawio"}.get(fmt, "x"))
    if fmt == "pdf":
        return _pdf(v), name, "application/pdf"
    if fmt == "pptx":
        return _pptx(v), name, "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if fmt == "drawio":
        return _drawio(v).encode(), name, "application/xml"
    raise EditError("Export as pdf, pptx or drawio.")


def _rows_shown(v: dict) -> list[str]:
    """The kinds of part with anything in them (steps always: the curve hangs on them)."""
    return [c for c in v["parts"] if c == "step" or any(s["parts"].get(c) for s in v["stages"])]


def _label(r: dict) -> str:
    t = r["text"]
    if r.get("score") is not None and "score" in r:
        t = f"{FACES[r['score']][0]} {t}"
    return t


def _lines(s: str, width: int) -> list[str]:
    return textwrap.wrap(s, width) or [""]


def _steps(v: dict) -> list[tuple[int, dict]]:
    return [(n, r) for n, s in enumerate(v["stages"]) for r in s["parts"].get("step", []) if r["state"] != "removed"]


COL, HEAD, LAB = 230, 54, 150      # draw.io and the layout: a column per stage, the header, the labels' column
CURVE = 150                        # the emotion row's height: five levels, +2 at the top


def _drawio(v: dict) -> str:
    q = {'"': "&quot;"}
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    title = f'<b style="font-size:18px">{escape(v["title"])}</b><br><span style="color:#5b6775">{escape(v["subtitle"])}</span>'
    cells.append(f'<mxCell id="title" value="{escape(title, q)}" style="text;html=1;align=left;verticalAlign=top;" vertex="1" parent="1">'
                 f'<mxGeometry x="0" y="-70" width="{LAB + COL * max(1, len(v["stages"]))}" height="60" as="geometry"/></mxCell>')
    if v["personas"]:
        who = ", ".join(("~~" if r["state"] == "removed" else "") + r["text"] for r in v["personas"])
        cells.append(f'<mxCell id="personas" value="{escape("Personas: " + who, q)}" style="text;html=1;align=left;fontColor=#5b6775;" '
                     f'vertex="1" parent="1"><mxGeometry x="0" y="-14" width="{LAB + COL * max(1, len(v["stages"]))}" height="14" as="geometry"/></mxCell>')
    y = 0
    for n, s in enumerate(v["stages"]):
        fill, stroke, font = STYLE[s["state"]] if s["state"] != "same" else ("1F5FB8", "1F5FB8", "FFFFFF")
        lab = escape(s["name"]) + (f"<br><s>{escape(s['was_name'])}</s>" if s["was_name"] else "")
        if s["note"]:
            lab += f'<br><span style="font-size:10px">{escape(s["note"][:120])}</span>'
        cells.append(f'<mxCell id="s{n}" value="{escape(lab, q)}" style="shape=step;perimeter=stepPerimeter;fixedSize=1;size=14;whiteSpace=wrap;html=1;'
                     f'fillColor=#{fill};strokeColor=#{stroke};fontColor=#{font};fontStyle=1;" vertex="1" parent="1">'
                     f'<mxGeometry x="{LAB + n * COL}" y="{y}" width="{COL - 4}" height="{HEAD}" as="geometry"/></mxCell>')
    y += HEAD + 10
    for c in _rows_shown(v):
        if c == "step":
            # the emotion curve above the steps (owner, 17 Nov 2026): a point per step, +2 at the top, zero the line
            cells.append(f'<mxCell id="lab_emotion" value="&lt;b&gt;Emotion&lt;/b&gt;" style="text;html=1;align=left;verticalAlign=middle;" '
                         f'vertex="1" parent="1"><mxGeometry x="0" y="{y}" width="{LAB - 10}" height="{CURVE}" as="geometry"/></mxCell>')
            zero = y + CURVE / 2
            cells.append(f'<mxCell id="zero" style="endArrow=none;dashed=1;strokeColor=#8A96A3;" edge="1" parent="1">'
                         f'<mxGeometry relative="1" as="geometry"><mxPoint x="{LAB}" y="{zero}" as="sourcePoint"/>'
                         f'<mxPoint x="{LAB + COL * len(v["stages"])}" y="{zero}" as="targetPoint"/></mxGeometry></mxCell>')
            steps = _steps(v)
            per: dict[int, int] = {}
            for n, _r in steps:
                per[n] = per.get(n, 0) + 1
            seen: dict[int, int] = {}
            prev = None
            for k, (n, r) in enumerate(steps):
                if r.get("score") is None:
                    continue
                i = seen.get(n, 0)
                seen[n] = i + 1
                cx = LAB + n * COL + (i + 1) * COL / (per[n] + 1)
                cy = zero - r["score"] * (CURVE / 2 - 14) / 2
                col = SCORE_COLOUR[r["score"]]
                cells.append(f'<mxCell id="e{k}" value="{FACES[r["score"]][0]}" style="ellipse;whiteSpace=wrap;html=1;fillColor=#FFFFFF;'
                             f'strokeColor=#{col};strokeWidth=2;fontSize=14;" vertex="1" parent="1">'
                             f'<mxGeometry x="{cx - 13}" y="{cy - 13}" width="26" height="26" as="geometry"/></mxCell>')
                if prev is not None:
                    cells.append(f'<mxCell id="c{k}" style="endArrow=none;curved=1;strokeColor=#1F5FB8;strokeWidth=2;" edge="1" parent="1" '
                                 f'source="e{prev}" target="e{k}"><mxGeometry relative="1" as="geometry"/></mxCell>')
                prev = k
            y += CURVE + 10
        rows = {n: s["parts"].get(c, []) for n, s in enumerate(v["stages"])}
        h = max([40] + [sum(14 * (len(_lines(_label(r), 30)) + (len(_lines(r["was_text"], 30)) if r["was_text"] else 0)) + 16 for r in rr)
                        for rr in rows.values()])
        cells.append(f'<mxCell id="lab_{c}" value="&lt;b&gt;{escape(v["labels"].get(c, c))}&lt;/b&gt;" style="text;html=1;align=left;verticalAlign=top;" '
                     f'vertex="1" parent="1"><mxGeometry x="0" y="{y}" width="{LAB - 10}" height="{h}" as="geometry"/></mxCell>')
        for n, rr in rows.items():
            top = y
            for k, r in enumerate(rr):
                fill, stroke, font = STYLE[r["state"]]
                lab = escape(_label(r))
                if r["was_text"]:
                    lab = f"<s>{escape(r['was_text'])}</s><br>{lab}"
                ih = 14 * (len(_lines(_label(r), 30)) + (len(_lines(r["was_text"], 30)) if r["was_text"] else 0)) + 10
                cells.append(f'<mxCell id="i_{c}_{n}_{k}" value="{escape(lab, q)}" style="rounded=1;arcSize=8;whiteSpace=wrap;html=1;align=left;'
                             f'spacingLeft=6;fontSize=12;fillColor=#{fill};strokeColor=#{stroke};fontColor=#{font};fontStyle={8 if r["state"] == "removed" else 0};" '
                             f'vertex="1" parent="1"><mxGeometry x="{LAB + n * COL}" y="{top}" width="{COL - 10}" height="{ih}" as="geometry"/></mxCell>')
                top += ih + 6
        y += h + 10
    if any(s["links"] for s in v["stages"]):
        h = max(14 * len(s["links"]) + 20 for s in v["stages"])
        cells.append(f'<mxCell id="lab_links" value="&lt;b&gt;Linked elements&lt;/b&gt;" style="text;html=1;align=left;verticalAlign=top;" '
                     f'vertex="1" parent="1"><mxGeometry x="0" y="{y}" width="{LAB - 10}" height="{h}" as="geometry"/></mxCell>')
        for n, s in enumerate(v["stages"]):
            if s["links"]:
                lab = "<br>".join(("<s>" if x["state"] == "removed" else "") + escape(f"{x['entity_type']}: {x['name']}") +
                                  ("</s>" if x["state"] == "removed" else "") for x in s["links"])
                cells.append(f'<mxCell id="l{n}" value="{escape(lab, q)}" style="text;html=1;align=left;verticalAlign=top;fontSize=11;fontColor=#5b6775;" '
                             f'vertex="1" parent="1"><mxGeometry x="{LAB + n * COL}" y="{y}" width="{COL - 10}" height="{h}" as="geometry"/></mxCell>')
    return ('<mxfile host="EA Explorer"><diagram id="journey" name="' + escape(v["title"], q) +
            '"><mxGraphModel grid="1" gridSize="10" page="0"><root>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")


def _rgb(h: str):
    from reportlab.lib.colors import HexColor
    return HexColor("#" + h)


def _face(c, x: float, y: float, r: float, score: int) -> None:
    """A small face: a circle, two eyes and a mouth curved by the score (PDF fonts have no emoji)."""
    col = _rgb(SCORE_COLOUR[score])
    c.setStrokeColor(col)
    c.setFillColor(_rgb("FFFFFF"))
    c.setLineWidth(1.2)
    c.circle(x, y, r, stroke=1, fill=1)
    c.setFillColor(col)
    c.circle(x - r * 0.35, y + r * 0.25, r * 0.12, stroke=0, fill=1)
    c.circle(x + r * 0.35, y + r * 0.25, r * 0.12, stroke=0, fill=1)
    bend = score * r * 0.18
    p = c.beginPath()
    p.moveTo(x - r * 0.45, y - r * 0.3 + (bend if score > 0 else 0))
    p.curveTo(x - r * 0.2, y - r * 0.3 - bend, x + r * 0.2, y - r * 0.3 - bend, x + r * 0.45, y - r * 0.3 + (bend if score > 0 else 0))
    c.drawPath(p, stroke=1, fill=0)


def _pdf(v: dict) -> bytes:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas as rl
    buf = io.BytesIO()
    pw_, ph = landscape(A3)
    c = rl.Canvas(buf, pagesize=(pw_, ph))
    c.setTitle(v["title"])
    m = 30
    n_st = max(1, len(v["stages"]))
    lab = 90
    cw = (pw_ - 2 * m - lab) / n_st
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(_rgb("1F2328"))
    c.drawString(m, ph - m - 14, v["title"][:110])
    c.setFont("Helvetica", 10)
    c.setFillColor(_rgb("5B6775"))
    c.drawString(m, ph - m - 30, v["subtitle"][:200])
    if v["personas"]:
        c.drawString(m, ph - m - 44, ("Personas: " + ", ".join(r["text"] for r in v["personas"] if r["state"] != "removed"))[:220])
    y = ph - m - 56
    for n, s in enumerate(v["stages"]):
        x = m + lab + n * cw
        fill = STYLE[s["state"]][0] if s["state"] != "same" else "1F5FB8"
        c.setFillColor(_rgb(fill))
        c.setStrokeColor(_rgb(STYLE[s["state"]][1] if s["state"] != "same" else "1F5FB8"))
        c.rect(x + 1, y - 26, cw - 4, 26, stroke=1, fill=1)
        c.setFillColor(_rgb("FFFFFF" if s["state"] == "same" else STYLE[s["state"]][2]))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 6, y - 17, s["name"][:int(cw / 6)])
    y -= 34
    size = 7.5
    for code in _rows_shown(v):
        if code == "step":
            ch = 90
            c.setFillColor(_rgb("1F2328"))
            c.setFont("Helvetica-Bold", 9)
            c.drawString(m, y - ch / 2, "Emotion")
            zero = y - ch / 2
            c.setStrokeColor(_rgb("C9D1D9"))
            c.setDash(3, 3)
            c.line(m + lab, zero, m + lab + cw * n_st, zero)
            c.setDash()
            per: dict[int, int] = {}
            for n, _r in _steps(v):
                per[n] = per.get(n, 0) + 1
            seen: dict[int, int] = {}
            pts = []
            for n, r in _steps(v):
                i = seen.get(n, 0)
                seen[n] = i + 1
                if r.get("score") is None:
                    continue
                pts.append((m + lab + n * cw + (i + 1) * cw / (per[n] + 1), zero + r["score"] * (ch / 2 - 10) / 2, r["score"]))
            c.setStrokeColor(_rgb("1F5FB8"))
            c.setLineWidth(1.5)
            for (x1, y1, _s), (x2, y2, _t) in zip(pts, pts[1:], strict=False):
                c.line(x1, y1, x2, y2)
            for x1, y1, sc in pts:
                _face(c, x1, y1, 7, sc)
            c.setLineWidth(1)
            y -= ch + 6
        rows = [s["parts"].get(code, []) for s in v["stages"]]
        heights = []
        for rr in rows:
            h = 0
            for r in rr:
                lines = (simpleSplit(r["was_text"], "Helvetica", size, cw - 16) if r["was_text"] else []) + simpleSplit(r["text"], "Helvetica", size, cw - 16)
                h += len(lines) * (size + 2) + 8
            heights.append(h)
        rh = max([22] + heights)
        if y - rh < m:
            c.showPage()
            y = ph - m
        c.setFillColor(_rgb("1F2328"))
        c.setFont("Helvetica-Bold", 9)
        for k, ln in enumerate(simpleSplit(v["labels"].get(code, code), "Helvetica-Bold", 9, lab - 6)):
            c.drawString(m, y - 10 - k * 11, ln)
        c.setStrokeColor(_rgb("D0D7DE"))
        c.line(m, y + 2, m + lab + cw * n_st, y + 2)
        for n, rr in enumerate(rows):
            cy = y
            for r in rr:
                fill, stroke, font = STYLE[r["state"]]
                n_old = len(simpleSplit(r["was_text"], "Helvetica", size, cw - 16)) if r["was_text"] else 0
                lines = (simpleSplit(r["was_text"], "Helvetica", size, cw - 16) if r["was_text"] else []) + simpleSplit(r["text"], "Helvetica", size, cw - 16)
                ih = len(lines) * (size + 2) + 6
                x = m + lab + n * cw
                c.setFillColor(_rgb(fill))
                c.setStrokeColor(_rgb(stroke))
                c.roundRect(x + 2, cy - ih, cw - 6, ih, 3, stroke=1, fill=1)
                ly = cy - size - 2
                for k, ln in enumerate(lines):
                    old = k < n_old
                    c.setFillColor(_rgb("CF222E" if old else font))
                    c.setFont("Helvetica", size)
                    c.drawString(x + 6, ly, ln)
                    if old or r["state"] == "removed":
                        c.setStrokeColor(_rgb("CF222E"))
                        c.line(x + 6, ly + size * 0.3, x + 6 + c.stringWidth(ln, "Helvetica", size), ly + size * 0.3)
                    ly -= size + 2
                if code == "step" and r.get("score") is not None:
                    _face(c, x + cw - 14, cy - 9, 5, r["score"])
                cy -= ih + 4
        y -= rh + 8
    links = [s["links"] for s in v["stages"]]
    if any(links):
        c.setFillColor(_rgb("1F2328"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(m, y - 10, "Linked elements")
        for n, ls in enumerate(links):
            for k, x_ in enumerate(ls[:8]):
                c.setFillColor(_rgb("CF222E" if x_["state"] == "removed" else "1A7F37" if x_["state"] == "added" else "5B6775"))
                c.setFont("Helvetica", 7)
                c.drawString(m + lab + n * cw + 4, y - 10 - k * 9, f"{x_['entity_type']}: {x_['name']}"[:int(cw / 3.6)])
    c.showPage()
    c.save()
    return buf.getvalue()


def _pptx(v: dict) -> bytes:
    """One slide: the stages across, a text box per kind of part in each stage, the emotion as a row of faces and a
    line through them. Added green, changed amber with the old text struck through, removed red and struck through."""
    n_st = max(1, len(v["stages"]))
    left, top, width = 457200, 1066800, 11277600
    lab = 1100000
    cw = (width - lab) // n_st
    shapes, sid = [], 3

    def run(t, colour="1F2328", strike=False, bold=False, sz=900):
        b = ' b="1"' if bold else ""
        st = ' strike="sngStrike"' if strike else ""
        return (f'<a:r><a:rPr lang="en-GB" sz="{sz}"{b}{st}><a:solidFill><a:srgbClr val="{colour}"/></a:solidFill></a:rPr>'
                f'<a:t>{escape(t)}</a:t></a:r>')

    def box(name, x, y, w, h, paras, fill="FFFFFF", line="D0D7DE", geom="rect", anchor="t"):
        nonlocal sid
        sid += 1
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{escape(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
                f'<p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="{int(h)}"/></a:xfrm>'
                f'<a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
                f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln></p:spPr>'
                f'<p:txBody><a:bodyPr wrap="square" lIns="45720" tIns="27432" rIns="45720" bIns="27432" anchor="{anchor}">'
                '<a:normAutofit fontScale="70000" lnSpcReduction="10000"/></a:bodyPr><a:lstStyle/>' + "".join(paras) + "</p:txBody></p:sp>")

    for n, s in enumerate(v["stages"]):
        fill = "1F5FB8" if s["state"] == "same" else STYLE[s["state"]][0]
        font = "FFFFFF" if s["state"] == "same" else STYLE[s["state"]][2]
        shapes.append(box(s["name"], left + lab + n * cw, top, cw - 50000, 380000,
                          [f"<a:p>{run(s['name'], font, bold=True, sz=1100, strike=s['state'] == 'removed')}</a:p>"], fill, fill, "homePlate", "ctr"))
    y = top + 450000
    rows = _rows_shown(v)
    avail = 6858000 - 150000 - y         # the slide is 7.5 inches high
    rh = avail // max(1, len(rows) + 1)
    for code in rows:
        if code == "step":
            shapes.append(box("Emotion", left, y, lab - 50000, rh, [f"<a:p>{run('Emotion', bold=True, sz=1000)}</a:p>"], "FFFFFF", "FFFFFF"))
            per: dict[int, int] = {}
            for n, _r in _steps(v):
                per[n] = per.get(n, 0) + 1
            seen: dict[int, int] = {}
            pts = []
            for n, r in _steps(v):
                i = seen.get(n, 0)
                seen[n] = i + 1
                if r.get("score") is None:
                    continue
                pts.append((left + lab + n * cw + (i + 1) * cw / (per[n] + 1), y + rh / 2 - r["score"] * (rh / 2 - 120000) / 2, r["score"]))
            for (x1, y1, _a), (x2, y2, _b) in zip(pts, pts[1:], strict=False):
                sid += 1
                flip = ' flipV="1"' if y2 < y1 else ""
                shapes.append(f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{sid}" name="curve"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
                              f'<p:spPr><a:xfrm{flip}><a:off x="{int(x1)}" y="{int(min(y1, y2))}"/><a:ext cx="{int(x2 - x1)}" cy="{int(abs(y2 - y1))}"/></a:xfrm>'
                              '<a:prstGeom prst="line"><a:avLst/></a:prstGeom><a:ln w="19050"><a:solidFill><a:srgbClr val="1F5FB8"/></a:solidFill></a:ln></p:spPr></p:cxnSp>')
            for x1, y1, sc in pts:
                shapes.append(box("emotion", x1 - 110000, y1 - 110000, 220000, 220000,
                                  [f'<a:p><a:pPr algn="ctr"/>{run(("+" if sc > 0 else "") + str(sc), SCORE_COLOUR[sc], bold=True, sz=800)}</a:p>'],
                                  "FFFFFF", SCORE_COLOUR[sc], "ellipse", "ctr"))
            y += rh
        shapes.append(box(v["labels"].get(code, code), left, y, lab - 50000, rh,
                          [f"<a:p>{run(v['labels'].get(code, code), bold=True, sz=1000)}</a:p>"], "FFFFFF", "FFFFFF"))
        for n, s in enumerate(v["stages"]):
            paras = []
            for r in s["parts"].get(code, []):
                colour = STYLE[r["state"]][2] if r["state"] != "same" else "1F2328"
                body = (run(r["was_text"], "CF222E", strike=True) + run("  ") if r["was_text"] else "") + \
                    run(r["text"] + (f" ({'+' if r['score'] > 0 else ''}{r['score']})" if code == "step" and r.get("score") is not None else ""),
                        colour, strike=r["state"] == "removed")
                paras.append(f'<a:p><a:pPr marL="114300" indent="-114300"><a:buChar char="•"/></a:pPr>{body}</a:p>')
            shapes.append(box(f"{s['name']} {code}", left + lab + n * cw, y, cw - 50000, rh - 40000, paras or ["<a:p/>"], "F6F8FA", "D0D7DE"))
        y += rh
    head = (f'<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm>'
            '<a:off x="457200" y="228600"/><a:ext cx="11277600" cy="762000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
            f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p>{run(v["title"], bold=True, sz=2400)}</a:p><a:p>{run(v["subtitle"], "5B6775", sz=1200)}</a:p>'
            '</p:txBody></p:sp>')
    return bf.pptx_slide(v["title"], head + "".join(shapes))
