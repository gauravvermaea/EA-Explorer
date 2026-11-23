"""The project library (phase 13, D258): what an architecture project chooses from in the wizard.

Loaded on every start by the core seed from project_library.json (built from the reviewed master template repository
workbook by tools/build_project_library.py): the purposes, the ADM phases, the steps, the deliverables and artifacts
(each with every source that names it), the master folders, and the template libraries EA Explorer ships (its own,
with a file for every item, and TOGAF 10 by name only, D264). Only what is missing is added, so a Super Admin's changes
to the library are kept. On a laptop with the sample, a sample principles library is added too
(sample_principles.json: the fictional Meridian Assurance Group's architecture and security principles).

The TOGAF template files are not here: only their names. A Super Admin loads the licensed files once (Administration
> Project library); they are stored in Mayan exactly as uploaded.
"""

from __future__ import annotations

import json
from pathlib import Path

from .build import lit

HERE = Path(__file__).resolve().parent


def data() -> dict:
    """The deliverables library's data."""
    return json.loads((HERE / "project_library.json").read_text(encoding="utf-8"))


EA_EXPLORER = "EA Explorer"
TOGAF = "TOGAF 10"


def ea_explorer_templates() -> list[dict]:
    """EA Explorer's own templates (built by tools/build_ea_explorer_templates.py; the files are in
    library/templates/ea-explorer, mounted read-only into the API)."""
    f = HERE / "ea_explorer_templates.json"
    return json.loads(f.read_text(encoding="utf-8"))["templates"] if f.exists() else []


def _lib_rows(library: str, cols: list[str], rows: list[list]) -> str:
    """A library's template rows (only the missing ones)."""
    return (f"INSERT INTO proj.lib_templates (library_id, {', '.join(cols)})\n"
            f"SELECT l.id, v.* FROM proj.template_libraries l, (VALUES\n{_values(rows)}\n) AS v ({', '.join(cols)})\n"
            f"WHERE l.name = {lit(library)}\nON CONFLICT (library_id, path) DO NOTHING;\n")


def _values(rows: list[list]) -> str:
    return ",\n".join("(" + ", ".join(lit(v) for v in r) + ")" for r in rows)


def _ins(table: str, cols: list[str], rows: list[list], conflict: str) -> str:
    if not rows:
        return ""
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n{_values(rows)}\nON CONFLICT {conflict} DO NOTHING;\n"


CF_ITEMS: dict[str, str] = json.loads((HERE / "content_framework_map.json").read_text(encoding="utf-8"))["document_types"]


# ---------------------------------------------------------------- Release 12: the base improvements (R12.4, D879, D889)
# Steps and document types added to the library for every project, new and existing (D884: existing projects are
# brought up to date at start, see project_upgrade_sql). The wording is EA Explorer's own; the guides are named.
R12_STEPS = [
    ("A", "Plan the architecture project: its phases, milestones, who is responsible (RACI) and how status is reported",
     "TOGAF Series Guide: Project Management and the ADM (G188)"),
    ("RM", "Use business scenarios to find and test requirements",
     "TOGAF Series Guide: Business Scenarios (G176)"),
    ("E", "Choose the building blocks each work package brings in, reusing those that exist",
     "TOGAF 10: Building blocks; TOGAF Series Guide: Business Architecture building blocks (G248)"),
    ("F", "Confirm the building blocks each project of the migration plan delivers",
     "TOGAF 10: Building blocks"),
]
# (id, phase, name, kind, type, work folder, approved folder, live view)
R12_ITEMS = [
    ("G172", "RM", "Business Scenario Register", "Artifact", "Catalog",
     "09_ADM_Phase_Workspaces/RM_Requirements/Artifacts/172_Business_Scenario_Register", "07_Architecture_Requirements_Repository", "VP-49"),
    ("G173", "E", "Building Block Selection", "Artifact", "Catalog",
     "09_ADM_Phase_Workspaces/E_Opportunities/Artifacts/173_Building_Block_Selection", "08_Solutions_Landscape", "VP-58"),
    ("G174", "F", "Building Blocks by Project", "Artifact", "Catalog",
     "09_ADM_Phase_Workspaces/F_Migration/Artifacts/174_Building_Blocks_by_Project", "03_Architecture_Landscape/01_Strategic_Architecture",
     "VP-58"),
]
# the maps and catalogues that are always live (D879, D889): shown from the project's primary working model by their view,
# beside any file the project keeps for them
LIVE_VIEWS = {"G047": "VP-01", "G045": "VP-47", "G036": "VP-19", "G020": "VP-49", "G113": "VP-58", "G120": "VP-58",
              **{i[0]: i[7] for i in R12_ITEMS}}


