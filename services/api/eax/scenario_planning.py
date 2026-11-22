"""Scenario planning and game theory in a project, run by the person's AI (Release 10; D788, D818, D857).

The wizard runs through MCP (eax/mcp_scenario_planning.py), started in words ("run the scenario planning wizard for
project X"); the AI asks the questions, does the work from the project's documents and models, suggests, and saves each
part after the person's yes (a preview, then a confirm token, D458). No screen makes or changes any of it; the project's
**Scenario planning** tab and the project report show it, read-only (D818).

A **study** is kept in the project's own tables (D857 (1)), each run of the wizard **a dated version** (D857 (7)): a
draft while the wizard works, done when finished; the newest done version is the one shown, the earlier ones kept to
compare. Its parts:

* the **question** it answers and the **template** chosen (D857 (3)): the two-uncertainty grid (four futures), three to
  five futures, one uncertainty low to high, or players and games only;
* the **driving forces** (economic, technology, regulation, social, market, other), each rated for impact and
  uncertainty (1 to 5); the **critical uncertainties** (each with its two ends);
* the **futures**, each with its story, what is true in it, when, where it sits on each uncertainty, and the scenario
  model that answers it (D492) if there is one; the **signposts** of each future (what to watch and the level that says
  it is coming), asked about at each project review and marked seen or not (D857 (6));
* the **players** (the organisation and the others who decide: competitors, regulators, suppliers, business units,
  customers), and their **games**: moves at once (a payoff table) or in turn (a tree), with values in any form (D857 (5));
* the **options** (each may point to a scenario model) and their **scores in each future**;
* the **working** (eax/game_theory.py, never the AI: best replies, dominant options, stable outcomes, mixed strategies,
  games worked back from the end, the most robust option and the least regret) and the **recommendation**.

Always in a project (D857 (2)): the AI reads every document and model of the project and may make as many scenario
models as are needed (eax/scenarios.py make_scenario). Reading needs a role on the project; changing needs a
contributing role. Nothing here is logic in the database (D248).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from . import game_theory as gt
from . import projects as pj
from .metamodel_edit import EditError

PARTS = ("forces", "uncertainties", "futures", "signposts", "players", "games", "options", "scores")
FORCE_KINDS = ("economic", "technology", "regulation", "social", "market", "environment", "other")
PLAYER_KINDS = ("organisation", "competitor", "regulator", "supplier", "partner", "business unit", "customer", "other")
REVIEW_DAYS = 90                    # a signpost not marked for this long is asked about again at the next review
MAX_ITEMS = 60

TEMPLATES = {
    "grid": {"name": "Two uncertainties, four futures (the scenario grid)",
             "for": "The usual choice: the two most important and most uncertain forces make a grid of four futures.",
             "uncertainties": (2, 2), "futures": (4, 4)},
    "range": {"name": "Three to five futures",
              "for": "When a grid does not fit: three to five futures, each a coherent story, from any number of uncertainties.",
              "uncertainties": (1, 6), "futures": (3, 5)},
    "single": {"name": "One uncertainty, low to high",
               "for": "When one force decides most: two or three futures along it (low, middle, high).",
               "uncertainties": (1, 1), "futures": (2, 3)},
    "games": {"name": "Players and games only",
              "for": "When the futures are known and the question is how the others will move: the players, their games, "
                     "and the options against them.",
              "uncertainties": (0, 0), "futures": (0, 0)},
}
STEPS = [
    "1. The question the study answers, and a template (sp_templates; the person picks, or asks you to suggest).",
    "2. The driving forces, each rated for impact and uncertainty (1 to 5), from the project's documents and models.",
    "3. The critical uncertainties (the most important and most uncertain forces), each with its two ends.",
    "4. The futures: name, story, what is true in it, when, where it sits on each uncertainty, the scenario model if any.",
    "5. The signposts of each future: what to watch and the level that says it is coming.",
    "6. The players (the organisation first, then competitors, regulators, suppliers...) and their goals.",
    "7. The games: moves at once (a payoff table) or in turn (a tree), each value a number, money, or words with a score.",
    "8. The options (each may point to a scenario model; make_scenario makes more) and their score in each future.",
    "9. Work it out (sp_work_out), explain it in plain words, and finish with the recommendation (sp_finish).",
]


def _rows(conn, sql: str, **p) -> list[dict]:
    return [dict(r) for r in conn.execute(text(sql), p).mappings().all()]


def _one(conn, sql: str, **p) -> dict | None:
    r = _rows(conn, sql, **p)
    return r[0] if r else None


def _now() -> datetime:
    return datetime.now(UTC)


def _text(v: Any, n: int = 4000) -> str:
    return " ".join(str(v or "").split())[:n] if n <= 300 else str(v or "").strip()[:n]


def _rate(v: Any, what: str) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError) as exc:
        raise EditError(f"{what} is 1 to 5.") from exc
    if not 1 <= n <= 5:
        raise EditError(f"{what} is 1 to 5.")
    return n


def templates() -> list[dict]:
    """The templates the person picks from (D857 (3)): key, name, what each is for, how many uncertainties and futures."""
    return [{"key": k, "name": t["name"], "for": t["for"],
             "uncertainties": f"{t['uncertainties'][0]} to {t['uncertainties'][1]}" if t["uncertainties"][0] != t["uncertainties"][1]
             else str(t["uncertainties"][0]),
             "futures": f"{t['futures'][0]} to {t['futures'][1]}" if t["futures"][0] != t["futures"][1] else str(t["futures"][0])}
            for k, t in TEMPLATES.items()]


# ---------------------------------------------------------------- reading
def _project(pc, project: Any, user, what: str = "read") -> dict:
    p = pj.project_row(pc, project)
    pj._need(pc, p, user, what)
    return p


def _run_out(r: dict, full: bool = True) -> dict:
    out = {"id": str(r["guid"]), "version": r["version"], "status": r["status"], "question": r["question"],
           "template": r["template"], "template_name": TEMPLATES.get(r["template"], {}).get("name", r["template"]),
           "organisation": r["organisation"], "recommendation": r["recommendation"], "recommended": r["recommended"],
           "created_by": r["created_by"], "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
           "finished_at": r["finished_at"].isoformat() if r.get("finished_at") else None}
    if full:
        for k in PARTS:
            out[k] = r[k] or []
        out["results"] = r["results"] or {}
    else:
        out["counts"] = {k: len(r[k] or []) for k in PARTS}
    return out


def _runs(pc, p: dict) -> list[dict]:
    return _rows(pc, "SELECT * FROM proj.sp_runs WHERE project_id = :p ORDER BY version DESC", p=p["id"])


def _draft(pc, p: dict) -> dict | None:
    return next((r for r in _runs(pc, p) if r["status"] == "draft"), None)


def _latest(pc, p: dict) -> dict | None:
    return next((r for r in _runs(pc, p) if r["status"] == "done"), None)


# ---------------------------------------------------------------- the rows (the only SQL that changes anything)
def _insert(pc, row: dict) -> None:
    pc.execute(text(f"""INSERT INTO proj.sp_runs (project_id, version, question, template, organisation, created_by, {', '.join(PARTS)})
                        VALUES (:project_id, :version, :question, :template, :organisation, :created_by,
                                {', '.join(f'CAST(:{k} AS jsonb)' for k in PARTS)})"""),
               {**row, **{k: json.dumps(row.get(k) or []) for k in PARTS}})


def _set(pc, run_id: int, **cols) -> None:
    sets = ", ".join(f"{k} = CAST(:{k} AS jsonb)" if k in PARTS or k == "results" else f"{k} = :{k}" for k in cols)
    stamp = ", finished_at = now()" if cols.get("status") == "done" else ""
    pc.execute(text(f"UPDATE proj.sp_runs SET {sets}, updated_at = now(){stamp} WHERE id = :run_id"),
               {"run_id": run_id, **{k: json.dumps(v, default=str) if k in PARTS or k == "results" else v for k, v in cols.items()}})


def _delete_draft(pc, run_id: int) -> None:
    pc.execute(text("DELETE FROM proj.sp_runs WHERE id = :r AND status = 'draft'"), {"r": run_id})


def _add_mark(pc, run_id: int, ref: str, seen: bool, note: str, by: str) -> None:
    pc.execute(text("""INSERT INTO proj.sp_signpost_marks (run_id, signpost, seen, note, marked_by)
                       VALUES (:r, :s, :seen, :n, :by)"""), {"r": run_id, "s": ref, "seen": seen, "n": note, "by": by})


def _marks(pc, run_id: int) -> list[dict]:
    return _rows(pc, """SELECT signpost, seen, note, marked_by, marked_at FROM proj.sp_signpost_marks WHERE run_id = :r
                         ORDER BY marked_at""", r=run_id)


def signposts_due(pc, run: dict | None, days: int = REVIEW_DAYS) -> list[dict]:
    """The latest study's signposts with their last mark; due when never marked, or not for `days`."""
    if not run:
        return []
    marks = {m["signpost"]: m for m in _marks(pc, run["id"])}
    out = []
    for s in run["signposts"] or []:
        m = marks.get(s.get("ref"))
        due = not m or m["marked_at"] < _now() - timedelta(days=days)
        out.append({**s, "last": ({"seen": m["seen"], "note": m["note"], "by": m["marked_by"], "at": m["marked_at"].isoformat()}
                                  if m else None), "due": due})
    return out


