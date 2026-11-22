"""A project presentation deck, made with the person's own AI through MCP (R5.7-P1, D731; owner, 16 Nov 2026, 09:57,
agreed 16:16 to 16:18 and 17 Nov 13:52). EA Explorer is the source; the AI in the person's own client talks the deck
through with them and builds it there, in the client's own look. Nothing is saved back.

  sources   what a deck about a project can draw on, each with where it came from (so a slide can say its source):
            the project (purpose, status, the ADM phase and cycle, completion, goals), its phases with the steps done
            and the deliverables and artifacts with their documents (titles, states and versions), its models and
            views, the drawn views (as pictures through view_picture), decisions, dispensations, risks and issues,
            requirements, key questions, sign-offs, stakeholders, canvases and customer journeys
  outline   a suggested outline from where the project is (what is done, what is open), for the AI and the person to
            change

Only what the person may read (their own roles; the project's access is checked first). A document marked NOT FOR AI
USE OR AUTOMATED PROCESSING is given by its title only, and its content is never to be read or used.
"""

from __future__ import annotations

from typing import Any

from . import projects as pj

NOT_FOR_AI = "NOT FOR AI USE OR AUTOMATED PROCESSING"
GUIDE = ("Build the deck in your own client, in its own look; EA Explorer keeps nothing of it. Say each slide's source "
         "(the 'source' of what it uses). Ask view_picture for a view or drawn view as png (or svg), or as data to draw it "
         "yourself. Never read or use the content of anything marked not_for_ai: use its title only. Talk the outline "
         "through with the person before building.")


def _src(kind: str, ref: str, where: str) -> dict:
    return {"kind": kind, "id": ref, "where": where}


def _marked(*texts: Any) -> bool:
    return any(NOT_FOR_AI.lower() in str(t or "").lower() for t in texts)


