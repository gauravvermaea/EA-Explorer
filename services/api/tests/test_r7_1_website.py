"""Release 7.1: the website, the role guides and the How do I pages (D776; the owner, 18 Nov 2026, 12:54: "There needs to be
a Website. The website needs to be a sub folder inside the application and I should be just able to copy it seperately
and publish it"; "We need a number of How do I files in help. They should be able to print them as pdf"; "The 7.5 should
be part of 7.1"; 13:01: "tiles in tabs for roles", "Group them by some common", "allow search"; 13:48: "a seperate how
do I file per task with screenshots... make 170+ files"; "For each user case and each how do I seperate task page": D777).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SITE_ROOT = REPO / "services/web/public/site"
spec = importlib.util.spec_from_file_location("build_website", REPO / "tools/build_website.py")
W = importlib.util.module_from_spec(spec)
sys.modules["build_website"] = W
spec.loader.exec_module(W)
SITE = SITE_ROOT / W.version()   # each release its own copy (D778)


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
        now = (SITE / name).read_bytes() if isinstance(text, bytes) else (SITE / name).read_text(encoding="utf-8")
        assert now == text, f"{name} is out of date: run python tools/build_website.py"
    on_disk = {p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file()} - {"README.txt"}
    assert on_disk == set(made), f"left over: {sorted(on_disk - set(made))}"


def test_every_role_has_its_guide_and_its_tasks():
    _problems, made = _built()
    for code, _name, _line in W.ROLES:
        page = made[f"roles/{code}.html"]
        assert "How do I: your tasks" in page, code
        assert f'data-pane="{code}"' in made["how-do-i/index.html"], code
    assert {c for c, _n, _l in W.ROLES} == {"system-admin", "model-admin", "project-admin", "user", "industry-modeller",
                                            "developer", "executive", "platform-developer"}
    assert W.ROLE_NAME["user"] == "Practising architects"   # the owner, 18 Nov 2026, 16:36


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
    front = (SITE_ROOT / "index.html").read_text(encoding="utf-8")
    assert front == W.front_page(W.releases_on_disk()) and f'url={W.version()}/index.html' in front
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


def test_one_task_a_page_more_than_170_each_with_its_screen():
    """D777: a page per task, each naming the screen its picture shows; the list eax site shots works from is current."""
    pages = sorted((REPO / "docs/site/how-do-i").glob("*.md"))
    assert len(pages) >= 170, len(pages)
    for p in pages:
        meta, md = W.front_matter(p.read_text(encoding="utf-8"))
        assert re.fullmatch(r"(#/|/)\S*", meta.get("screen", "")), p.name
        assert md.count("## Steps") <= 1, p.name
    rows = W.screens_list(W.collect())
    assert (REPO / "docs/site/shots/screens.json").read_text(encoding="utf-8") == rows, "run python tools/build_website.py"
    import json
    listed = json.loads(rows)
    assert {r["page"] for r in listed} == {p.stem for p in pages}
    assert len({r["file"] for r in listed}) == len(listed)


def test_a_page_shows_its_picture_or_where_it_will_go():
    _problems, made = _built()
    page = made["how-do-i/add-an-entity.html"]
    if (REPO / "docs/site/shots/add-an-entity.png").is_file():
        assert '<img src="../shots/add-an-entity.png"' in page and "shots/add-an-entity.png" in made
    else:
        assert 'class="shot missing"' in page and "#/metamodel/{m}/entry" in page and "eax site shots" in page
    css = (REPO / "docs/site/assets/site.css").read_text(encoding="utf-8")
    assert ".shot.missing { display: none; }" in css   # a box with no picture is not printed


def test_the_pictures_are_taken_by_opening_pages_only():
    """The owner's rule for anything run against an installation: it only opens screens (D777). D781 widened it to what a
    page's do: line names: a tab, a link followed, a card picked, or a dialog opened by a button that only opens one (a
    label ending in ..., or one in OPENERS); the dialog is closed with Escape and nothing is ever saved. Signing in is the
    only form it fills; it is a command of its own (eax site shots), never part of eax test."""
    src = (REPO / "services/api/eax/testing/site_shots.py").read_text(encoding="utf-8")
    assert src.count(".click(") == 3 and 'page.click("#kc-login")' in src and 'name="Sign in", exact=True).first.click()' in src
    assert "el.click()" in src   # the one other click: what actions() allowed
    assert src.count(".fill(") == 2 and ".type(" not in src and "request.post" not in src
    assert src.count(".press(") == 1 and 'keyboard.press("Escape")' in src
    assert "site_shots" not in (REPO / "services/api/eax/testing/run.py").read_text(encoding="utf-8")
    sys.path.insert(0, str(REPO))
    from eaxcli import site_cli
    cmd = site_cli.shots_command(["--missing"])
    assert cmd[:3] == ["--profile", "test", "run"] and cmd[-2:] == ["eax.testing.site_shots", "--missing"]
    assert any(a.endswith(":/site-src") for a in cmd)
    for launcher, words in (("eax.ps1", '"settings", "site", "errors")'), ("eax.sh", "settings|site|errors)")):   # errors: R7.9, D789
        assert words in (REPO / launcher).read_text(encoding="utf-8"), launcher
    assert "### site [build|check|shots|pdfs]" in (REPO / "eaxcli/help.txt").read_text(encoding="utf-8")


def test_a_pages_do_line_only_opens_things():
    """D781: tab, open, follow and pick, nothing else; open takes a label ending in ... or one read and listed in
    OPENERS; every How do I page's do: line is one the picture taker understands."""
    sys.path.insert(0, str(REPO / "services/api"))
    from eax.testing import site_shots as S
    assert S.actions('tab "Deliveries"; open "Make a key..."') == [("tab", "Deliveries"), ("open", "Make a key...")]
    assert S.actions('follow "Claims Platform"; pick "Backups"') == [("follow", "Claims Platform"), ("pick", "Backups")]
    assert S.actions('open "Bring data in"') == [("open", "Bring data in")]
    for bad in ('open "Delete"', 'open "Save"', 'click "Restore"', 'tab Deliveries'):
        try:
            S.actions(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} was allowed")
    assert S.same_words("tab", "Relations (8)", "Relations") and not S.same_words("tab", "Relationsx", "Relations")
    assert S.same_words("open", "⬇ Bring data in", "Bring data in") and not S.same_words("open", "Bring data in now", "Bring data in")
    assert S.same_words("pick", "Backups What is backed up, when", "Backups")
    for p in sorted((REPO / "docs/site/how-do-i").glob("*.md")):
        meta, _md = W.front_matter(p.read_text(encoding="utf-8"))
        for key in ("do", "do2"):
            if meta.get(key):
                S.actions(meta[key])   # raises on a line it would not follow