def r12_library_sql() -> str:
    """The Release 12 steps and document types, each added once (after the phase's last step), and the live views set
    where a library item has none yet (a Super Admin's choice is kept)."""
    out = []
    for phase, name, source in R12_STEPS:
        out.append("INSERT INTO proj.lib_steps (phase, seq, name, source, marking, note)\n"
                   f"SELECT {lit(phase)}, coalesce(max(seq), 0) + 1, {lit(name)}, {lit(source)}, 'Added', '' FROM proj.lib_steps WHERE phase = {lit(phase)}\n"
                   "ON CONFLICT (phase, name) DO NOTHING;\n")
    out.append(_ins("proj.lib_items", ["id", "phase", "name", "kind", "type", "default_pick", "work_folder", "approved_folder", "templates",
                                       "content_area"],
                    [[i, ph, n, k, t, True, w, a, "", ""] for i, ph, n, k, t, w, a, _v in R12_ITEMS], "(id)"))
    out.append("UPDATE proj.lib_items i SET live_view = v.vp FROM (VALUES\n" + _values([[k, v] for k, v in LIVE_VIEWS.items()])
               + "\n) AS v (id, vp) WHERE i.id = v.id AND i.live_view = '';\n")
    return "".join(out)


def project_upgrade_sql() -> str:
    """Every existing project brought up to date with the library (D884: "Redo all existing projects and update them
    with this on script level"): the library's steps and document types it lacks, in the phases it has (a phase a
    project does not run is left alone); its items' live views; its repository built again where it has new document
    types; and its project management settings (RACI none, no gates: as it was). Each statement only adds what is missing, so it runs at every start and changes nothing twice."""
    return """
INSERT INTO proj.steps (project_id, cycle, phase, seq, name, library_id)
SELECT p.id, p.cycle, s.phase,
       (SELECT coalesce(max(x.seq), 0) + 1 FROM proj.steps x WHERE x.project_id = p.id AND x.cycle = p.cycle AND x.phase = s.phase),
       s.name, s.id
  FROM proj.projects p JOIN proj.lib_steps s ON NOT s.retired
 WHERE EXISTS (SELECT 1 FROM proj.steps h WHERE h.project_id = p.id AND h.cycle = p.cycle AND h.phase = s.phase)
   AND NOT EXISTS (SELECT 1 FROM proj.steps h WHERE h.project_id = p.id AND h.cycle = p.cycle AND h.library_id = s.id);
WITH added AS (
  INSERT INTO proj.items (project_id, cycle, phase, name, kind, type, library_id, chosen, folder, approved_folder, live_view)
  SELECT p.id, p.cycle, i.phase, i.name, i.kind, i.type, i.id, i.default_pick, i.work_folder, i.approved_folder, i.live_view
    FROM proj.projects p JOIN proj.lib_items i ON NOT i.retired
   WHERE EXISTS (SELECT 1 FROM proj.items h WHERE h.project_id = p.id AND h.cycle = p.cycle AND h.phase = i.phase)
     AND NOT EXISTS (SELECT 1 FROM proj.items h WHERE h.project_id = p.id AND h.cycle = p.cycle AND h.library_id = i.id)
  RETURNING project_id)
-- a project given new document types has its repository built again, so their folders are there (as queue_rebuild)
UPDATE proj.projects SET repo_state = CASE WHEN repo_state = 'building' THEN repo_state ELSE 'pending' END,
       repo_again = (repo_state = 'building'), repo_tries = 0
 WHERE id IN (SELECT project_id FROM added);
UPDATE proj.items t SET live_view = i.live_view FROM proj.lib_items i
 WHERE t.library_id = i.id AND t.live_view = '' AND i.live_view <> '';
INSERT INTO proj.pm_settings (project_id) SELECT id FROM proj.projects ON CONFLICT (project_id) DO NOTHING;
"""


