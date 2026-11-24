"""The scenario planning wizard through MCP (Release 10; D788, D818, D857): the guided prompt and its tools.

Registered on the same MCP server (eax.mcp_server imports this module). The person starts it in words ("run the
scenario planning wizard for project X"); the AI asks, does the heavy lifting from the project's documents and models,
suggests, and saves each part only after the person's yes: a tool that changes something answers first with a
**preview** and a confirm token, and does it when called again with the same arguments and `confirm=<token>` (by the
same person, within 30 minutes; D458). The working (games, robustness, regret) is EA Explorer's code, never guessed.
"""

from __future__ import annotations

from typing import Any

from . import scenario_planning as sp
from .mcp_server import mcp


async def _proj(*args, **kwargs):
    """mcp_scenarios' project wrapper, looked up when a tool runs: importing it at the top made a cycle when
    mcp_scenarios was imported first (mcp_scenarios -> mcp_server -> this module -> mcp_scenarios)."""
    from .mcp_scenarios import _proj as proj
    return await proj(*args, **kwargs)


GUIDE = """The scenario planning wizard (Release 10). Always in a project: read its documents and models first
(list_projects, project_overview, the models' reports), then work as the person, one step at a time, and ask before
saving anything. Suggest, but the person decides.

""" + "\n".join(sp.STEPS) + """

Tools: sp_templates (the templates), sp_overview(project) (every version, the one shown, the draft), sp_start(project,
question, template, copy_latest?) to begin a new dated version, sp_save(project, part, items) for each part (forces,
uncertainties, futures, signposts, players, games, options, scores; each replaces that part of the draft), sp_work_out
(the working as it stands and what is still needed), sp_finish(project, recommendation, recommended) and sp_discard.
At a project review: sp_overview shows the signposts due; sp_mark_signposts records each as seen or not.

Shapes:
  forces        [{name, kind (economic|technology|regulation|social|market|environment|other), impact 1-5, uncertainty 1-5, note}]
  uncertainties [{name, low, high, force?}]
  futures       [{name, story, true: [..], when, positions: {uncertainty: "low"|"high"|words}, model?}]
  signposts     [{future, sign, watch, level}]
  players       [{name, kind (organisation|competitor|regulator|supplier|partner|business unit|customer|other), stakeholder?, goals}]
  games         moves at once: {name, kind: "simultaneous", players: [..], options: {player: [..]},
                                payoffs: [{options: {player: option}, values: {player: value}}]}  (every outcome)
                moves in turn: {name, kind: "sequential", players: [..], tree: {player, choices: [{option, then: node}]}}
                                down to ends {values: {player: value}}
  options       [{name, model?, description}]   (make_scenario makes a scenario model for an option)
  scores        [{option, future, value, why}]  (every option in every future)
  a value       a number; {"money": n, "currency"?}; or {"words": "much better", "score": 2} (the score the person agreed)

Explain the working in plain words (each result has in_words). Give links to what you made (/#/projects/<id>/planning)."""


@mcp.prompt() if hasattr(mcp, "prompt") else (lambda f: f)
def scenario_planning_wizard(project: str = "", question: str = "") -> str:
    """Run the scenario planning wizard for a project: futures, signposts, players and games, options tested across them."""
    return (f"{GUIDE}\n\nProject: {project or '(ask which; list_projects shows them)'}. "
            f"The question: {question or '(ask what the study should decide)'}.\nStart with sp_overview, then sp_templates.")


@mcp.tool()
async def how_to_run_scenario_planning() -> Any:
    """READ FIRST when asked to run scenario planning, futures, signposts or game theory in a project: the steps, the
    tools and the shapes they take."""
    return {"guide": GUIDE}


@mcp.tool()
async def sp_templates() -> Any:
    """The scenario planning templates the person chooses from (the grid of four futures, three to five futures, one
    uncertainty low to high, players and games only), each with what it is for."""
    return {"templates": sp.templates(), "steps": sp.STEPS}