def count(pc, p: dict) -> int:
    """How many studies' versions a project has (the project page shows the tab when there is one)."""
    return len(_runs(pc, p))


def overview(pc, project: Any, user) -> dict:
    """The project's studies: every version (newest first), the newest done one in full with its working and its
    signposts (those due at this review marked), and the draft the wizard is working on, if any."""
    p = _project(pc, project, user)
    runs = _runs(pc, p)
    latest = next((r for r in runs if r["status"] == "done"), None)
    draft = next((r for r in runs if r["status"] == "draft"), None)
    due = signposts_due(pc, latest)
    return {"project": p["name"], "versions": [_run_out(r, full=False) for r in runs],
            "latest": _run_out(latest) if latest else None, "draft": _run_out(draft) if draft else None,
            "signposts": due, "signposts_due": sum(1 for s in due if s["due"]), "templates": templates(),
            "steps": STEPS}


def get_run(pc, project: Any, user, version: Any) -> dict:
    """One version of the project's study in full (1, 2, ... or v1), with its signposts' marks when finished."""
    p = _project(pc, project, user)
    try:
        v = int(str(version).lstrip("vV"))
    except ValueError as exc:
        raise EditError("A version is its number (1, 2, ...).", 404) from exc
    r = next((x for x in _runs(pc, p) if x["version"] == v), None)
    if not r:
        raise EditError(f"{p['name']} has no scenario planning version {v}.", 404)
    out = _run_out(r)
    if r["status"] == "done":
        out["signposts"] = signposts_due(pc, r)
    return out


