"""Release 7.1: the website, the role guides and the How do I pages (D776; the owner, 18 Nov 2026, 12:54: "There needs to be
a Website. The website needs to be a sub folder inside the application and I should be just able to copy it seperately
and publish it"; "We need a number of How do I files in help. They should be able to print them as pdf"; "The 7.5 should
be part of 7.1"; 13:01: "tiles in tabs for roles", "Group them by some common", "allow search").
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SITE = REPO / "services/web/public/site"
spec = importlib.util.spec_from_file_location("build_website", REPO / "tools/build_website.py")
W = importlib.util.module_from_spec(spec)
sys.modules["build_website"] = W
spec.loader.exec_module(W)


def _built() -> tuple[list[str], dict[str, str]]:
    made: dict[str, str] = {}
    return W.build(write=False, made=made), made


def test_the_site_builds_with_no_link_to_nowhere_and_the_folder_is_up_to_date():
    """The folder is what gets copied and published: it must be the build of today's sources (python
    tools/build_website.py after changing docs/site, docs/guides or releases)."""
    problems, made = _built()
    assert problems == []
    for name, text in made.items():
        assert (SITE / name).is_file(), f"{name} is missing: run python tools/build_website.py"
        assert (SITE / name).read_text(encoding="utf-8") == text, f"{name} is out of date: run python tools/build_website.py"
    on_disk = {p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file()} - {"README.txt"}
    assert on_disk == set(made), f"left over: {sorted(on_disk - set(made))}"


def test_every_role_has_its_guide_and_its_tasks():
    _problems, made = _built()
    for code, name, _line in W.ROLES:
        page = made[f"roles/{code}.html"]
        assert "How do I: your tasks" in page, code
        assert f'data-pane="{code}"' in made["how-do-i/index.html"], code
    assert {c for c, _n, _l in W.ROLES} == {"system-admin", "model-admin", "project-admin", "user", "industry-modeller",
                                            "developer"}


def test_every_how_do_i_page_is_a_task_with_a_topic_and_prints():
    for p in sorted((REPO / "docs/site/how-do-i").glob("*.md")):
        meta, md = W.front_matter(p.read_text(encoding="utf-8"))
        assert meta.get("title") and meta.get("summary"), p.name
        assert meta.get("group") in W.GROUP_ORDER, (p.name, meta.get("group"))
        assert meta.get("roles") and all(r in W.ROLE_NAME for r in meta["roles"]), p.name
        assert "## Steps" in md or "## Things to ask" in md, p.name
        assert "objective" not in md.lower(), p.name
    _problems, made = _built()
    for name, text in made.items():
        if name.startswith("how-do-i/") and name != "how-do-i/index.html":
            assert 'class="print"' in text and "Print or save as PDF" in text, name
    css = (REPO / "docs/site/assets/site.css").read_text(encoding="utf-8")
    assert "@media print" in css and ".top, .page-tools" in css


def test_how_do_i_is_tiles_in_role_tabs_grouped_by_topic_with_a_filter():
    _problems, made = _built()
    index = made["how-do-i/index.html"]
    assert 'class="role-tabs"' in index and 'data-tab="all"' in index and 'class="filter"' in index
    assert index.count('class="group"') >= len(W.ROLES) and 'class="tiles"' in index and "data-words=" in index
    js = (REPO / "docs/site/assets/site.js").read_text(encoding="utf-8")
    assert ".role-tabs button" in js and 'filter.addEventListener("input"' in js


def test_the_site_can_be_copied_anywhere_and_works_offline():
    """Relative links only, no script in the page itself (the front door's Content-Security-Policy), nothing fetched,
    search from a file made with the site, and the YouTube channel linked."""
    _problems, made = _built()
    for name, text in made.items():
        if not name.endswith(".html"):
            continue
        assert not re.search(r'(href|src)="/(?!/)', text), f"{name}: an address from the server's root"
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text), f"{name}: a script in the page"
        assert "search-index.js" in text and "https://www.youtube.com/@ea-explorer-os" in text, name
    js = (REPO / "docs/site/assets/site.js").read_text(encoding="utf-8")
    assert "fetch(" not in js and "XMLHttpRequest" not in js
    assert "window.EAX_SEARCH" in made["assets/search-index.js"]


def test_the_app_serves_the_site_and_links_it():
    nginx = (REPO / "services/web/nginx/default.conf.template").read_text()
    assert "location /site/" in nginx and "try_files $uri $uri/index.html =404" in nginx
    assert '"/site/index.html"' in (REPO / "services/web/src/menu.js").read_text()


def test_every_ai_tool_area_is_on_a_tile_with_its_how_do_i_page():
    """R7.5 inside R7.1: What it can do as tiles, each opening its help page; every tool still listed below them."""
    sys.path.insert(0, str(REPO / "services/api"))
    from eax import mcp_catalogue
    page = (REPO / "services/web/src/Mcp.jsx").read_text(encoding="utf-8")
    tiles = page[page.index("export const AI_TILES"):page.index("function WhatItCanDo")]
    for area in mcp_catalogue.AREAS.values():
        assert f'"{area}"' in tiles, f"no tile for the tools of {area}"
    for slug in re.findall(r'page: "([a-z0-9-]+)"', tiles):
        assert (REPO / "docs/site/how-do-i" / f"{slug}.md").is_file(), slug
    assert '["tools", "What it can do"]' in page and "<ToolList only={areas}" in page