def sources(conn, project: Any, user, parts: list[str] | None = None) -> dict:
    """Everything a deck about the project may draw on, as the person may read it, with sources."""
    d = pj.detail(conn, project, user)                         # refuses who may not read the project
    name = d["name"]
    want = set(parts or []) or {"project", "phases", "models", "governance", "requirements", "questions", "signoffs",
                                "stakeholders", "canvases", "journeys", "scenario_planning"}
    out: dict[str, Any] = {"guide": GUIDE, "not_for_ai": NOT_FOR_AI}
    it = d.get("iteration") or {}
    if "project" in want:
        out["project"] = {"name": name, "id": d.get("id") or d.get("guid"), "purpose": d.get("purpose") or "",
                          "description": d.get("description") or "", "status": d.get("status"),
                          "template": (d.get("template") or {}).get("name"),
                          "phase_now": next((ph["name"] for ph in d.get("phases") or [] if ph["code"] not in (d.get("phases_done") or [])
                                             and ph["code"] in (it.get("phases") or [ph["code"]])), None),
                          "cycle": d.get("cycle"), "iteration": it.get("label") or it.get("name"), "completion": d.get("completion"),
                          "goals": d.get("goals") or [], "source": _src("project", str(d.get("id") or ""), f"{name} › Home")}
    if "phases" in want:
        docs_by_item: dict[str, list] = {}
        skipped = []
        for doc in d.get("documents") or []:
            title = doc.get("title") or doc.get("file_name") or ""
            marked = _marked(title, doc.get("description"), " ".join(doc.get("tags") or []))
            row = {"title": title, "file": doc.get("file_name"), "state": doc.get("state"), "version": doc.get("versions"),
                   "kind": doc.get("kind"), "not_for_ai": marked, "source": _src("document", doc["id"], f"{name} › {doc.get('folder') or 'Documents'}")}
            if marked:
                skipped.append(title)
            docs_by_item.setdefault(doc.get("item_id") or "", []).append(row)
        phases = []
        for ph in d.get("phases") or []:
            steps = [{"name": s["name"], "done": bool(s.get("done_at")), "done_at": s.get("done_at"), "done_by": s.get("done_by")}
                     for s in d.get("steps") or [] if s.get("phase") == ph["code"] and not s.get("removed")]
            items = [{"name": i["name"], "kind": i.get("kind"), "type": i.get("type"), "documents": docs_by_item.get(i["id"], []),
                      "source": _src("item", i["id"], f"{name} › Phases › {ph['name']}")}
                     for i in d.get("items") or [] if i.get("phase") == ph["code"]]
            if steps or items:
                phases.append({"code": ph["code"], "name": ph["name"], "done": ph["code"] in (d.get("phases_done") or []),
                               "steps": steps, "items": items})
        out["phases"] = phases
        out["project_files"] = docs_by_item.get("", [])
        out["titles_only"] = skipped                     # marked NOT FOR AI: their titles only
    if "models" in want:
        out["models"] = [{"id": m.get("id"), "name": m.get("name"), "role": m.get("role"), "how": m.get("how"),
                          "source": _src("model", str(m.get("id")), f"{name} › Models")} for m in d.get("models") or []]
        out["views"] = [{**v, "source": _src("view", v.get("code") or "", f"{name} › Views")} for v in d.get("views") or []]
        out["drawn_views"] = _drawn_views(out["models"])
    if "governance" in want:
        from . import governance as gv
        recs = gv.listing(conn, d.get("id") or project, user)["records"]
        pick = lambda kinds: [{"ref": r["ref"], "title": r["title"], "status": r["status"], "owner": r["owner"], "phase": r["phase"],  # noqa: E731
                               "raised_on": r["raised_on"], "expires_on": r["expires_on"],
                               "source": _src("governance record", r["id"], f"{name} › Governance log › {r['ref'] or r['kind']}")}
                              for r in recs if r["kind"] in kinds]
        out["decisions"] = pick({"Decision", "Architecture Decision Record"})
        out["dispensations"] = pick({"Dispensation"})
        out["risks"] = pick({"Risk"})
        out["issues"] = pick({"Issue"})
        out["compliance"] = pick({"Compliance assessment"})
    if "requirements" in want:
        out["requirements"] = _requirements(conn, d)
    if "questions" in want:
        out["key_questions"] = [{"id": q.get("id"), "question": q.get("question") or q.get("text"), "status": q.get("status"),
                                 "answer": q.get("answer"), "source": _src("key question", str(q.get("id")), f"{name} › Key questions")}
                                for q in d.get("key_questions") or []]
    if "signoffs" in want:
        out["signoffs"] = [{**{k: s.get(k) for k in ("file_name", "item", "version", "state", "phase", "raised_by", "raised_at", "closed_at")},
                            "source": _src("sign-off", str(s.get("id") or ""), f"{name} › Sign-off")} for s in d.get("signoffs") or []]
    if "stakeholders" in want:
        out["stakeholders"] = [{k: s.get(k) for k in ("name", "role", "organisation", "interest", "influence", "concerns")} | {
            "source": _src("stakeholder", str(s.get("id") or ""), f"{name} › Stakeholders")} for s in d.get("stakeholders") or []]
    if "canvases" in want:
        from . import canvases as cv
        out["canvases"] = [{**{k: c[k] for k in ("id", "name", "kind", "status", "items")},
                            "source": _src("canvas", c["id"], f"{name} › Business model canvas")}
                           for c in cv.listing(conn, d.get("id") or project, user)["canvases"]]
    if "journeys" in want:
        from . import journeys as jy
        out["journeys"] = [{**{k: j[k] for k in ("id", "name", "kind", "status", "stages", "steps", "emotion")},
                            "source": _src("customer journey", j["id"], f"{name} › Customer journeys")}
                           for j in jy.listing(conn, d.get("id") or project, user)["journeys"]]
    if "scenario_planning" in want and d.get("scenario_planning"):   # the newest finished study (Release 10)
        from . import scenario_planning as spl
        sec = spl.report_section(conn, pj.project_row(conn, d.get("id") or project))
        if sec:
            out["scenario_planning"] = {**sec, "source": _src("scenario planning", f"v{sec['version']}", f"{name} › Scenario planning")}
    return out


def _drawn_views(models: list[dict]) -> list[dict]:
    """The models' drawn views (names only; view_picture draws them); nothing when the drawn views' service is away."""
    from . import views_client as vc
    out = []
    for m in models:
        try:
            got = vc.list_views(m["id"])
        except Exception:  # noqa: BLE001 - the drawn views' service away: the deck goes on without them
            continue
        for v in (got.get("views") if isinstance(got, dict) else got) or []:
            out.append({"model": m["name"], "model_id": m["id"], "view": v.get("name"), "id": v.get("id"),
                        "source": _src("drawn view", str(v.get("id")), f"{m['name']} › Drawn views › {v.get('name')}")})
    return out