def test_the_picture_taker_fills_the_demo_ids_and_skips_what_it_cannot():
    sys.path.insert(0, str(REPO / "services/api"))
    from eax.testing import site_shots as S
    ids = {"model": "m1", "project": ""}
    assert S.fill("#/metamodel/{m}/grid", ids) == "#/metamodel/m1/grid"
    assert S.fill("#/projects/{p}/tasks", ids) is None
    assert S.fill("#/admin/backups", ids) == "#/admin/backups"
    links = [["Pin Protea Insurance (demo estate) model", "#/metamodel/abc-1"], ["x", "#/metamodel/new"],
             ["Protea Claims Transformation 2028 (sample)", "#/projects/77"], ["Protea Claims Transformation 2028 (sample)", "#/projects/77/models"]]
    assert S.id_from(links, "Protea Insurance (demo estate)", "model") == "abc-1"
    assert S.id_from(links, "Protea Claims Transformation 2028 (sample)", "project") == "77"
    # a tile that names another model (18 Nov 2026: the clean-up model was taken for the demo estate)
    tiles = [["Protea Insurance clean-up (MCP) merges into Protea Insurance (demo estate)", "#/metamodel/clean"],
             ["Protea Insurance (demo estate)", "#/metamodel/estate"]]
    assert S.id_from(tiles, "Protea Insurance (demo estate)", "model") == "estate"
    assert S.id_from([["Protea Claims Transformation 2028", "#/projects/9"]], "Protea Claims Transformation 2028 (sample)",
                     "project") == "9"
    # Project admin's list links #/project-admin/<id>; the Super Admin is on no project, so it is the only list that
    # shows the demo project (18 Nov 2026: all 48 project pictures skipped). Its tabs are not projects.
    admin = [["Projects", "#/project-admin/list"], ["Bases", "#/project-admin/bases"],
             ["Protea Claims Transformation 2028 (sample)", "#/project-admin/p-42"]]
    assert S.id_from(admin, "Protea Claims Transformation 2028 (sample)", "project") == "p-42"
    assert S.id_from([["Projects", "#/project-admin/list"]], "Projects", "project") == ""
    # a tile's words start with its kind mark, so neither starts with the name (18 Nov 2026: the clean-up model again):
    # the name nearest the start wins, and the picture taker reads the tile's bold name first
    marked = [["● Protea Insurance clean-up (MCP) 348 entities · merges into Protea Insurance (demo estate)", "#/metamodel/clean"],
              ["● Protea Insurance (demo estate) 900 entities", "#/metamodel/estate"]]
    assert S.id_from(marked, "Protea Insurance (demo estate)", "model") == "estate"
    assert "querySelector('b')" in (REPO / "services/api/eax/testing/site_shots.py").read_text(encoding="utf-8")
    rows =[{"page": "a", "file": "a.png"}, {"page": "b", "file": "b.png"}]
    assert [r["page"] for r in S.wanted(rows, {"b"}, False, Path("/nowhere"))] == ["b"]
    assert S.args(["--only", "a,b", "--missing"])["only"] == {"a", "b"}


