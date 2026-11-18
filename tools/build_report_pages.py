"""The website's Reports section: one page for every standard report and dashboard (Release 7.1, D779).

The owner, 18 Nov 2026, 17:03: "Have one for reports too but reports will not need screenshots, just describe each
reprort in some detail and how to use it".

    python tools/build_report_pages.py           writes docs/site/reports/*.md from the report catalogue
    python tools/build_report_pages.py --check   says whether they are current (a test runs this)

The pages are made from the same catalogue the app uses (services/api/eax/report_defs.py and report_about.py), so a
new or changed report changes its page: run this, then python tools/build_website.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "site" / "reports"
sys.path.insert(0, str(ROOT / "services" / "api"))

from eax import report_about, report_defs

AUDIENCE = {code: (name, group) for code, name, group in report_defs.AUDIENCES}
VIEWS = {v["code"]: v for v in report_defs.VIEWS}
EXECUTIVE = {"ceo", "cfo", "cio", "cto", "coo", "cro", "ciso", "cdo", "cco", "bu_head", "architecture_board", "portfolio_manager"}

FAMILY_WHY = {
    "Standard": "The standard reports answer the questions most architecture practices are asked again and again: what we "
                "have, what it costs, how it depends on what, and where the risks are. They work on any model built on a "
                "metamodel with the matching types and attributes.",
    "TOGAF catalogue": "A catalogue, in the TOGAF Standard's content framework, is a structured list of one kind of building "
                       "block with its key attributes: the reference others check against. This one belongs to the ADM "
                       "phase shown above.",
    "TOGAF matrix": "A matrix, in the TOGAF Standard's content framework, shows how two kinds of building block relate: "
                    "rows of one kind, columns of the other, a mark where they are connected. It answers \"what touches "
                    "what\" at a glance.",
    "View": "Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the "
            "element and relationship types that matter to them. EA Explorer shows each one from your model as a "
            "catalogue, a matrix, a network and a heat map.",
    "Audience": "An audience dashboard gathers, on one page, the headline charts of the reports one kind of person usually "
                "needs, so they start from what matters to them instead of browsing the whole catalogue.",
    "Gap analysis": "Gap analysis compares a baseline with a target and keeps the differences: the bridge, in ADM phase E, "
                    "from the target architecture to the plan.",
    "Dependency": "Dependency reports follow relationships step by step, upstream and downstream, to show what a change "
                  "would affect and what something relies on.",
    "Data quality": "Data quality reports show how far each model can be trusted, and where to start improving it.",
    "KPI trends": "KPI trends show how each model's key figures move over time, kept on the 1st of every month and at every tag.",
}
FAMILY_TOGAF = {
    "TOGAF catalogue": "A catalogue of the TOGAF content framework (phase: {group}).",
    "TOGAF matrix": "A matrix of the TOGAF content framework (phase: {group}).",
    "View": "An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below.",
    "Gap analysis": "ADM phase E, Opportunities and Solutions (gap analysis is also used in phases B to D).",
    "Dependency": "Impact analysis, used in every phase that weighs a change, and in phase H.",
    "Data quality": "Supports every phase: the content framework is only useful if its building blocks are complete and correct.",
    "KPI trends": "Architecture governance and the architecture capability: measuring the repository over time.",
    "Audience": "Stakeholder management: each audience sees the views that address its concerns.",
    "Standard": "Architecture views and catalogues that address common stakeholder concerns, in phases B to F.",
}
CODE = re.compile(r"\b((?:SR|TC|TM|VP|GR|DR|QR|HM|KR)-\d+)\b")


def slug(code: str) -> str:
    """The page's file name: report-sr-01, report-au-ceo."""
    return "report-" + code.lower().replace("_", "-")


def _types(names: list[str]) -> str:
    return ", ".join(re.sub(r"(?<!^)(?=[A-Z])", " ", n) for n in names)


def _link_codes(text: str, codes: set[str]) -> str:
    return CODE.sub(lambda m: f"[[{slug(m.group(1))}|{m.group(1)}]]" if m.group(1) in codes else m.group(1), text)


def _roles(r: dict) -> str:
    aud = set(r.get("audiences", []))
    roles = ["user"]
    if aud & EXECUTIVE:
        roles.append("executive")
    if aud & {"model_owner", "data_steward"} or r.get("family") == "Data quality":
        roles.append("model-admin")
    if aud & {"it_operations", "internal_audit"}:
        roles.append("system-admin")
    return ", ".join(roles)


