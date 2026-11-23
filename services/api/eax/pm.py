"""Project management for an architecture project (Release 12, R12.4; D879, D884, D889; TOGAF Series Guide: Project
Management and the ADM, G188): what the project's Project plan tab shows and does.

* **Settings**, chosen at setup and changed later by the Project Admin or Lead Architect:
  - how the project records who is Responsible, Accountable, Consulted and Informed (RACI): not at all, per phase, per
    deliverable or per step (D884: "User chooses during project setup, they may choose not to have RACI");
  - the **approval gates**: the phases, chosen by the architect, that may only be marked complete once each of their
    chosen deliverables has an approved document (D879: "Approval gates chosen by the architect"). None by default, so
    a project that chooses none works as before;
  - the **roadmap's period**: any start and end (both empty: all of it), and its marks (months, quarters or years).
* **A plan** of the phases (a start and an end for each), the **milestones** (due, done, late) and the **status
  reports** (red, amber or green, with a summary and the next steps).

Every existing project has its settings row (RACI none, no gates: as it was), made by the seed at start (D884). Rules
here, rows in proj.pm_settings, proj.phase_plans, proj.milestones, proj.raci and proj.status_reports (D248).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from . import projects as pj
from .metamodel_edit import EditError

RACI_MODES = {"none": "No RACI", "phase": "Per phase", "deliverable": "Per deliverable", "step": "Per step"}
LETTERS = {"R": "Responsible", "A": "Accountable", "C": "Consulted", "I": "Informed"}
RAG = ("green", "amber", "red")
MARKS = ("month", "quarter", "year")

_rows, _one = pj._rows, pj._one


def _text(v: Any, limit: int = 500) -> str:
    return str(v or "").strip()[:limit]


def _date(v: Any, what: str, optional: bool = False) -> date | None:
    if v in (None, "") and optional:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError as exc:
        raise EditError(f"{what} is a date (YYYY-MM-DD).") from exc


def _project(pc, project: Any, user, what: str = "read") -> dict:
    p = pj.project_row(pc, project)
    pj._need(pc, p, user, what)
    return p


def _phases(pc, p: dict) -> list[dict]:
    """The phases the project runs (those with steps in its current cycle), in the ADM's order."""
    return _rows(pc, """SELECT l.code, l.name FROM proj.lib_phases l
                         WHERE EXISTS (SELECT 1 FROM proj.steps s WHERE s.project_id = :p AND s.cycle = :c AND s.phase = l.code)
                         ORDER BY l.sort_order""", p=p["id"], c=p.get("cycle") or 1)


def settings(pc, p: dict) -> dict:
    """The project's settings (the defaults when it has no row yet)."""
    r = _one(pc, "SELECT * FROM proj.pm_settings WHERE project_id = :p", p=p["id"]) or {}
    return {"raci": r.get("raci") or "none", "gates": list(r.get("gates") or []),
            "roadmap_from": r["roadmap_from"].isoformat() if r.get("roadmap_from") else None,
            "roadmap_to": r["roadmap_to"].isoformat() if r.get("roadmap_to") else None,
            "roadmap_marks": r.get("roadmap_marks") or "year", "modified_by": r.get("modified_by"), "modified_at": r.get("modified_at")}


def _save(pc, p: dict, user, s: dict) -> None:
    pc.execute(text("""INSERT INTO proj.pm_settings (project_id, raci, gates, roadmap_from, roadmap_to, roadmap_marks, modified_by, modified_at)
                       VALUES (:p, :r, CAST(:g AS text[]), :f, :t, :m, :u, now())
                       ON CONFLICT (project_id) DO UPDATE SET raci = :r, gates = CAST(:g AS text[]), roadmap_from = :f, roadmap_to = :t,
                              roadmap_marks = :m, modified_by = :u, modified_at = now()"""),
               {"p": p["id"], "r": s["raci"], "g": list(s["gates"]), "f": s["roadmap_from"], "t": s["roadmap_to"], "m": s["roadmap_marks"],
                "u": user.username if user else "system"})


