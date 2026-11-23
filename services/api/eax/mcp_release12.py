"""The Release 12 work through MCP (D884: "MCP tools for Agile sprints, the risk register, data governance, and surveys
and skills"): read, and change with a preview first (D458). A tool that changes something answers first with a
**preview** and a confirm token, and does it when called again with the same arguments and `confirm=<token>` (by the
same person, within 30 minutes). Every rule is the screens' own (eax/agile.py, eax/pm.py, eax/risk_register.py,
eax/survey_starters.py, eax/skills.py); nothing here decides anything itself. Registered on the same MCP server.
"""

from __future__ import annotations

from typing import Any

from .mcp_server import mcp


async def _proj(*args, **kwargs):
    """mcp_scenarios._proj, looked up when called (as mcp_iterations does, to keep the imports free of cycles)."""
    from .mcp_scenarios import _proj as proj
    return await proj(*args, **kwargs)


def _read(pc, who, project: str) -> dict:
    from . import projects as pj
    p = pj.project_row(pc, project)
    pj._need(pc, p, who, "read")
    return p


# ---------------------------------------------------------------- Agile sprints (R12.2)
@mcp.tool()
async def agile_overview(project: str) -> Any:
    """An Agile project's sprints: the backlog (with what is offered from the requirements, epics and features in its
    models), the open sprint with its goal, phases and accepter, the sprints before it with their reviews (demo,
    outcome, retrospective, planning), the usual sprint length and how the backlog is prioritised."""
    from . import agile as ag
    return await _proj(lambda pc, who: {**ag.overview(pc, project, who), "offered": ag.offered(pc, project, who)})


@mcp.tool()
async def agile_add_to_backlog(project: str, entities: list[str] | None = None, title: str = "", priority: int = 0,
                               confirm: str = "") -> Any:
    """Add to an Agile project's backlog: requirements, epics or features of its models (entities: their ids, as
    agile_overview offers them), or one item by its title. Preview, the person's yes, then confirm=<token>."""
    from . import agile as ag
    d = {"entities": entities} if entities else {"title": title, "priority": priority}
    args = {"project": project, **d}

    def run(pc, who, ok):
        if ok:
            return ag.add_to_backlog(pc, project, who, d)
        _read(pc, who, project)
        return {"preview": {"project": project, "adds": entities or [title],
                            "note": "Requirements must be in the project's models and not in the backlog already."}}
    return await _proj(run, write=True, tool="agile_add_to_backlog", args=args, confirm=confirm)


@mcp.tool()
async def agile_plan_sprint(project: str, goal: str, phases: list[str], accepter: str, items: list[str],
                            starts_on: str = "", ends_on: str = "", zero: bool = False, confirm: str = "") -> Any:
    """Plan the next sprint of an Agile project: its goal (obligatory), the ADM phases it runs, who accepts its
    deliverables, the backlog items it takes (their ids from agile_overview), and its dates (the usual length unless
    given). zero: the first sprint as Sprint zero, the strategic sprint. Preview, the person's yes, then confirm=<token>."""
    from . import agile as ag
    d = {"goal": goal, "phases": phases, "accepter": accepter, "items": items, "zero": zero,
         **({"starts_on": starts_on} if starts_on else {}), **({"ends_on": ends_on} if ends_on else {})}
    args = {"project": project, **d}

    def run(pc, who, ok):
        if ok:
            return ag.plan(pc, project, who, d)
        _read(pc, who, project)
        return {"preview": {"project": project, "sprint": "Sprint zero" if zero else "the next sprint", **d}}
    return await _proj(run, write=True, tool="agile_plan_sprint", args=args, confirm=confirm)


@mcp.tool()
async def agile_review_sprint(project: str, sprint: str, decisions: dict, demo: str = "", retrospective: str = "",
                              note: str = "", confirm: str = "") -> Any:
    """Record an Agile sprint's review: decisions {item id: true (accepted) or false (back to the backlog)} for every
    item of the sprint, the demo (what was shown, to whom), the retrospective, and a note. Preview, the person's yes,
    then confirm=<token>."""
    from . import agile as ag
    args = {"project": project, "sprint": sprint, "decisions": decisions, "demo": demo, "retrospective": retrospective, "note": note}

    def run(pc, who, ok):
        if ok:
            return ag.review(pc, project, who, sprint, decisions, note, demo=demo, retrospective=retrospective)
        _read(pc, who, project)
        return {"preview": {"project": project, "sprint": sprint,
                            "accepted": [k for k, v in decisions.items() if v is True or (isinstance(v, dict) and v.get("accepted"))],
                            "back_to_backlog": [k for k, v in decisions.items() if v is False or (isinstance(v, dict) and not v.get("accepted"))]}}
    return await _proj(run, write=True, tool="agile_review_sprint", args=args, confirm=confirm)


