"""D838: the Questions page (a FAQ) on the website, and How do I under Documentation in place of the ? menu.

Owner, 21 Nov 2026, 20:51: "build a FAQ / How do I page and Have some sort of by role tabs + search. The in questions 1.
Give quick steps on the question in How do I 2. Point to the document 3. Point to the video (comming)"; "Also add them
to website"; 20:53: "The how do i should be a sub menu under documentation and we remove ? menu, ensure all test cases
are fixed".

Before: no such page; the screens' links to /site/how-do-i/... reached no file (the site is in /site/<version>/), and
help was on a ? menu at the top right. After: faq.html, every How do I page once as a question with its quick steps,
the page and printed guides to read and its video (or coming soon), role tabs and a filter; /site/index.html#to=<page>
opens that page of the newest copy; Documentation › How do I holds Help for this page, Questions and the How do I pages.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("build_website_d838", REPO / "tools/build_website.py")
W = importlib.util.module_from_spec(spec)
sys.modules["build_website_d838"] = W
spec.loader.exec_module(W)


def _faq(monkeypatch=None, vids=None) -> str:
    if monkeypatch is not None:
        monkeypatch.setattr(W, "videos", lambda: vids or {})
    made: dict[str, str] = {}
    W.build(write=False, made=made)
    return made["faq.html"]


def test_every_how_do_i_page_is_one_question_with_role_tabs_and_a_filter():
    page = _faq()
    tasks = list((REPO / "docs/site/how-do-i").glob("*.md"))
    assert page.count("<summary>How do I ") == len(tasks)                       # each once, not once a tab
    assert 'class="filter" placeholder="Type to find a question"' in page
    for code, name, _line in W.ROLES:
        assert f'data-tab="{code}">{name}</button>' in page
    assert 'data-tab="all" aria-selected="true">Every question</button>' in page
    assert re.search(r'data-roles="[^"]*project-admin[^"]*"', page) and re.search(r'data-roles="[^"]*model-admin', page)


def test_a_question_has_its_quick_steps_its_documents_and_its_video_coming():
    page = _faq()
    one = page[page.index("<summary>How do I tag a model?</summary>"):]
    one = one[:one.index("</details>")]
    assert "<h4>Quick steps</h4><ol><li>" in one and "Tag a model now" in one
    assert '<a href="how-do-i/tag-a-model.html">How do I: Tag a model</a>' in one
    assert "Administrator guide for models" in one and "chapter Versions, tags and merging" in one
    assert '<span class="quiet">Coming soon</span>' in one


def test_pages_a_guide_names_by_list_point_to_that_guide():
    """A guide's chapter can name its How do I pages in a list (howdoi:pages=a,b): those point to the guide too."""
    page = _faq()
    one = page[page.index("<summary>How do I get help on any screen?</summary>"):]
    one = one[:one.index("</details>")]
    assert "01. Overview" in one and "chapter Finding your way" in one


def test_a_video_shows_once_it_is_out(monkeypatch):
    page = _faq(monkeypatch, {"tag-a-model": "https://www.youtube.com/watch?v=abc"})
    one = page[page.index("<summary>How do I tag a model?</summary>"):]
    assert '<a href="https://www.youtube.com/watch?v=abc" target="_blank" rel="noopener">Watch the video' in one[:one.index("</details>")]
    data = json.loads((REPO / "docs/site/videos.json").read_text(encoding="utf-8"))
    assert data["videos"] == {} or all(v.startswith("https://") for v in data["videos"].values())


def test_questions_is_in_the_sites_top_bar():
    assert ("faq.html", "Questions") in W.SECTIONS


def test_the_screens_links_open_a_page_of_the_newest_copy_and_nothing_else():
    front = W.front_page(["7.9.0", "7.0.0"])
    assert 'window.location.replace("7.9.0/" + m[1])' in front
    assert r"^#to=([A-Za-z0-9_][A-Za-z0-9_./-]*\.html(#[A-Za-z0-9_-]+)?)$" in front     # a page of the site only
    assert 'm[1].indexOf("..") < 0 && m[1].indexOf("//") < 0' in front
    mcp = (REPO / "services/web/src/Mcp.jsx").read_text(encoding="utf-8")
    assert "/site/how-do-i/" not in mcp and "/site/index.html#to=how-do-i/" in mcp


def test_how_do_i_is_under_documentation_and_the_question_mark_menu_is_back():
    menu = (REPO / "services/web/src/menu.js").read_text(encoding="utf-8")
    # the ? menu came back (owner, 22 Nov 2026, 07:38: "Bring back ?", D840), with Questions in it too
    q = menu[menu.index('{ key: "help", label: "?"'):menu.index('key: "ai"')]
    assert 'action: "help"' in q and 'href: "/site/index.html#to=faq.html"' in q and 'place: "right"' in q
    docs = menu[menu.index('key: "docs"'):]
    how = docs[docs.index('{ label: "How do I", items: ['):]
    how = how[:how.index("] },")]
    for x in ('{ label: "Help for this page (F1)", action: "help" }', 'href: "/site/index.html#to=faq.html"',
              'href: "/site/index.html#to=how-do-i/index.html"'):
        assert x in how
    assert 'a.key === "help" ? "Help and documentation"' in (REPO / "services/web/src/TopMenu.jsx").read_text(encoding="utf-8")