def _checked(pc, p: dict, d: dict, now: dict) -> dict:
    """The settings as they would be after d, checked."""
    s = dict(now)
    if "raci" in d:
        if d["raci"] not in RACI_MODES:
            raise EditError(f"RACI is one of: {', '.join(RACI_MODES)}.")
        s["raci"] = d["raci"]
    if "gates" in d:
        gates = [str(g).strip() for g in (d["gates"] or []) if str(g).strip()]
        known = {r["code"] for r in _rows(pc, "SELECT code FROM proj.lib_phases")}
        bad = [g for g in gates if g not in known]
        if bad:
            raise EditError(f"No phase {', '.join(bad)}: a gate is the end of one of the ADM's phases.")
        s["gates"] = sorted(set(gates), key=gates.index)
    if "roadmap_from" in d:
        s["roadmap_from"] = _date(d["roadmap_from"], "The roadmap's start", optional=True)
    if "roadmap_to" in d:
        s["roadmap_to"] = _date(d["roadmap_to"], "The roadmap's end", optional=True)
    if "roadmap_marks" in d:
        if d["roadmap_marks"] not in MARKS:
            raise EditError(f"The roadmap's marks are one of: {', '.join(MARKS)}.")
        s["roadmap_marks"] = d["roadmap_marks"]
    f, t = s["roadmap_from"], s["roadmap_to"]
    if f and t and str(t) <= str(f):
        raise EditError("The roadmap's end comes after its start.")
    return s


def from_wizard(pc, p: dict, user, d: dict | None) -> None:
    """The setup wizard's choices (RACI, the gates, the roadmap's period); none: RACI none, no gates."""
    _save(pc, p, user, _checked(pc, p, d or {}, settings(pc, p)))


def set_settings(pc, project: Any, user, d: dict) -> dict:
    """Changes the settings (Project Admin or Lead Architect). Changing how RACI is recorded keeps what was recorded
    the other way (it shows again if the project goes back)."""
    p = _project(pc, project, user, "admin")
    s = _checked(pc, p, d, settings(pc, p))
    _save(pc, p, user, s)
    return {"message": "The project plan's settings are saved.", "settings": settings(pc, p)}


# ---------------------------------------------------------------- gates
def gate_waiting(pc, p: dict, phase: str) -> list[str]:
    """The chosen deliverables of a gated phase that have no approved document yet ([] when the phase is no gate)."""
    if phase not in settings(pc, p)["gates"]:
        return []
    return [r["name"] for r in _rows(pc, """
        SELECT i.name FROM proj.items i
         WHERE i.project_id = :p AND i.cycle = :c AND i.phase = :ph AND i.chosen AND i.kind = 'Deliverable'
           AND NOT EXISTS (SELECT 1 FROM proj.documents d WHERE d.item_id = i.id AND d.archived_at IS NULL AND d.deleted_at IS NULL
                                                          AND d.state IN ('Approved', 'Accepted'))
         ORDER BY i.name""", p=p["id"], c=p.get("cycle") or 1, ph=phase)]


def check_gate(pc, p: dict, phase: str) -> None:
    """A gated phase is only marked complete when each of its chosen deliverables is approved."""
    waiting = gate_waiting(pc, p, phase)
    if waiting:
        shown = ", ".join(waiting[:8]) + (f" and {len(waiting) - 8} more" if len(waiting) > 8 else "")
        raise EditError(f"Phase {phase} is an approval gate: each of its deliverables needs an approved document before it is "
                        f"complete. Waiting: {shown}.", 409)