def test_a_how_do_i_page_is_one_simple_task_and_a_guide_links_its_tasks():
    """The owner, 18 Nov 2026, 14:12: "Each is simple one task only", "and then other pages as discussed": a topic with
    several tasks is a Guide, listing each task's own How do I page in order."""
    for p in sorted((REPO / "docs/site/how-do-i").glob("*.md")):
        _meta, md = W.front_matter(p.read_text(encoding="utf-8"))
        assert "## Each task, one page" not in md, p.name
        assert len(re.findall(r"^\d+\. ", md, re.M)) <= 6, f"{p.name}: more than six steps is more than one task"
    guides = sorted((REPO / "docs/site/guides").glob("*.md"))
    assert len(guides) >= 15
    for g in guides:
        meta, md = W.front_matter(g.read_text(encoding="utf-8"))
        tasks = re.findall(r"\]\(\.\./how-do-i/([a-z0-9-]+)\.md\)", md[md.index("## Each task, one page"):])
        assert len(tasks) >= 2 and meta.get("roles"), g.name
        for t in tasks:
            assert (REPO / "docs/site/how-do-i" / f"{t}.md").is_file(), (g.name, t)
    _problems, made = _built()
    assert "guides/index.html" in made and 'href="../guides/index.html"' in made["how-do-i/index.html"]
    assert "Read first: concepts and guides for you" in made["roles/system-admin.html"]


def test_an_old_copy_of_a_page_that_became_a_guide_is_left_out(tmp_path, monkeypatch):
    """A laptop that still has the older page (it moved to Guides on 18 Nov 2026) builds the same site, not two pages."""
    import shutil
    src = tmp_path / "docs/site"
    shutil.copytree(REPO / "docs/site", src)
    (tmp_path / "docs/guides").mkdir()
    (tmp_path / "releases").mkdir()
    shutil.copy(src / "guides/restore-a-backup.md", src / "how-do-i/restore-a-backup.md")
    monkeypatch.setattr(W, "ROOT", tmp_path)
    monkeypatch.setattr(W, "SRC", src)
    outs = {p.out for p in W.collect()}
    assert "guides/restore-a-backup.html" in outs and "how-do-i/restore-a-backup.html" not in outs