# ---------------------------------------------------------------- the project plan (R12.4)
@mcp.tool()
async def project_plan(project: str) -> Any:
    """A project's plan: how it records RACI and its approval gates, each phase's planned dates (late ones marked, a
    gate's deliverables still waiting for approval), the milestones, the RACI and the status reports."""
    from . import pm
    return await _proj(lambda pc, who: pm.overview(pc, project, who))


@mcp.tool()
async def project_plan_change(project: str, what: str, data: dict, confirm: str = "") -> Any:
    """Change a project's plan. what: settings {raci: none|phase|deliverable|step, gates: [phase], roadmap_from,
    roadmap_to, roadmap_marks}; phase {phase, starts_on, ends_on}; milestone {name, due_on, phase, note}; status {rag:
    green|amber|red, summary, next_steps}; raci {ref (a phase, an item id or a step id), people: {username: [R, A, C,
    I]}}. Preview, the person's yes, then confirm=<token>."""
    from . import pm
    args = {"project": project, "what": what, "data": data}
    do = {"settings": lambda pc, who: pm.set_settings(pc, project, who, data),
          "phase": lambda pc, who: pm.set_phase_plan(pc, project, who, str(data.get("phase") or ""), data),
          "milestone": lambda pc, who: pm.add_milestone(pc, project, who, data),
          "status": lambda pc, who: pm.add_status(pc, project, who, data),
          "raci": lambda pc, who: pm.set_raci(pc, project, who, str(data.get("ref") or ""), data.get("people") or {})}

    def run(pc, who, ok):
        if what not in do:
            return {"error": f"what is one of: {', '.join(do)}."}
        if ok:
            return do[what](pc, who)
        _read(pc, who, project)
        return {"preview": {"project": project, "change": what, **data}}
    return await _proj(run, write=True, tool="project_plan_change", args=args, confirm=confirm)


# ---------------------------------------------------------------- the risk register (R12.5)
@mcp.tool()
async def risk_register(project: str) -> Any:
    """A project's risk register: its Governance log's Risk records with the risks they describe in its models
    (Assessments of kind Risk: likelihood, impact, score, residual risk, treatment, controls, what each bears on), and
    the risks in the models not in the log yet."""
    from . import risk_register as rr
    return await _proj(lambda pc, who: rr.register(pc, project, who))


@mcp.tool()
async def risk_log(project: str, model: str, element: str, confirm: str = "") -> Any:
    """Log a risk of one of the project's models (an Assessment of kind Risk: model and element ids from risk_register)
    in its Governance log, as a draft Risk record that describes it. Preview, the person's yes, then confirm=<token>."""
    from . import risk_register as rr
    args = {"project": project, "model": model, "element": element}

    def run(pc, who, ok):
        if ok:
            return rr.log(pc, project, who, {"model": model, "element": element})
        _read(pc, who, project)
        found = [a for a in rr.register(pc, project, who)["not_logged"] if a["id"] == element]
        if not found:
            return {"error": "That risk is not among those not logged yet (risk_register lists them)."}
        return {"preview": {"project": project, "logs": found[0]["name"], "score": found[0]["score"],
                            "residual": found[0].get("ResidualRisk"), "owner": found[0].get("Owner")}}
    return await _proj(run, write=True, tool="risk_log", args=args, confirm=confirm)