# ---------------------------------------------------------------- the plan of the phases
def set_phase_plan(pc, project: Any, user, phase: str, d: dict) -> dict:
    """A phase's planned start and end ({starts_on, ends_on}); both empty: no plan for it."""
    p = _project(pc, project, user, "admin")
    if phase not in {r["code"] for r in _phases(pc, p)}:
        raise EditError(f"The project does not run phase {phase}.", 404)
    s, e = _date(d.get("starts_on"), "The start", optional=True), _date(d.get("ends_on"), "The end", optional=True)
    if not s and not e:
        pc.execute(text("DELETE FROM proj.phase_plans WHERE project_id = :p AND cycle = :c AND phase = :ph"),
                   {"p": p["id"], "c": p.get("cycle") or 1, "ph": phase})
        return {"message": f"Phase {phase} has no plan now."}
    if not (s and e):
        raise EditError("Give the phase a start and an end.")
    if e < s:
        raise EditError("The end comes on or after the start.")
    pc.execute(text("""INSERT INTO proj.phase_plans (project_id, cycle, phase, starts_on, ends_on) VALUES (:p, :c, :ph, :s, :e)
                       ON CONFLICT (project_id, cycle, phase) DO UPDATE SET starts_on = :s, ends_on = :e"""),
               {"p": p["id"], "c": p.get("cycle") or 1, "ph": phase, "s": s, "e": e})
    return {"message": f"Phase {phase} is planned from {s} to {e}."}


# ---------------------------------------------------------------- milestones
def _milestone(pc, p: dict, m: Any) -> dict:
    r = _one(pc, "SELECT * FROM proj.milestones WHERE project_id = :p AND guid::text = :g", p=p["id"], g=str(m))
    if not r:
        raise EditError("No such milestone on this project.", 404)
    return r


def add_milestone(pc, project: Any, user, d: dict) -> dict:
    """Adds a milestone ({name, due_on, phase, note}) to the project; anyone who contributes may."""
    p = _project(pc, project, user, "contribute")
    name = _text(d.get("name"), 200)
    if not name:
        raise EditError("Give the milestone a name.")
    due = _date(d.get("due_on"), "The milestone's date")
    r = _one(pc, """INSERT INTO proj.milestones (project_id, name, due_on, phase, note, created_by)
                    VALUES (:p, :n, :d, :ph, :no, :u) RETURNING guid::text AS id""",
             p=p["id"], n=name, d=due, ph=_text(d.get("phase"), 10), no=_text(d.get("note"), 1000), u=user.username)
    return {"message": f"Milestone {name} is due on {due}.", "id": r["id"]}


def change_milestone(pc, project: Any, user, m: Any, d: dict) -> dict:
    """A milestone's name, date, phase or note, or marked done ({done: true}) or not done."""
    p = _project(pc, project, user, "contribute")
    r = _milestone(pc, p, m)
    name = _text(d.get("name", r["name"]), 200) or r["name"]
    due = _date(d["due_on"], "The milestone's date") if "due_on" in d else r["due_on"]
    done = d.get("done")
    pc.execute(text("""UPDATE proj.milestones SET name = :n, due_on = :d, phase = :ph, note = :no,
                              done_at = CASE WHEN :set THEN CASE WHEN :done THEN coalesce(done_at, now()) END ELSE done_at END,
                              done_by = CASE WHEN :set THEN CASE WHEN :done THEN coalesce(done_by, :u) END ELSE done_by END
                        WHERE id = :i"""),
               {"n": name, "d": due, "ph": _text(d.get("phase", r["phase"]), 10), "no": _text(d.get("note", r["note"]), 1000),
                "set": done is not None, "done": bool(done), "u": user.username, "i": r["id"]})
    return {"message": f"Milestone {name} is saved."}


def delete_milestone(pc, project: Any, user, m: Any) -> dict:
    """Removes a milestone (the Project Admin or Lead Architect)."""
    p = _project(pc, project, user, "admin")
    r = _milestone(pc, p, m)
    pc.execute(text("DELETE FROM proj.milestones WHERE id = :i"), {"i": r["id"]})
    return {"message": f"Milestone {r['name']} is removed."}


# ---------------------------------------------------------------- RACI
_COL = {"phase": "phase", "deliverable": "item_id", "step": "step_id"}