def test_site_build_deletes_only_the_old_copies_of_pages_that_became_guides(tmp_path):
    sys.path.insert(0, str(REPO))
    from eaxcli import site_cli
    for d in ("docs/site/guides", "docs/site/how-do-i"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "docs/site/guides/restore-a-backup.md").write_text("guide")
    (tmp_path / "docs/site/how-do-i/restore-a-backup.md").write_text("old")
    (tmp_path / "docs/site/how-do-i/back-up-now.md").write_text("task")
    assert site_cli.remove_old_copies(tmp_path) == ["restore-a-backup.md"]
    assert sorted(p.name for p in (tmp_path / "docs/site/how-do-i").iterdir()) == ["back-up-now.md"]
    assert (tmp_path / "docs/site/guides/restore-a-backup.md").read_text() == "guide"


def test_eax_site_loads_the_builder_on_its_own():
    """The bug of 18 Nov 2026, 14:52: eax site shots stopped at "'NoneType' object has no attribute '__dict__'" (the
    builder loaded without being registered, so its dataclass found no module). Run in a fresh Python, as eax runs it."""
    import subprocess
    code = "import sys; sys.path.insert(0, '.'); from eaxcli import site_cli; print(site_cli._builder().build(write=False))"
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().endswith("[]")


def test_every_page_says_why_with_its_goal_and_where_it_sits_in_togaf():
    """The owner, 18 Nov 2026, 16:36: "Each guide item how do I role needs to have 1-2 paragraphs of context"; 16:39:
    "in how do I put what is the goal"; 16:48: "how it is with TOGAF"."""
    for folder in ("how-do-i", "guides"):
        for p in sorted((REPO / "docs/site" / folder).glob("*.md")):
            _meta, md = W.front_matter(p.read_text(encoding="utf-8"))
            why = md.split("## Why do this", 1)
            assert len(why) == 2 and md.index("## Why do this") == md.index("## "), f"{p.name}: the context comes first"
            assert "**The goal:**" in why[1] and "**In TOGAF terms:**" in why[1], p.name
            assert len(why[1].split("**In TOGAF terms:**")[0].split()) >= 15, f"{p.name}: too little context"
    for code, _n, _l in W.ROLES:
        md = (REPO / "docs/site/roles" / f"{code}.md").read_text(encoding="utf-8")
        for head in ("## A day in your life", "## Where EA Explorer fits", "## Where you sit in TOGAF"):
            assert head in md, (code, head)


def test_concepts_cover_the_thinking_and_pages_link_like_a_wiki():
    """The owner, 16:36: "pages around phelosphy of project ADM, meta model what they are how they are used different
    types of projecs and there goals"; 16:37: "Have one topic link to other as in a wiki"."""
    have = {p.stem for p in (REPO / "docs/site/concepts").glob("*.md")}
    assert {"the-adm", "metamodels", "kinds-of-projects", "ea-explorer-and-togaf", "data-quality", "enterprise-architecture"} <= have
    problems, made = _built()
    assert problems == [] and "concepts/index.html" in made
    assert 'href="../concepts/the-adm.html"' in made["how-do-i/choose-the-adm-cycle.html"]
    assert "[[" not in "".join(v for k, v in made.items() if k.endswith(".html"))
    W.WIKI_MISSES.clear()
    assert W.WIKI.sub("x", "see [[no-such-page]]") == "see x"