# ---------------------------------------------------------------- checking each part
def _names(items: list[dict]) -> set[str]:
    return {str(i.get("name") or "").lower() for i in items}


def _list(items: Any, part: str) -> list[dict]:
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise EditError(f"{part} is a list of objects.")
    if len(items) > MAX_ITEMS:
        raise EditError(f"At most {MAX_ITEMS} {part}.")
    return items


def _unique(items: list[dict], part: str) -> None:
    seen = set()
    for i in items:
        n = str(i.get("name") or "").strip().lower()
        if not n:
            raise EditError(f"Each of the {part} needs a name.")
        if n in seen:
            raise EditError(f"Two {part} are called {i['name']}.")
        seen.add(n)


def _models(pc, p: dict) -> set[str]:
    """The names of the project's models (lower case): a future or an option may point to one."""
    links = [r["id"] for r in _rows(pc, "SELECT model_guid::text AS id FROM proj.project_models WHERE project_id = :p", p=p["id"])]
    if not links:
        return set()
    return {r["name"].lower() for r in _rows(pj.core(pc), """SELECT name FROM core.models WHERE guid::text = ANY (CAST(:g AS text[]))
                                                            AND NOT is_deleted""", g=links)}


def check(pc, p: dict, run: dict, part: str, items: Any) -> list[dict]:
    """One part made clean, or refused in words; checked against the other parts already saved."""
    if part not in PARTS:
        raise EditError(f"A part is one of: {', '.join(PARTS)}.")
    items = _list(items, part)
    out: list[dict] = []
    if part == "forces":
        _unique(items, "forces")
        for i in items:
            kind = str(i.get("kind") or "other").lower()
            if kind not in FORCE_KINDS:
                raise EditError(f"A force's kind is one of: {', '.join(FORCE_KINDS)}.")
            out.append({"name": _text(i["name"], 200), "kind": kind, "impact": _rate(i.get("impact"), f"{i['name']}: impact"),
                        "uncertainty": _rate(i.get("uncertainty"), f"{i['name']}: uncertainty"), "note": _text(i.get("note"))})
    elif part == "uncertainties":
        _unique(items, "uncertainties")
        for i in items:
            if not i.get("low") or not i.get("high"):
                raise EditError(f"{i['name']} needs its two ends: low and high.")
            out.append({"name": _text(i["name"], 200), "low": _text(i["low"], 200), "high": _text(i["high"], 200),
                        "force": _text(i.get("force"), 200)})
    elif part == "futures":
        _unique(items, "futures")
        unc = {u["name"].lower(): u for u in run["uncertainties"] or []}
        models = _models(pc, p)
        for i in items:
            pos = i.get("positions") or {}
            if not isinstance(pos, dict):
                raise EditError(f"{i['name']}: positions is {{uncertainty: low | high | words}}.")
            for k in pos:
                if str(k).lower() not in unc:
                    raise EditError(f"{i['name']} is placed on '{k}', which is not one of the uncertainties saved.")
            model = _text(i.get("model"), 200)
            if model and model.lower() not in models:
                raise EditError(f"{i['name']} points to the model '{model}', which is not in the project (make_scenario makes one).")
            true = i.get("true") or []
            out.append({"name": _text(i["name"], 200), "story": _text(i.get("story"), 8000),
                        "true": [_text(t, 300) for t in (true if isinstance(true, list) else [true])][:30],
                        "when": _text(i.get("when"), 100), "positions": {str(k): _text(v, 200) for k, v in pos.items()},
                        "model": model})
    elif part == "signposts":
        fut = _names(run["futures"] or [])
        for n, i in enumerate(items, 1):
            if str(i.get("future") or "").lower() not in fut:
                raise EditError(f"A signpost belongs to one of the futures saved: '{i.get('future')}' is not one.")
            if not i.get("sign"):
                raise EditError("Each signpost needs its sign (what would tell us).")
            out.append({"ref": f"SP-{n}", "future": _text(i["future"], 200), "sign": _text(i["sign"], 500),
                        "watch": _text(i.get("watch"), 500), "level": _text(i.get("level"), 300)})
    elif part == "players":
        _unique(items, "players")
        orgs = [i for i in items if str(i.get("kind") or "").lower() == "organisation"]
        if len(orgs) > 1:
            raise EditError("Only one player is the organisation itself.")
        for i in items:
            kind = str(i.get("kind") or "other").lower()
            if kind not in PLAYER_KINDS:
                raise EditError(f"A player's kind is one of: {', '.join(PLAYER_KINDS)}.")
            out.append({"name": _text(i["name"], 200), "kind": kind, "stakeholder": _text(i.get("stakeholder"), 200),
                        "goals": _text(i.get("goals"), 2000)})
    elif part == "games":
        _unique(items, "games")
        known = {pl["name"] for pl in run["players"] or []}
        for i in items:
            g = {k: v for k, v in i.items() if k in ("name", "kind", "players", "options", "payoffs", "tree", "note")}
            for pl in g.get("players") or []:
                if pl not in known:
                    raise EditError(f"The game {i['name']} has the player '{pl}', who is not one of the players saved.")
            try:
                gt.work_out(g)
            except gt.GameError as exc:
                raise EditError(f"The game {i['name']}: {exc}") from exc
            g["name"] = _text(g["name"], 200)
            g["kind"] = g.get("kind") or "simultaneous"
            out.append(g)
    elif part == "options":
        _unique(items, "options")
        models = _models(pc, p)
        for i in items:
            model = _text(i.get("model"), 200)
            if model and model.lower() not in models:
                raise EditError(f"The option {i['name']} points to the model '{model}', which is not in the project.")
            out.append({"name": _text(i["name"], 200), "model": model, "description": _text(i.get("description"))})
    elif part == "scores":
        opts, fut = _names(run["options"] or []), _names(run["futures"] or [])
        for i in items:
            if str(i.get("option") or "").lower() not in opts:
                raise EditError(f"A score is for one of the options saved: '{i.get('option')}' is not one.")
            if str(i.get("future") or "").lower() not in fut:
                raise EditError(f"A score is in one of the futures saved: '{i.get('future')}' is not one.")
            try:
                gt.value_of(i.get("value"))
            except gt.GameError as exc:
                raise EditError(f"{i['option']} in {i['future']}: {exc}") from exc
            out.append({"option": _text(i["option"], 200), "future": _text(i["future"], 200), "value": i["value"],
                        "why": _text(i.get("why"), 1000)})
    return out


