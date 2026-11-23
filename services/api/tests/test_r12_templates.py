"""Release 12 (D879, D880): the five new project types, the six model templates they start their models from, their
views and their TOGAF references, and a sample of each whose name says its type.

The model templates were loaded on a real PostgreSQL while building (22 Nov 2026): six locked templates, each with the
57 types of ArchiMate 4 (the Release 12 ones among them), every type copied from the root (origin set).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from eax import project_templates as pt
from eax.report_defs import VIEWS
from eax.seed import build
from eax.seed import model_templates as MT
from eax.seed import sample_projects as sp

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "web" / "src"
TEMPLATES = json.loads((ROOT / "eax" / "seed" / "project_templates.json").read_text(encoding="utf-8"))["templates"]
NEW = ["agile", "digital-transformation", "ea-capability", "risk-security", "data-governance"]


def _t(code):
    return next(t for t in TEMPLATES if t["code"] == code)


def test_six_model_templates_ship_locked_and_structure_only():
    assert [c for c, *_ in MT.TEMPLATES] == ["government", "agile", "digital", "ea-capability", "risk-security", "data-governance"]
    assert all(n.endswith("model template") for _c, n, _d in MT.TEMPLATES)
    assert all("Structure only" in d for _c, _n, d in MT.TEMPLATES)
    sql = build.seed_sql(with_template=False, with_insurance=False, with_sample=False, with_principles=False,
                         with_togaf10=False, with_model_templates=True)
    assert sql.count("INSERT INTO core.models") == 6 and sql.count("'template'") == 6
    assert "INSERT INTO core.entities" not in sql              # no starter elements (D858)
    assert "Government Reference Model (TOGAF GRM)" in MT.TEMPLATES[0][2]
    assert "with_model_templates=templates" in (ROOT / "eax" / "seed" / "__main__.py").read_text(encoding="utf-8")


def test_five_new_project_types_each_start_from_their_model_template():
    expect = {"agile": "agile", "digital-transformation": "digital", "ea-capability": "ea-capability",
              "risk-security": "risk-security", "data-governance": "data-governance"}
    for code, tmpl in expect.items():
        t = _t(code)
        spec = pt.clean_spec({k: v for k, v in t.items() if k not in ("code", "name", "icon", "description", "sort")})
        made = [s for s in spec["slots"] if s.get("template")]
        assert made and all(s["template"] == tmpl for s in made), code
        assert all(s["template_model"] == build.gid("model", MT.key(tmpl)) for s in made), code
        assert all("empty" in s["starts"] for s in made), code       # a new model can start from the template
    # the listing gives the wizard the template's model, which it offers as the new model's start
    out = pt._out({"code": "x", "name": "x", "icon": "", "description": "", "spec": {"slots": [{"role": "target", "template": "agile"}]},
                   "builtin": True, "retired": False, "modified_by": "", "modified_at": None})
    assert out["spec"]["slots"][0]["template_name"] == "Agile model template"
    assert "defaultSource={making.slot.template_model || sourceDefault}" in (WEB / "Projects.jsx").read_text(encoding="utf-8")


def test_an_unknown_model_template_is_refused():
    try:
        pt.clean_spec({"slots": [{"role": "target", "template": "nope"}]})
    except pt.EditError as exc:
        assert "Unknown model template" in str(exc)
    else:
        raise AssertionError("an unknown model template was accepted")


def test_their_views_exist_and_the_new_viewpoints_are_used():
    codes = {v["code"] for v in VIEWS}
    used = set()
    for code in NEW:
        assert set(_t(code)["views"]) <= codes, code
        used |= set(_t(code)["views"])
    assert {f"VP-{n}" for n in range(50, 58)} <= used
    assert _t("risk-security")["views"][:2] == ["VP-50", "VP-51"] and "VP-57" in _t("agile")["views"]


def test_each_names_its_togaf_guides_with_a_link():
    numbers = {"agile": ["g210", "g20f"], "ea-capability": ["g184"], "risk-security": ["g152"], "digital-transformation": ["c196"],
               "data-governance": ["g21b"]}
    for code, docs in numbers.items():
        refs = pt.rf.template_links(_t(code)) if hasattr(pt, "rf") else __import__("eax.references", fromlist=["x"]).template_links(_t(code))
        urls = [r["url"] for r in refs]
        assert all(u.startswith("https://") for u in urls) and "https://www.opengroup.org/togaf" in urls, code
        for d in docs:
            assert f"https://www.opengroup.org/library/{d}" in urls, (code, d)
            title = next(r["title"] for r in refs if r["url"].endswith(d))
            assert f"({d.upper()})" in title, title


def test_the_agile_type_has_a_default_sprint_length_and_the_ea_capability_type_its_phases():
    assert _t("agile")["agile"]["sprint_days"] == 14
    assert _t("ea-capability")["phases"] == ["P", "A", "E", "F", "G", "RM"]


def test_a_sample_of_each_new_type_named_for_its_type():
    by_code = {}
    for s in sp.SAMPLES:
        by_code.setdefault(s[0], []).append(s)
    expected = {"agile": "Agile sprints: ", "digital-transformation": "Digital transformation: ",
                "ea-capability": "EA capability setup: ", "risk-security": "Risk and security architecture: ",
                "data-governance": "Data governance: "}
    for code, prefix in expected.items():
        (s,) = by_code[code]
        assert s[1].startswith(prefix) and s[1].endswith("(sample)"), s[1]
        empty = [m for m in s[4] if m[0] == "empty"]
        assert empty and empty[0][1].endswith("model template"), code
        assert empty[0][3]["name"].endswith("(sample)") and re.match(r"^[A-Z][A-Za-z ]+ model: ", empty[0][3]["name"]), empty
    ridge = next(s for s in sp.SAMPLES if "Ridgeview" in s[1])
    assert ridge[1] == "Government services: Ridgeview City Council (sample)" and ridge[0] == "transformation"
    assert ("refer", "Government Reference Model (TOGAF GRM)", "reference", {}) in ridge[4]
    assert any(m[0] == "empty" and m[1] == "Government model template" for m in ridge[4])
