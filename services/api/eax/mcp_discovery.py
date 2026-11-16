"""MCP tools for enterprise discovery (R5.5; owner, 15 Nov 2026, 20:27: "EA explorer will only be source and sink of
information. Let MCP and LLm run this one").

The people's own AI runs discovery: it asks which projects are due, starts a run (the target model is tagged first),
reaches and reads each source with its own tools and access, adds the content with the usual tools (add_entities,
add_relationships, the metamodel draft tools), says where each element was found and what it skipped as NOT FOR AI USE,
and finishes the run (its changes committed as "AI agent on behalf of" the person who set the project up, the model
tagged again). The AI signs in to EA Explorer with its own MCP sign-in. Rules live in eax.discovery_projects.
"""

from __future__ import annotations

from typing import Any

from . import discovery_projects as dp
from . import permissions
from .mcp_server import _run, mcp


def _who():
    return permissions.current.get()


@mcp.tool()
async def discovery_projects() -> Any:
    """The discovery projects you may see: name, target model, sources, schedule, when the next run is due (due,
    overdue or running) and the last run. Set up by a Discovery Admin on the Enterprise discovery page."""
    return await _run(lambda conn: dp.listing(conn, _who())["projects"])


@mcp.tool()
async def discovery_projects_due() -> Any:
    """The discovery projects whose run is due or overdue now: what a scheduled task of your AI client asks, then runs
    each with run_discovery_project (EA Explorer runs nothing itself)."""
    return await _run(lambda conn: {"due": dp.due(conn, _who())})


@mcp.tool()
async def run_discovery_project(project: str, read: str = "", gone: str = "", ai_client: str = "") -> Any:
    """READ FIRST to run discovery. Starts a run of a discovery project (by name or id). read: "new" (only what is new
    or changed since the last run) or "all"; gone: "mark" (mark elements whose source item is gone) or "delete". Without
    them it asks which, with the project's defaults: ask the person, or use the defaults on a scheduled run. The target
    model is tagged first. Returns the run id, the sources (kind, where, what to include, attachments, where the last
    run got to) and the guide to follow. ai_client: your client's name, for the record."""
    return await _run(lambda conn: dp.start_run(conn, _who(), project, read, gone, ai_client), begin=True)


@mcp.tool()
async def discovery_record_found(run: str, items: list[dict]) -> Any:
    """Where each element or relationship you added or changed in this run was found: items [{element (name, display
    ID or guid), kind: "entity" | "relationship", source (its name or id), item (the mail, file, page, ticket or
    commit), place (page, line, slide, moment in a recording), link, may_be_same (an element already there that it may
    be the same as, when unsure), note}] (up to 1000 at a time)."""
    return await _run(lambda conn: dp.record_found(conn, _who(), run, items), begin=True)


@mcp.tool()
async def discovery_report_skipped(run: str, items: list[dict]) -> Any:
    """What you skipped because it is marked NOT FOR AI USE OR AUTOMATED PROCESSING: items [{source, title, place,
    date}]. Only its title, place and date: never read or report what it holds."""
    return await _run(lambda conn: dp.record_skipped(conn, _who(), run, items), begin=True)


@mcp.tool()
async def discovery_finish_run(run: str, positions: dict | None = None, gone: list[dict] | None = None,
                               summary: str = "") -> Any:
    """Finish a run: positions {source name or id: where you got to (a date, a commit, a message id)}, gone [{element,
    source}] (elements whose source item is no longer there: marked or deleted as the run chose), and a short summary
    (what you found, the metamodel changes you made, your doubts). Your changes are committed as "AI agent on behalf
    of" the person who set the project up (or their commit is asked for), the model is tagged again, and the run's
    report comes back: show it to the person."""
    return await _run(lambda conn: dp.finish_run(conn, _who(), run, positions, gone, summary), begin=True)


@mcp.tool()
async def discovery_run_report(run: str) -> Any:
    """A discovery run's report: who ran it and for whom, what it found and where, what it skipped as NOT FOR AI USE,
    what may be the same as an element already there, what was no longer found, and the link comparing its two tags
    (what it changed, the metamodel first)."""
    return await _run(lambda conn: dp.report(conn, _who(), run))


@mcp.tool()
async def discovery_log_decision(run: str, kind: str, title: str, fields: dict | None = None, owner: str = "",
                                 sponsor: str = "", expires_on: str = "", phase: str = "", record_type: str = "",
                                 source: str = "", item: str = "", place: str = "", link: str = "") -> Any:
    """An architecture decision record (kind "ADR") or a dispensation (kind "Dispensation") found in a source during
    this run, logged as a Draft in the organisation's Governance Log with where it was found; the Architecture Board
    accepts or rejects it. fields: the template's fields (see the Governance Log templates: for an ADR context,
    options, decision, rationale, consequences; for a dispensation waived, systems, justification, risks,
    remediation); a dispensation needs its expiry date (expires_on, YYYY-MM-DD) and a sponsor."""
    from .mcp_build import _proj
    from .mcp_server import may_write
    if permissions.current.get() is not None and (why := may_write()):
        return {"error": why}

    def work(pc, who):
        from . import projects as pj
        return dp.log_decision(pj.core(pc), pc, who, run, {"kind": kind, "title": title, "fields": fields or {}, "owner": owner,
                                                           "sponsor": sponsor, "expires_on": expires_on, "phase": phase,
                                                           "record_type": record_type, "source": source, "item": item,
                                                           "place": place, "link": link})
    return await _proj(work, write=True)