# ---------------------------------------------------------------- the working
def work(run: dict) -> dict:
    """The working of a study as it stands (eax/game_theory.py); a part that cannot be worked out says why."""
    out: dict[str, Any] = {"games": [], "options": None, "players_answers": [], "worked_at": _now().isoformat()}
    worked = []
    for g in run["games"] or []:
        try:
            w = gt.work_out(g)
        except gt.GameError as exc:
            w = {"error": str(exc)}
        w["name"] = g.get("name")
        worked.append(w)
    out["games"] = worked
    opts = [o["name"] for o in run["options"] or []]
    futs = [f["name"] for f in run["futures"] or []]
    if opts and futs:
        try:
            out["options"] = gt.robustness(opts, futs, run["scores"] or [])
        except gt.GameError as exc:
            out["options"] = {"error": str(exc)}
    if run.get("organisation") and opts:
        out["players_answers"] = gt.players_answers(run["games"] or [], worked, run["organisation"], opts)
    forces = run["forces"] or []
    out["critical"] = [f["name"] for f in sorted(forces, key=lambda f: -(f["impact"] * f["uncertainty"]))[:4]]
    return out


def _missing(run: dict) -> list[str]:
    """What the template still needs before the study can be finished."""
    t = TEMPLATES.get(run["template"]) or TEMPLATES["grid"]
    need = []
    u, f = len(run["uncertainties"] or []), len(run["futures"] or [])
    lo, hi = t["uncertainties"]
    if not lo <= u <= hi:
        need.append(f"{lo if lo == hi else f'{lo} to {hi}'} critical uncertainties (there are {u})")
    lo, hi = t["futures"]
    if not lo <= f <= hi:
        need.append(f"{lo if lo == hi else f'{lo} to {hi}'} futures (there are {f})")
    if run["template"] == "games" and not run["games"]:
        need.append("at least one game")
    if run["template"] != "games" and f and not run["signposts"]:
        need.append("signposts for the futures")
    if run["options"] and run["futures"]:
        need_n = len(run["options"]) * len(run["futures"])
        if len(run["scores"] or []) < need_n:
            need.append(f"a score for every option in every future ({len(run['scores'] or [])} of {need_n})")
    return need


