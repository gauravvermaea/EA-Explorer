"""Release 12 (D884): MCP tools for Agile sprints, the project plan, the risk register, data governance, and surveys
and skills. Every tool that changes something previews first and acts only with the confirm token (D458), and calls
the screens' own functions, so the AI meets the same rules as a person."""

from __future__ import annotations

import ast
from pathlib import Path

from eax import mcp_catalogue as cat

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "eax" / "mcp_release12.py").read_text(encoding="utf-8")
FN = {f.name: ast.get_source_segment(SRC, f) for f in ast.parse(SRC).body if isinstance(f, ast.AsyncFunctionDef | ast.FunctionDef)}

READS = {"agile_overview", "project_plan", "risk_register", "data_governance", "survey_starters", "skills_by_togaf_role"}
CHANGES = {"agile_add_to_backlog", "agile_plan_sprint", "agile_review_sprint", "project_plan_change", "risk_log", "survey_start",
           "set_my_togaf_skills"}


def test_the_tools_are_offered_and_listed():
    tools = {t["name"]: t for t in cat.tools() if t["area"] == cat.AREAS["mcp_release12"]}
    assert set(tools) == READS | CHANGES
    assert all(tools[n]["changes"] for n in CHANGES) and not any(tools[n]["changes"] for n in READS)
    assert "mcp_release12," in (ROOT / "eax" / "mcp_server.py").read_text(encoding="utf-8")


def test_every_change_previews_first_and_uses_the_screens_rules():
    for name in CHANGES:
        src = FN[name]
        assert "confirm=confirm" in src and "write=True" in src and '"preview"' in src, name
    assert "ag.plan(pc, project, who, d)" in FN["agile_plan_sprint"]
    assert "rr.log(pc, project, who," in FN["risk_log"]
    assert "ss.start(cc, who, code, d)" in FN["survey_start"]
    assert "sk.clean_togaf(roles, levels)" in FN["set_my_togaf_skills"]
    plan = FN["project_plan_change"]
    for f in ("pm.set_settings", "pm.set_phase_plan", "pm.add_milestone", "pm.add_status", "pm.set_raci"):
        assert f in plan


def test_data_governance_reads_owners_stewards_and_systems_of_record():
    src = FN["data_governance"]
    for a in ("'DataSteward'", "'SystemOfRecord'", "'QualityDimension'", '== "Data quality"', '"no_steward"', '"no_system_of_record"'):
        assert a in src