def _requirements(conn, d: dict) -> list[dict]:
    """The Requirement and Constraint elements of the project's home model tagged with the project, else the first 50."""
    home = pj.project_row(conn, d["id"]).get("home_model")
    if not home:
        return []
    tag = f"project:{d.get('id')}"
    rows = pj._rows(pj.core(conn), """SELECT e.guid::text AS id, e.display_id, e.name, e.description, t.name AS type,
                                             (:t = ANY (e.tags)) AS tagged
                                        FROM core.entities e JOIN core.entity_types t ON t.id = e.entity_type_id
                                        JOIN core.models m ON m.id = e.model_id
                                       WHERE m.guid = CAST(:m AS uuid) AND NOT e.is_deleted AND t.code IN ('Requirement', 'Constraint')
                                       ORDER BY (:t = ANY (e.tags)) DESC, e.display_id LIMIT 50""", m=str(home), t=tag)
    return [{**r, "source": _src("element", r["id"], f"Model › {r['type']} {r['display_id']}")} for r in rows]


def outline(conn, project: Any, user, audience: str = "", slides: int = 10) -> dict:
    """A suggested outline from where the project is: for the AI and the person to change, never final."""
    s = sources(conn, project, user)
    p = s["project"]
    done = [ph for ph in s["phases"] if ph["done"]]
    open_ = [ph for ph in s["phases"] if not ph["done"]]
    open_q = [q for q in s["key_questions"] if (q.get("status") or "").lower() not in ("accepted", "answered", "closed")]
    risks = [r for r in s["risks"] + s["issues"] if (r.get("status") or "") in ("Open", "In progress")]
    waiting = [x for x in s["signoffs"] if (x.get("state") or "") == "open"]
    plan = [
        {"title": p["name"], "purpose": "Title: the project, who it is for, the date", "use": ["project"]},
        {"title": "Why this project", "purpose": "The purpose and goals, with their outcomes", "use": ["project.goals"]},
        {"title": "Where we are", "purpose": f"ADM phase now: {p.get('phase_now') or 'not set'}; completion and the phases done",
         "use": ["project.completion", "phases"]},
    ]
    if done:
        plan.append({"title": "What is done", "purpose": "Deliverables agreed in " + ", ".join(ph["name"] for ph in done[:4]),
                     "use": ["phases[].items (done phases)"]})
    if s["drawn_views"] or s["views"]:
        plan.append({"title": "The architecture", "purpose": "Two or three views as pictures (view_picture), each with one message",
                     "use": ["drawn_views", "views"]})
    if s["journeys"] or s["canvases"]:
        plan.append({"title": "The customer and the business", "purpose": "A customer journey (today and target) or the business model canvas",
                     "use": ["journeys", "canvases"]})
    if s["decisions"]:
        plan.append({"title": "Decisions made", "purpose": f"{len(s['decisions'])} decisions; the ones that matter most",
                     "use": ["decisions"]})
    if s["requirements"]:
        plan.append({"title": "What it must do", "purpose": "The main requirements and constraints", "use": ["requirements"]})
    if risks:
        plan.append({"title": "Risks and issues", "purpose": f"{len(risks)} open: owners and what is being done", "use": ["risks", "issues"]})
    if open_q:
        plan.append({"title": "Open questions", "purpose": f"{len(open_q)} key questions still open", "use": ["key_questions"]})
    if waiting:
        plan.append({"title": "Waiting for sign-off", "purpose": f"{len(waiting)} documents waiting", "use": ["signoffs"]})
    plan.append({"title": "Next steps", "purpose": "What comes next: " + (", ".join(ph["name"] for ph in open_[:3]) or "the next phase"),
                 "use": ["phases (open)", "key_questions", "risks"]})
    n = max(3, min(int(slides or 10), 40))
    if len(plan) > n:
        plan = plan[:n - 1] + [plan[-1]]
    return {"project": p["name"], "audience": audience or "not said: ask the person", "slides": plan,
            "note": "A suggestion only: change it with the person. Get each slide's content from deck_sources and the pictures "
                    "from view_picture; say the sources.", "guide": GUIDE}