# ---------------------------------------------------------------- changing (preview unless confirm)
def start(pc, project: Any, user, question: str, template: str, copy_latest: bool = False, confirm: bool = False) -> dict:
    """A new version of the project's study, a draft; with copy_latest, starting from the newest done version's parts."""
    p = _project(pc, project, user, "contribute")
    question = _text(question, 1000)
    if not question:
        raise EditError("Say what question the study answers.")
    if template not in TEMPLATES:
        raise EditError(f"A template is one of: {', '.join(TEMPLATES)} (sp_templates lists them).")
    if _draft(pc, p):
        raise EditError("A draft study is open in this project: finish it (sp_finish) or throw it away (sp_discard) first.", 409)
    latest = _latest(pc, p)
    if copy_latest and not latest:
        raise EditError("There is no finished study to start from: start without copy_latest.")
    nxt = (max((r["version"] for r in _runs(pc, p)), default=0)) + 1
    plan = {"will": [f"start version {nxt} of {p['name']}'s scenario planning as a draft: {question}",
                     f"template: {TEMPLATES[template]['name']}"]
            + ([f"start from version {latest['version']}'s forces, futures, signposts, players, games, options and scores"]
               if copy_latest else []), "version": nxt}
    if not confirm:
        return {"preview": plan}
    _insert(pc, {"project_id": p["id"], "version": nxt, "question": question, "template": template,
                 "organisation": latest["organisation"] if copy_latest else "", "created_by": user.username,
                 **{k: (latest[k] if copy_latest else []) or [] for k in PARTS}})
    return {"version": nxt, "status": "draft", "message": f"Version {nxt} is a draft: save its parts with sp_save, one at a time.",
            "steps": STEPS, "link": f"/#/projects/{p['guid']}/planning"}