def test_developers_have_an_integrate_section_and_platform_developers_a_platform_section():
    """The owner, 18 Nov 2026, 16:51: "build a whole section for developers how they can work different kinds of
    connectors, oData reports ingestion etc"; "another section for platform developers how they can bring the software
    for Dev and debugging"."""
    have = {f: {p.stem for p in (REPO / "docs/site" / f).glob("*.md")} for f in ("integrate", "platform")}
    assert {"build-a-connector", "import-formats", "deliveries", "push-sources", "odata-sources", "odata-feeds",
            "build-reports-on-odata", "webhooks", "rest-api"} <= have["integrate"]
    assert {"run-it-on-your-machine", "debug-it", "test-it", "make-a-change", "release-it"} <= have["platform"]
    _problems, made = _built()
    assert "integrate/index.html" in made and "platform/index.html" in made
    assert 'href="../integrate/index.html"' in made["how-do-i/index.html"]


def test_every_report_has_a_page_made_from_the_catalogue():
    """The owner, 18 Nov 2026, 17:03: "Have one for reports too but reports will not need screenshots, just describe each
    reprort in some detail and how to use it" (D779): tools/build_report_pages.py writes them from the app's catalogue."""
    import subprocess
    out = subprocess.run([sys.executable, "tools/build_report_pages.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    sys.path.insert(0, str(REPO / "services/api"))
    from eax import report_defs
    pages = list((REPO / "docs/site/reports").glob("*.md"))
    assert len(pages) == len(report_defs.REPORTS)
    for p in pages:
        md = p.read_text(encoding="utf-8")
        assert "screen:" not in md and "## How to use it" in md and "## How to read it" in md and "**In TOGAF terms:**" in md
    _problems, made = _built()
    assert "reports/index.html" in made and "reports/report-sr-01.html" in made


def test_the_site_lists_files_in_the_same_order_on_every_machine():
    """D798: sorting Path objects is case-blind on Windows, so README.md moved after backups.md
    there and the search index built on the laptop differed from the test runner's."""
    from pathlib import PureWindowsPath

    class WindowsFolder:
        def glob(self, pattern):
            return [PureWindowsPath(f"C:/g/{n}") for n in ("backups.md", "README.md", "catastrophe.md")]

    # Before the fix: plain sorted() on Windows paths puts backups.md first.
    assert sorted(WindowsFolder().glob("*.md"))[0].name == "backups.md"
    # After: ordered by plain name, as on Linux.
    assert [p.name for p in W.listed(WindowsFolder())] == ["README.md", "backups.md", "catastrophe.md"]


def test_the_site_builder_never_sorts_a_raw_folder_listing():
    """Every listing goes through listed(), so no new one can bring the Windows order back."""
    text = (REPO / "tools/build_website.py").read_text(encoding="utf-8")
    text = text.replace("sorted(folder.glob(pattern), key=lambda f: f.name)", "")  # listed() itself
    assert not re.search(r"sorted\(\s*\(?[\w. /\"]+\)?\.glob\(", text), "use listed(folder, pattern)"


def test_the_printed_guides_copied_into_the_site_count_as_made(tmp_path, monkeypatch):
    """D799: the build copied documents/*.pdf into the site's manuals/ but left them out of what it made, so the
    up-to-date check called all 25 PDFs left over. Now each PDF is part of the build, byte for byte."""
    guide = W.printed_guides()[0]["file"] if W.printed_guides() else "EA-Explorer-01-overview.pdf"
    (tmp_path / guide).write_bytes(b"%PDF-1.4 test")
    monkeypatch.setattr(W, "DOCUMENTS", tmp_path)
    made: dict = {}
    assert W.build(write=False, made=made) == []
    assert made.get(f"manuals/{guide}") == b"%PDF-1.4 test"
    listed_json = __import__("json").loads(made["manuals/manuals.json"])
    assert [g["file"] for g in listed_json["guides"]] == [guide]


def test_the_site_without_printed_guides_makes_no_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "DOCUMENTS", tmp_path)
    made: dict = {}
    W.build(write=False, made=made)
    assert not [n for n in made if n.endswith(".pdf")]