# ---------------------------------------------------------------- data governance (R12.4, views VP-54 to VP-56)
@mcp.tool()
async def data_governance(model: str) -> Any:
    """A model's data governance: each data domain (a Grouping) and the information in it (business and data objects)
    with its owner, data steward, system of record and classification; what has no owner, steward or system of record;
    and the data quality rules (Requirements of kind Data quality) with their dimension and target."""
    from . import projects as pj
    from . import repository as repo

    def run(pc, who):
        cc = pj.core(pc)
        m = repo.get_model(cc, model)
        rows = pj._rows(cc, """
            SELECT e.guid::text AS id, e.name, t.code AS type,
                   max(v.value_text) FILTER (WHERE a.code = 'Owner') AS owner,
                   max(v.value_text) FILTER (WHERE a.code = 'DataSteward') AS steward,
                   max(v.value_text) FILTER (WHERE a.code = 'SystemOfRecord') AS system_of_record,
                   max(v.value_text) FILTER (WHERE a.code = 'DataClassification') AS classification,
                   max(v.value_text) FILTER (WHERE a.code = 'RequirementKind') AS requirement_kind,
                   max(v.value_text) FILTER (WHERE a.code = 'QualityDimension') AS dimension,
                   max(v.value_text) FILTER (WHERE a.code = 'Target') AS target
              FROM core.entities e JOIN core.entity_types t ON t.id = e.entity_type_id
              LEFT JOIN core.attribute_values v ON v.entity_id = e.id AND NOT v.is_deleted
              LEFT JOIN core.attribute_types a ON a.id = v.attribute_type_id
             WHERE e.model_id = :m AND NOT e.is_deleted AND t.code IN ('Grouping', 'BusinessObject', 'DataObject', 'DataEntity', 'Requirement')
             GROUP BY e.guid, e.name, t.code ORDER BY t.code, e.name""", m=m["_id"])
        info = [r for r in rows if r["type"] in ("BusinessObject", "DataObject", "DataEntity")]
        return {"model": m["name"], "domains": [r for r in rows if r["type"] == "Grouping"], "information": info,
                "quality_rules": [r for r in rows if r["type"] == "Requirement" and r["requirement_kind"] == "Data quality"],
                "no_owner": [r["name"] for r in info if not r["owner"]], "no_steward": [r["name"] for r in info if not r["steward"]],
                "no_system_of_record": [r["name"] for r in info if not r["system_of_record"]],
                "views": ["VP-54 Data ownership", "VP-55 Data quality", "VP-56 Data lineage"]}
    return await _proj(run)


# ---------------------------------------------------------------- surveys and skills (R12.6, R12.8)
@mcp.tool()
async def survey_starters() -> Any:
    """The ready-made surveys to start from: EA capability maturity (the ACMM, on the Maturity page), the business
    capability assessment (from a model's capabilities), digital technology readiness and data management."""
    from . import survey_starters as ss
    return {"starters": ss.listing()}


@mcp.tool()
async def survey_start(code: str, model: str = "", under: str = "", title: str = "", confirm: str = "") -> Any:
    """Make a draft survey from a ready-made one (code from survey_starters); for the business capability assessment
    give the model and, if it has more than 40 capabilities, the capability to assess what is under it. The draft is
    then changed and sent like any survey. Preview, the person's yes, then confirm=<token>."""
    from . import projects as pj
    from . import survey_starters as ss
    d = {k: v for k, v in {"model": model, "under": under, "title": title}.items() if v}
    args = {"code": code, **d}

    def run(pc, who, ok):
        cc = pj.core(pc)
        if ok:
            out = ss.start(cc, who, code, d)
            return {**out, "link": f"/#/surveys/{out.get('id')}"}
        if code not in ss.STARTERS:
            return {"error": f"code is one of: {', '.join(ss.STARTERS)}."}
        prev = {"starter": ss.STARTERS[code][0]}
        if code == "business-capability" and model:
            m, caps = ss.capabilities(cc, model, under or None)
            prev.update(model=m["name"], capabilities=[c["name"] for c in caps][:60], count=len(caps), most=ss.MAX_CAPABILITIES)
        return {"preview": prev}
    return await _proj(run, write=True, tool="survey_start", args=args, confirm=confirm)


@mcp.tool()
async def skills_by_togaf_role() -> Any:
    """The TOGAF architect roles, the eight categories of architecture skill and the four levels; and who holds each
    role, with each person's level in each category (from their own profile)."""
    from . import projects as pj
    from . import skills as sk

    def run(pc, who):
        rep = sk.repository(pj.core(pc), who)
        people = {u["username"]: {"name": u["name"], "roles": u["togaf_roles"], "levels": u["togaf_levels"]} for u in rep["users"]
                  if u["togaf_roles"] or u["togaf_levels"]}
        return {"togaf": rep["togaf"], "by_role": rep["by_role"], "people": people}
    return await _proj(run)


@mcp.tool()
async def set_my_togaf_skills(roles: list[str], levels: dict, confirm: str = "") -> Any:
    """Set the signed-in person's own TOGAF roles and their level (1 Background to 4 Expert) in each category of
    architecture skill (keys from skills_by_togaf_role); their free skill tags stay as they are. Preview, the person's
    yes, then confirm=<token>."""
    from . import projects as pj
    from . import skills as sk
    args = {"roles": roles, "levels": levels}

    def run(pc, who, ok):
        cc = pj.core(pc)
        r, lv = sk.clean_togaf(roles, levels)
        if ok:
            return sk.set_mine(cc, who, sk.mine(cc, who)["skills"], r, lv)
        return {"preview": {"person": who.username, "roles": r, "levels": lv}}
    return await _proj(run, write=True, tool="set_my_togaf_skills", args=args, confirm=confirm)