@mcp.tool()
async def sp_overview(project: str) -> Any:
    """A project's scenario planning: every dated version (newest first), the newest finished one in full with its
    working (games, the most robust option, least regret) and its signposts (those due at this review marked), and the
    draft being worked on, if any."""
    return await _proj(lambda pc, who: sp.overview(pc, project, who))


@mcp.tool()
async def sp_version(project: str, version: int) -> Any:
    """One version of a project's scenario planning in full (to compare with another)."""
    return await _proj(lambda pc, who: sp.get_run(pc, project, who, version))


@mcp.tool()
async def sp_work_out(project: str) -> Any:
    """The working of the draft (or the newest finished version) as it stands: every game worked out (best replies,
    dominant options, stable outcomes, mixed strategies, or worked back from the end), the options across the futures
    (best in each, most robust, least regret, beaten everywhere, wins in one only), and what is still needed to finish."""
    return await _proj(lambda pc, who: sp.work_out(pc, project, who))


@mcp.tool()
async def sp_start(project: str, question: str, template: str = "grid", copy_latest: bool = False, confirm: str = "") -> Any:
    """Start a new dated version of a project's scenario planning, as a draft: the question it answers and the template
    (grid | range | single | games). copy_latest starts from the newest finished version's parts (a re-run). Without
    confirm: a preview and a confirm token; after the person's yes call again with the same arguments and confirm=<token>."""
    args = {"project": project, "question": question, "template": template, "copy_latest": copy_latest}
    return await _proj(lambda pc, who, ok: sp.start(pc, project, who, question, template, copy_latest, confirm=ok),
                       write=True, tool="sp_start", args=args, confirm=confirm)


@mcp.tool()
async def sp_save(project: str, part: str, items: list[dict], confirm: str = "") -> Any:
    """Save one part of the draft (it replaces what that part holds): forces, uncertainties, futures, signposts,
    players, games, options or scores (shapes in how_to_run_scenario_planning). Checked first: a game is worked out and
    must hold together. Without confirm: a preview (with the working for games and scores) and a confirm token; after
    the person's yes call again with the same arguments and confirm=<token>."""
    args = {"project": project, "part": part, "items": items}
    return await _proj(lambda pc, who, ok: sp.save(pc, project, who, part, items, confirm=ok),
                       write=True, tool="sp_save", args=args, confirm=confirm)


@mcp.tool()
async def sp_finish(project: str, recommendation: str, recommended: str = "", confirm: str = "") -> Any:
    """Finish the draft: its working is kept with it and it becomes the version shown on the project's Scenario planning
    tab and in the project report. recommendation in plain words; recommended, the option chosen. Refused while the
    template still needs something (sp_work_out says what). Preview, the person's yes, then confirm=<token>."""
    args = {"project": project, "recommendation": recommendation, "recommended": recommended}
    return await _proj(lambda pc, who, ok: sp.finish(pc, project, who, recommendation, recommended, confirm=ok),
                       write=True, tool="sp_finish", args=args, confirm=confirm)


@mcp.tool()
async def sp_discard(project: str, confirm: str = "") -> Any:
    """Throw away the open draft (a finished version is never removed). Preview, the person's yes, then confirm=<token>."""
    args = {"project": project}
    return await _proj(lambda pc, who, ok: sp.discard(pc, project, who, confirm=ok),
                       write=True, tool="sp_discard", args=args, confirm=confirm)


@mcp.tool()
async def sp_mark_signposts(project: str, marks: list[dict], confirm: str = "") -> Any:
    """At a project review: mark signposts of the version shown as seen or not: marks [{signpost: "SP-1", seen: true,
    note}]. A signpost not marked for 90 days is asked about again. Preview, the person's yes, then confirm=<token>."""
    args = {"project": project, "marks": marks}
    return await _proj(lambda pc, who, ok: sp.mark_signposts(pc, project, who, marks, confirm=ok),
                       write=True, tool="sp_mark_signposts", args=args, confirm=confirm)
