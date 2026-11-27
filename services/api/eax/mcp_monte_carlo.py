"""Monte Carlo studies through MCP (Release 14.7; D957 (2), D962): the person's AI drafts the ranges, EA Explorer runs them.

Registered on the same MCP server (eax.mcp_server imports this module). The AI reads the project's documents and
models, drafts each input as three numbers (or a risk's chance and loss) with where it came from, and saves only after
the person's yes: a tool that changes something answers first with a **preview** and a confirm token, and does it when
called again with the same arguments and `confirm=<token>` (D458). The working is EA Explorer's (eax/monte_carlo.py),
never the AI's (D857 (4)); the AI reads the result and explains it. Nothing is deleted through MCP (R4.22): a study
is deleted on the project's Monte Carlo tab.
"""

from __future__ import annotations

from typing import Any

from . import monte_carlo_studies as ms
from .mcp_server import mcp


async def _proj(*args, **kwargs):
    """mcp_scenarios' project wrapper, looked up when a tool runs (importing it at the top makes a cycle)."""
    from .mcp_scenarios import _proj as proj
    return await proj(*args, **kwargs)


GUIDE = """Monte Carlo studies (Release 14.7): ranges instead of single numbers, run thousands of times by EA Explorer.
Always in a project. Read its documents and models first, then work as the person: draft, show, and save only after
their yes. Every figure comes from EA Explorer's engine; explain it in plain words (each result has in_words).

""" + "\n".join(ms.STEPS) + """

Kinds (mc_kinds): roadmap (work packages' durations and what each waits for: how likely a date is met), business_case
(benefit and cost lines: the net value and the chance it is positive), risk (risks as events: the chance the year's
losses pass an amount, before and after controls), scenarios (each option's score in each future: the chance each
option is best).

Shapes of an input (mc_save inputs, the whole list each time):
  roadmap        {name, low, likely, high, shape?, after: [names it waits for], source}
  business_case  {name, side: benefit|cost, low, likely, high, shape?, source}
  risk           {name, chance (0 to 1) or likelihood (1-5), low, likely, high (the loss) or impact (1-5),
                  chance_after or likelihood_after (after controls, optional), source}
  scenarios      {option, future, low, likely, high, shape?, source}
  shape          pert (the default) or triangular
Groups (mc_save groups): [{name, members: [input names], strength: weak|medium|strong}]: inputs that move together.
Settings (mc_save settings): roadmap {target, milestones: [{name, packages, by?}]}; risk {amounts: [..]};
scenarios {weights: {future: weight}}.
Likelihood and Impact levels become numbers by the organisation's risk scale (mc_risk_scale).
Give the link to what you made (/#/projects/<id>/montecarlo/<study>)."""


@mcp.prompt() if hasattr(mcp, "prompt") else (lambda f: f)
def monte_carlo_study(project: str = "", question: str = "") -> str:
    """Run a Monte Carlo study in a project: ranges drafted from its documents and models, run by EA Explorer."""
    return (f"{GUIDE}\n\nProject: {project or '(ask which; list_projects shows them)'}. "
            f"The question: {question or '(ask what the study should answer)'}.\nStart with mc_overview, then mc_kinds.")


@mcp.tool()
async def how_to_run_monte_carlo() -> Any:
    """READ FIRST when asked for a Monte Carlo simulation, roadmap confidence, the chance of a date or a budget, a
    business case as a range, or risk exposure: the steps, the tools and the shapes they take."""
    return {"guide": GUIDE}


@mcp.tool()
async def mc_kinds() -> Any:
    """The kinds of Monte Carlo study (roadmap, business_case, risk, scenarios), each with what it answers."""
    return {"kinds": ms.kinds(), "steps": ms.STEPS}


@mcp.tool()
async def mc_overview(project: str) -> Any:
    """A project's Monte Carlo studies, each with its latest run in words; the organisation's risk scale."""
    return await _proj(lambda pc, who: ms.overview(pc, project, who))


@mcp.tool()
async def mc_study(project: str, study: str) -> Any:
    """One Monte Carlo study in full: its inputs (each with who set it and where it came from), groups, settings,
    its runs, and the latest run's result (whether the inputs changed since)."""
    return await _proj(lambda pc, who: ms.get_study(pc, project, who, study))


@mcp.tool()
async def mc_run_result(project: str, study: str, number: int) -> Any:
    """One run of a study in full: the inputs it used, its seed and its result (percentiles, chances, drivers)."""
    return await _proj(lambda pc, who: ms.get_run(pc, project, who, study, number))


@mcp.tool()
async def mc_risk_scale() -> Any:
    """What Likelihood and Impact 1 to 5 mean in this organisation: a chance in a year, and a loss [low, likely, high]."""
    return await _proj(lambda pc, who: ms.risk_scale(pc))


@mcp.tool()
async def mc_start(project: str, name: str, kind: str, question: str = "", currency: str = "", unit: str = "",
                   confirm: str = "") -> Any:
    """Start a Monte Carlo study in a project: its name, kind (roadmap | business_case | risk | scenarios), the question
    it answers, the currency for amounts, a roadmap's unit (days | weeks | months). Without confirm: a preview and a
    confirm token; after the person's yes call again with the same arguments and confirm=<token>."""
    args = {"project": project, "name": name, "kind": kind, "question": question, "currency": currency, "unit": unit}
    return await _proj(lambda pc, who, ok: ms.create(pc, project, who, name, kind, question, currency, unit, confirm=ok),
                       write=True, tool="mc_start", args=args, confirm=confirm)


@mcp.tool()
async def mc_save(project: str, study: str, inputs: list[dict] | None = None, groups: list[dict] | None = None,
                  settings: dict | None = None, confirm: str = "") -> Any:
    """Save a study's inputs (the whole list), groups and/or settings (shapes in how_to_run_monte_carlo); each input is
    marked as drafted by the AI. Checked first. Without confirm: a preview and a confirm token; after the person's yes
    call again with the same arguments and confirm=<token>."""
    data = {k: v for k, v in (("inputs", inputs), ("groups", groups), ("settings", settings)) if v is not None}
    args = {"project": project, "study": study, **data}
    return await _proj(lambda pc, who, ok: ms.update(pc, project, who, study, data, by="ai", confirm=ok),
                       write=True, tool="mc_save", args=args, confirm=confirm)


@mcp.tool()
async def mc_run(project: str, study: str, runs: int = 0, seed: int = 0, confirm: str = "") -> Any:
    """Run a study (runs: 100 to 100,000, the study's own when 0; seed: the study's own when 0). The preview already
    shows the result; with confirm the run is kept with the inputs and seed it used, so it gives the same answer again."""
    args = {"project": project, "study": study, "runs": runs, "seed": seed}
    return await _proj(lambda pc, who, ok: ms.run(pc, project, who, study, runs or None, seed or None, confirm=ok),
                       write=True, tool="mc_run", args=args, confirm=confirm)

