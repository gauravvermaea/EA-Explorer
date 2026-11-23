"""Release 12: the ready-made surveys (R12.6, D879, D884), TOGAF roles and skill levels beside each person's skills
(R12.8) and the references to the TOGAF guides (R12.9).

Run on a real PostgreSQL while building (23 Nov 2026): a model's three capabilities found, two under one of them; a
business capability assessment of those two made as a draft (two sections), the readiness and data management surveys
made as drafts, the ACMM sent to its own page, a capability survey with no model refused, an unknown one refused; a
person's skills saved, then their TOGAF roles and levels, then their skills alone (the roles kept); an unknown role, an
unknown category and a level 5 refused."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from eax import guides as G
from eax import skills as sk
from eax import survey_starters as ss
from eax import surveys as sv
from eax.metamodel_edit import EditError

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "web" / "src"


# ---------------------------------------------------------------- surveys
def test_the_four_surveys():
    assert list(ss.STARTERS) == ["acmm", "business-capability", "technology-readiness", "data-management"]
    assert ss.STARTERS["acmm"][2] == "maturity" and ss.STARTERS["business-capability"][2] == "model"
    assert {s["code"] for s in ss.listing()} == set(ss.STARTERS)


def test_each_ready_made_survey_is_a_valid_survey():
    r = sv.clean_spec(ss.readiness_spec())
    assert [s["title"] for s in r["sections"]][:3] == ["Foundational factors", "Impact factors", "Sustaining factors"]
    assert sum(len(f) for _g, _w, f in ss.READINESS) == 15                     # the guide's fifteen factors (G212)
    d = sv.clean_spec(ss.data_spec())
    assert len(ss.DATA_AREAS) == 10 and len(d["sections"][0]["questions"]) == 10
    caps = [{"name": f"Capability {i}", "description": ""} for i in range(ss.MAX_CAPABILITIES)]
    c = sv.clean_spec(ss.capability_spec(caps))                                 # 40 capabilities fit the survey's limits
    assert len(c["sections"]) == ss.MAX_CAPABILITIES == sv.MAX_SECTIONS
    assert sum(len(s["questions"]) for s in c["sections"]) <= sv.MAX_QUESTIONS
    q = [x["text"] for x in c["sections"][0]["questions"]]
    assert q[:4] == ["How mature is it today?", "How mature does it need to be?", "How well does it perform today?",
                     "How much does it matter to the strategy?"]


def test_starting_rules():
    with pytest.raises(EditError, match="from the Maturity page"):
        ss.start(None, None, "acmm", {})
    with pytest.raises(EditError, match="Choose the model"):
        ss.start(None, None, "business-capability", {})
    with pytest.raises(EditError, match="No such survey to start from"):
        ss.start(None, None, "nope", {})
    src = inspect.getsource(ss.start)
    assert "Choose a capability to assess what is under it." in src and "sv.create(conn, user," in src   # a draft, as any survey
    assert "rt.code IN ('Composition', 'Aggregation')" in inspect.getsource(ss.capabilities)


def test_the_survey_routes_and_screen():
    api = (ROOT / "eax" / "api" / "surveys.py").read_text(encoding="utf-8")
    for r in ('"/surveys/starters")', '"/surveys/starters/<string:code>")', '"/surveys/starters/business-capability/capabilities")'):
        assert r in api
    ui = (WEB / "Surveys.jsx").read_text(encoding="utf-8")
    assert "Start from a ready-made survey" in ui and "function Under(" in ui and "Start a draft" in ui


# ---------------------------------------------------------------- TOGAF roles and skill levels
def test_roles_categories_and_levels():
    assert sk.TOGAF_ROLES[:2] == ["Chief Architect", "Enterprise Architect"] and "Solution Architect" in sk.TOGAF_ROLES
    assert [n for _k, n, _c in sk.CATEGORIES] == ["Application", "Architecture", "Business", "Change", "Data", "Generic", "Legal",
                                                    "Technology"]
    assert [a for a, _b in sk.LEVELS.values()] == ["Background", "Aware", "Knowledgeable", "Expert"]
    t = sk.togaf()
    assert len(t["roles"]) == 7 and len(t["categories"]) == 8 and len(t["levels"]) == 4


def test_togaf_choices_are_checked():
    roles, levels = sk.clean_togaf(["Data Architect", "Enterprise Architect"], {"data": "3", "architecture": 4, "legal": ""})
    assert roles == ["Enterprise Architect", "Data Architect"] and levels == {"data": 3, "architecture": 4}   # the list's order
    with pytest.raises(EditError, match="No TOGAF role Wizard"):
        sk.clean_togaf(["Wizard"], {})
    with pytest.raises(EditError, match="No skill category cooking"):
        sk.clean_togaf([], {"cooking": 2})
    with pytest.raises(EditError, match="1 Background, 2 Aware, 3 Knowledgeable or 4 Expert"):
        sk.clean_togaf([], {"data": 5})


def test_skills_kept_as_they_were_unless_the_togaf_part_is_given():
    src = inspect.getsource(sk.set_mine)
    assert "if togaf_roles is not None or togaf_levels is not None:" in src
    sql = (ROOT / "migrations" / "sql" / "0119_r12_project_management.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE personal.user_skills ADD COLUMN IF NOT EXISTS togaf_roles text[] NOT NULL DEFAULT '{}'" in sql
    assert "ALTER TABLE personal.user_skills ADD COLUMN IF NOT EXISTS togaf_levels jsonb NOT NULL DEFAULT '{}'" in sql
    api = (ROOT / "eax" / "api" / "projects.py").read_text(encoding="utf-8")
    assert '(data or {}).get("togaf_roles")' in api
    rep = inspect.getsource(sk.repository)
    assert '"by_role"' in rep and '"by_category"' in rep
    ui = (WEB / "Skills.jsx").read_text(encoding="utf-8")
    assert "function TogafSkills(" in ui and "function TogafRepository(" in ui and "By TOGAF role" in ui


# ---------------------------------------------------------------- the guides
def test_the_guides_referenced_not_copied():
    codes = [g[0] for g in G.GUIDES]
    assert len(codes) == len(set(codes))
    for c in ("G188", "G176", "G248", "G210", "G212", "G203", "G198", "G249", "G152", "G21H", "G21D", "G211"):
        assert c in codes
    assert "G21I" not in codes                                     # microservices dropped (D879)
    assert all(g["url"] == f"https://www.opengroup.org/library/{g['code'].lower()}" for g in G.listing())
    api = (ROOT / "eax" / "api" / "projects.py").read_text(encoding="utf-8")
    assert '"/reference-library/guides")' in api
    ui = (WEB / "ReferenceLibrary.jsx").read_text(encoding="utf-8")
    assert "The TOGAF guides EA Explorer follows" in ui and "<Guides />" in ui
    help_ = json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "button:Start a draft" in help_ and "tab:By TOGAF role" in help_