def _refs(pc, p: dict, scope: str) -> dict[str, tuple[str, Any]]:
    """What RACI can be recorded against: {reference: (name, the value kept)}. A phase by its code, a deliverable by
    its item's guid, a step by its id."""
    c = p.get("cycle") or 1
    if scope == "phase":
        return {r["code"]: (r["name"], r["code"]) for r in _phases(pc, p)}
    if scope == "deliverable":
        return {r["guid"]: (r["name"], r["id"]) for r in _rows(pc, """SELECT id, guid::text AS guid, phase || ': ' || name AS name FROM proj.items
                                                                  WHERE project_id = :p AND cycle = :c AND chosen ORDER BY phase, name""",
                                                             p=p["id"], c=c)}
    return {str(r["id"]): (r["name"], r["id"]) for r in _rows(pc, """SELECT id, phase || ': ' || name AS name FROM proj.steps
                                                                 WHERE project_id = :p AND cycle = :c AND NOT removed ORDER BY phase, seq""",
                                                            p=p["id"], c=c)}


def _ref_of(r: dict, scope: str, by_value: dict) -> str | None:
    """The reference a stored RACI row is shown under."""
    return by_value.get(r[_COL[scope]])


def set_raci(pc, project: Any, user, ref: str, assignments: dict) -> dict:
    """Who is R, A, C and I for one phase, deliverable or step, as the project records RACI: {username: [letters]}.
    Everyone named is one of the project's people; there is at most one Accountable."""
    p = _project(pc, project, user, "admin")
    mode = settings(pc, p)["raci"]
    if mode == "none":
        raise EditError("The project does not record RACI: choose per phase, per deliverable or per step in the plan's settings first.", 409)
    refs = _refs(pc, p, mode)
    if str(ref) not in refs:
        raise EditError(f"No such {mode} on this project.", 404)
    people = {r["username"].lower() for r in _rows(pc, "SELECT DISTINCT username FROM proj.members WHERE project_id = :p", p=p["id"])}
    rows, accountable = [], []
    for u, letters in (assignments or {}).items():
        u = str(u).strip().lower()
        letters = [str(x).upper() for x in (letters if isinstance(letters, (list, tuple)) else [letters]) if str(x).strip()]
        if not letters:
            continue
        if u not in people:
            raise EditError(f"{u} is not one of the project's people: add them on the Organisation tab first.")
        bad = [x for x in letters if x not in LETTERS]
        if bad:
            raise EditError(f"RACI letters are R, A, C and I, not {', '.join(bad)}.")
        for x in sorted(set(letters)):
            rows.append((u, x))
            if x == "A":
                accountable.append(u)
    if len(accountable) > 1:
        raise EditError(f"One person is Accountable, not {len(accountable)} ({', '.join(accountable)}).")
    col, value = _COL[mode], refs[str(ref)][1]
    pc.execute(text(f"DELETE FROM proj.raci WHERE project_id = :p AND scope = :s AND {col} = :v"), {"p": p["id"], "s": mode, "v": value})
    for u, x in rows:
        pc.execute(text(f"INSERT INTO proj.raci (project_id, scope, {col}, username, letter) VALUES (:p, :s, :v, :u, :x)"),
                   {"p": p["id"], "s": mode, "v": value, "u": u, "x": x})
    return {"message": f"RACI for {refs[str(ref)][0]} is saved.", "accountable": accountable[0] if accountable else None}


# ---------------------------------------------------------------- status
def add_status(pc, project: Any, user, d: dict) -> dict:
    """Records how the project stands: red, amber or green, a summary and the next steps."""
    p = _project(pc, project, user, "contribute")
    rag = str(d.get("rag") or "").lower()
    if rag not in RAG:
        raise EditError("The status is green, amber or red.")
    summary = _text(d.get("summary"), 4000)
    if not summary:
        raise EditError("Say in a line or two how the project stands.")
    pc.execute(text("INSERT INTO proj.status_reports (project_id, by_user, rag, summary, next_steps) VALUES (:p, :u, :r, :s, :n)"),
               {"p": p["id"], "u": user.username, "r": rag, "s": summary, "n": _text(d.get("next_steps"), 4000)})
    return {"message": f"Status reported: {rag}."}