def save(pc, project: Any, user, part: str, items: Any, confirm: bool = False) -> dict:
    """One part of the draft replaced by `items` (checked); preview unless confirm."""
    p = _project(pc, project, user, "contribute")
    run = _draft(pc, p)
    if not run:
        raise EditError("No draft study is open in this project: start one with sp_start.", 404)
    clean = check(pc, p, run, part, items)
    plan = {"will": [f"save {len(clean)} {part} in version {run['version']} (replacing the {len(run[part] or [])} saved)"],
            part: clean}
    if part == "players":
        org = next((x["name"] for x in clean if x["kind"] == "organisation"), "")
        plan["organisation"] = org
    if part in ("games", "scores"):
        trial = {**run, part: clean}
        w = work(trial)
        plan["working"] = w["games"] if part == "games" else w["options"]
    if not confirm:
        return {"preview": plan}
    _set(pc, run["id"], **{part: clean}, **({"organisation": plan.get("organisation", "")} if part == "players" else {}))
    left = _missing({**run, part: clean})
    return {"saved": part, "count": len(clean), "version": run["version"], "still_needed": left,
            "message": f"{len(clean)} {part} saved in version {run['version']}."}


def work_out(pc, project: Any, user) -> dict:
    """The draft's working as it stands, and what it still needs (reading only)."""
    p = _project(pc, project, user)
    run = _draft(pc, p) or _latest(pc, p)
    if not run:
        raise EditError("This project has no scenario planning study yet: start one with sp_start.", 404)
    return {"version": run["version"], "status": run["status"], "working": work(run), "still_needed": _missing(run)}