def library_sql(d: dict | None = None) -> str:
    """The deliverables library as SQL to load."""
    d = d or data()
    out = [
        _ins("proj.lib_purposes", ["code", "name", "standard", "sort_order"],
             [[p["code"], p["name"], p["standard"], i * 10] for i, p in enumerate(d["purposes"], 1)], "(code)"),
        _ins("proj.lib_phases", ["code", "name", "workspace", "objectives", "inputs", "sort_order"],
             [[p["code"], p["name"], p["workspace"], p["objectives"], p["inputs"], p["sort"]] for p in d["phases"]], "(code)"),
        _ins("proj.lib_steps", ["phase", "seq", "name", "source", "marking", "note"],
             [[s["phase"], s["seq"], s["name"], s["source"], s["marking"] or "", s["note"] or ""] for s in d["steps"]], "(phase, name)"),
        _ins("proj.lib_items", ["id", "phase", "name", "kind", "type", "default_pick", "work_folder", "approved_folder", "templates",
                                "content_area"],
             [[i["id"], i["phase"], i["name"], i["kind"], i["type"] or "", i["default"] != "Not for use", i["work"], i["approved"] or "",
               i["templates"] or "", CF_ITEMS.get(i["name"], "")] for i in d["items"]], "(id)"),
        # where each document type sits in the content framework (D299): set where it is not chosen yet
        ("UPDATE proj.lib_items i SET content_area = v.a FROM (VALUES\n"
         + _values([[n, a] for n, a in CF_ITEMS.items()]) + "\n) AS v (n, a) WHERE i.name = v.n AND i.content_area = '';\n"),
        _ins("proj.lib_folders", ["path", "holds", "togaf_class", "origin"],
             [[f["path"], f["holds"] or "", f["togaf_class"] or "", f["origin"] or ""] for f in d["folders"]], "(path)"),
        _ins("proj.template_libraries", ["name", "kind", "description", "shared"],
             [[EA_EXPLORER, "ea-explorer", "EA Explorer's own starter templates: a file for every deliverable and artifact, "
               "the worked samples rebranded to [Organisation] where there is one", True],
              [TOGAF, "togaf", "The TOGAF Standard, 10th Edition: Template Deliverables (The Open Group I094). Only their "
               "names ship; a Super Admin loads the licensed files once.", True]], "(name)"),
    ]
    # project templates (D282): the shipped ones, added once; a Super Admin's changes are kept
    tpl = json.loads((HERE / "project_templates.json").read_text(encoding="utf-8"))["templates"]
    out.append(_ins("proj.project_templates", ["code", "name", "icon", "description", "spec", "builtin", "sort_order"],
                    [[t["code"], t["name"], t["icon"], t["description"],
                      json.dumps({k: v for k, v in t.items() if k not in ("code", "name", "icon", "description", "sort")}), True, t["sort"]]
                     for t in tpl], "(code)"))
    # TOGAF's templates by name (files loaded later); the other sources' names are covered by EA Explorer's own files
    togaf = [t for t in d["templates"] if t["source"] == "TOGAF 10"]
    if togaf:
        out.append(_lib_rows(TOGAF, ["path", "source", "code", "name", "phase", "purpose", "folder"],
                             [[f"{t['folder']}/{t['name']}".lstrip("/"), t["source"], t["code"] or "", t["name"], t["phase"] or "",
                               t["purpose"] or "", t["folder"] or ""] for t in togaf]))
    ours = ea_explorer_templates()
    if ours:
        out.append(_lib_rows(EA_EXPLORER, ["path", "item_id", "source", "name", "origin", "file_name"],
                             [[t["path"], t["item"], EA_EXPLORER, t["path"].rsplit("/", 1)[-1], t["origin"], t["path"].rsplit("/", 1)[-1]]
                              for t in ours]))
    # an item's sources: added with the item only (a re-run never duplicates them)
    src = [[i["id"], s["source"], s["phase"] or "", s["name"], s["kind"] or "", s["type"] or "", s["marking"] or "", s["note"] or "",
            s["files"] or "", s["location"] or ""] for i in d["items"] for s in i["sources"]]
    if src:
        out.append("INSERT INTO proj.lib_item_sources (item_id, source, phase, name, kind, type, marking, note, files, location)\n"
                   "SELECT v.* FROM (VALUES\n" + _values(src) + "\n) AS v (item_id, source, phase, name, kind, type, marking, note, files, location)\n"
                   "WHERE NOT EXISTS (SELECT 1 FROM proj.lib_item_sources s WHERE s.item_id = v.item_id);\n")
    out.append(r12_library_sql())
    return "".join(out)


def sample_principles_sql() -> str:
    """The sample principles as SQL to load."""
    d = json.loads((HERE / "sample_principles.json").read_text(encoding="utf-8"))
    return _ins("proj.lib_principles", ["code", "set_name", "category", "name", "statement", "rationale", "implications", "tier", "owner",
                                        "measure", "source"],
                [[p["code"], p["set"], p["category"] or "", p["name"], p["statement"] or "", p["rationale"] or "", p["implications"] or "",
                  p["tier"] or "", p["owner"] or "", p["measure"] or "", "Sample: Meridian Assurance Group (fictional)"]
                 for p in d["principles"]], "(code)")