# ---------------------------------------------------------------- what the tab shows
def overview(pc, project: Any, user) -> dict:
    """What the Project plan tab shows: the settings, the phases with their plan, state and gate, the milestones,
    the RACI, the status reports, the people, and how many are late."""
    p = _project(pc, project, user, "read")
    c = p.get("cycle") or 1
    s = settings(pc, p)
    today = date.today()
    plans = {r["phase"]: r for r in _rows(pc, "SELECT * FROM proj.phase_plans WHERE project_id = :p AND cycle = :c", p=p["id"], c=c)}
    done = pj.phases_done(pc, p)
    phases = []
    for ph in _phases(pc, p):
        pl = plans.get(ph["code"])
        late = bool(pl and ph["code"] not in done and pl["ends_on"] < today)
        phases.append({"code": ph["code"], "name": ph["name"], "starts_on": pl["starts_on"].isoformat() if pl else None,
                       "ends_on": pl["ends_on"].isoformat() if pl else None, "complete": ph["code"] in done, "late": late,
                       "gate": ph["code"] in s["gates"], "waiting": gate_waiting(pc, p, ph["code"]) if ph["code"] in s["gates"] else []})
    miles = _rows(pc, """SELECT guid::text AS id, name, due_on, phase, note, done_at, done_by FROM proj.milestones
                          WHERE project_id = :p ORDER BY due_on, name""", p=p["id"])
    for m in miles:
        m["late"] = not m["done_at"] and m["due_on"] < today
        m["due_on"] = m["due_on"].isoformat()
    raci = {}
    if s["raci"] != "none":
        refs = _refs(pc, p, s["raci"])
        by_value = {v: k for k, (_n, v) in refs.items()}
        got = _rows(pc, "SELECT phase, item_id, step_id, username, letter FROM proj.raci WHERE project_id = :p AND scope = :s "
                        "ORDER BY username, letter", p=p["id"], s=s["raci"])
        raci = {"scope": s["raci"], "rows": [{"ref": k, "name": n, "people": {}} for k, (n, _v) in refs.items()]}
        by = {r["ref"]: r for r in raci["rows"]}
        for g in got:
            k = _ref_of(g, s["raci"], by_value)
            if k in by:
                by[k]["people"].setdefault(g["username"], []).append(g["letter"])
        raci["no_accountable"] = sum(1 for r in raci["rows"] if not any("A" in v for v in r["people"].values()))
    status = _rows(pc, """SELECT at, by_user, rag, summary, next_steps FROM proj.status_reports WHERE project_id = :p
                           ORDER BY at DESC LIMIT 20""", p=p["id"])
    people = sorted({r["username"] for r in _rows(pc, "SELECT username FROM proj.members WHERE project_id = :p", p=p["id"])})
    return {"settings": s, "raci_modes": RACI_MODES, "letters": LETTERS, "phases": phases, "milestones": miles, "raci": raci,
            "status": status, "people": people,
            "late": sum(1 for x in phases if x["late"]) + sum(1 for m in miles if m["late"]),
            "may_change": bool(pj.my_roles(pc, p, user) & pj.ADMINS) or pj._super(user)}


def count(pc, p: dict) -> dict:
    """What the project page shows of the plan: the settings, the milestones left and the latest status."""
    s = settings(pc, p)
    left = _one(pc, "SELECT count(*) AS n, count(*) FILTER (WHERE due_on < current_date) AS late FROM proj.milestones "
                    "WHERE project_id = :p AND done_at IS NULL", p=p["id"]) or {}
    last = _one(pc, "SELECT rag, at FROM proj.status_reports WHERE project_id = :p ORDER BY at DESC LIMIT 1", p=p["id"])
    return {"raci": s["raci"], "gates": s["gates"], "milestones_left": int(left.get("n") or 0), "milestones_late": int(left.get("late") or 0),
            "status": last["rag"] if last else None, "roadmap_from": s["roadmap_from"], "roadmap_to": s["roadmap_to"],
            "roadmap_marks": s["roadmap_marks"]}