def finish(pc, project: Any, user, recommendation: str, recommended: str = "", confirm: bool = False) -> dict:
    """The draft finished: its working kept with it, the recommendation; it becomes the version shown."""
    p = _project(pc, project, user, "contribute")
    run = _draft(pc, p)
    if not run:
        raise EditError("No draft study is open in this project.", 404)
    need = _missing(run)
    if need:
        raise EditError("The study still needs: " + "; ".join(need) + ".")
    recommendation = _text(recommendation, 8000)
    if not recommendation:
        raise EditError("Give the recommendation (plain words).")
    recommended = _text(recommended, 200)
    if recommended and recommended.lower() not in _names(run["options"] or []):
        raise EditError(f"The option recommended, '{recommended}', is not one of the study's options.")
    w = work(run)
    plan = {"will": [f"finish version {run['version']}: it becomes the version shown on the Scenario planning tab and in the "
                     "project report", "keep the working with it as it is now"], "working": w,
            "recommendation": recommendation, "recommended": recommended}
    if not confirm:
        return {"preview": plan}
    _set(pc, run["id"], status="done", results=w, recommendation=recommendation, recommended=recommended)
    return {"version": run["version"], "status": "done", "link": f"/#/projects/{p['guid']}/planning",
            "message": f"Version {run['version']} is finished and shown on the project's Scenario planning tab."}


def discard(pc, project: Any, user, confirm: bool = False) -> dict:
    """The open draft thrown away (a finished version is never removed)."""
    p = _project(pc, project, user, "contribute")
    run = _draft(pc, p)
    if not run:
        raise EditError("No draft study is open in this project.", 404)
    if not confirm:
        return {"preview": {"will": [f"throw away the draft, version {run['version']} ({run['question']})"]}}
    _delete_draft(pc, run["id"])
    return {"message": f"The draft version {run['version']} was thrown away."}


def mark_signposts(pc, project: Any, user, marks: Any, confirm: bool = False) -> dict:
    """At a project review: signposts of the version shown marked seen or not, with a note."""
    p = _project(pc, project, user, "contribute")
    run = _latest(pc, p)
    if not run:
        raise EditError("This project has no finished scenario planning study.", 404)
    refs = {s["ref"]: s for s in run["signposts"] or []}
    marks = _list(marks, "marks")
    clean = []
    for m in marks:
        ref = str(m.get("signpost") or "").upper()
        if ref not in refs:
            raise EditError(f"'{m.get('signpost')}' is not one of the signposts ({', '.join(refs) or 'none'}).")
        if not isinstance(m.get("seen"), bool):
            raise EditError(f"{ref}: seen is true or false.")
        clean.append({"signpost": ref, "seen": m["seen"], "note": _text(m.get("note"), 1000)})
    if not clean:
        raise EditError("Mark at least one signpost.")
    plan = {"will": [f"{c['signpost']} ({refs[c['signpost']]['sign']}): {'seen' if c['seen'] else 'not seen'}"
                     + (f", {c['note']}" if c["note"] else "") for c in clean]}
    if not confirm:
        return {"preview": plan}
    for c in clean:
        _add_mark(pc, run["id"], c["signpost"], c["seen"], c["note"], user.username)
    seen = [c for c in clean if c["seen"]]
    return {"marked": len(clean), "seen": [c["signpost"] for c in seen],
            "message": f"{len(clean)} signpost(s) marked" + (f"; {len(seen)} seen: say what it means for the recommendation."
                                                           if seen else ".")}


# ---------------------------------------------------------------- the project report
def report_section(pc, p: dict) -> dict | None:
    """The newest finished study for the project report: the question, the futures, the options' table, the
    recommendation, and the signposts due."""
    run = _latest(pc, p)
    if not run:
        return None
    res = run["results"] or {}
    return {"version": run["version"], "question": run["question"], "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
            "futures": [{"name": f["name"], "story": f["story"]} for f in run["futures"] or []],
            "players": [x["name"] for x in run["players"] or []],
            "options": (res.get("options") or {}).get("in_words") or [],
            "games": [{"name": g.get("name"), "in_words": g.get("in_words") or [g.get("error", "")]} for g in res.get("games") or []],
            "players_answers": res.get("players_answers") or [],
            "recommendation": run["recommendation"], "recommended": run["recommended"],
            "signposts_due": sum(1 for s in signposts_due(pc, run) if s["due"])}