def page(r: dict, codes: set[str], reports: list[dict]) -> str:
    """One report's page."""
    about = report_about.about(r)
    family = r.get("family", "Standard")
    who = [AUDIENCE.get(a, (a, ""))[0] for a in r.get("audiences", [])]
    title = r["title"]
    lines = ["---", f"title: {r['code']} {title}", f"summary: {r['about'].split('. From the ArchiMate')[0].rstrip('.')}.",
             f"group: {family}", f"roles: {_roles(r)}", "---", ""]
    detail: list[str] = []   # what it shows beyond its summary (the summary is shown at the top of the page)
    if ". From the ArchiMate" in r["about"]:
        detail += ["From the " + r["about"].split(". From the ", 1)[1], ""]
    elif CODE.search(r["about"]):
        detail += [_link_codes(r["about"], codes), ""]
    if family == "View" and r.get("view_code") in VIEWS:
        v = VIEWS[r["view_code"]]
        detail += [f"**Its concerns:** {v['concerns']}. **For:** {v['stakeholders']}. **Purpose:** {v['purpose']}.", "",
                  f"**Element types shown:** {_types(v['element_types'])}.", "",
                  f"**Relationships shown:** {', '.join(v['relationship_types'])}. The heat map colours by **{v['heat_attribute']}**.", ""]
        if v.get("togaf_artifact"):
            detail += [f"**The TOGAF artifact it supports:** {v['togaf_artifact']}.", ""]
        also = report_defs.VIEW_REPORTS.get(r["view_code"], [])
        if also:
            detail += ["**Reports that go with it:** " + ", ".join(f"[[{slug(c)}|{c}]]" for c in also if c in codes) + ".", ""]
    if family == "TOGAF matrix" and r.get("a_types"):
        detail += [f"**Rows:** {_types(r['a_types'])}. **Columns:** {_types(r['b_types'])}.", ""]
    if family == "Audience":
        aud = r.get("audience")
        inside = [x for x in reports if x.get("family") != "Audience" and aud in x.get("audiences", [])]
        if inside:
            detail += ["**What it gathers:** " + ", ".join(f"[[{slug(x['code'])}|{x['code']} {x['title']}]]" for x in inside) + ".", ""]
    if detail:
        lines += ["## What it shows", "", *detail]
    lines += ["## Why it matters", "", FAMILY_WHY.get(family, FAMILY_WHY["Standard"]), "",
              (f"**In TOGAF terms:** {FAMILY_TOGAF.get(family, FAMILY_TOGAF['Standard']).format(group=r.get('group', ''))} "
               "See [[ea-explorer-and-togaf]]."), "",
              "## Who it is for", "", ", ".join(who) + "." if who else "Anyone who reads the model.", "",
              "## How to use it", "", _link_codes(about["use"], codes), "",
              "## How to read it", "", _link_codes(about["read"], codes), "",
              "## Where to find it", "",
              (f"Open a model, **Reports › Reports**, and choose **{title}**; it opens its dashboard for that model. Every "
               "chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in "
               "the model's OData feed for your own tools ([[odata-feeds]])."), ""]
    if r.get("view"):
        lines += [f"For developers and report builders: it reads `{r['view']}`; its dashboard is `{r['slug']}`.", ""]
    lines += ["## Related", "", "- [[views-and-reports]]", "- [[open-a-standard-report]]", "- [[build-your-own-report]]"]
    return "\n".join(lines) + "\n"


def pages() -> dict[str, str]:
    """Every report's page by its file name."""
    reports = report_defs.REPORTS
    codes = {r["code"] for r in reports}
    return {f"{slug(r['code'])}.md": page(r, codes, reports) for r in reports}


def main(argv: list[str]) -> int:
    """Writes the pages (or, with --check, says which are out of date)."""
    made = pages()
    if "--check" in argv:
        stale = [n for n, t in made.items() if not (OUT / n).is_file() or (OUT / n).read_text(encoding="utf-8") != t]
        extra = sorted(p.name for p in OUT.glob("*.md") if p.name not in made) if OUT.is_dir() else []
        for n in stale + extra:
            print(f"  out of date: docs/site/reports/{n}")
        return 1 if stale or extra else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.md"):
        if p.name not in made:
            p.unlink()
    for name, text in made.items():
        (OUT / name).write_text(text, encoding="utf-8")
    print(f"{len(made)} report pages in docs/site/reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
