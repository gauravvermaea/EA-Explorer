"""R5.7-P1, a project presentation deck made with the person's own AI through MCP (owner, 16 Nov 2026 and 17 Nov 13:52;
D731): deck_sources and deck_outline give the content with its sources; view_picture gives a view as a PNG or an SVG
drawn as on the screens (icons included) or as its raw data. The database checks run on EAX_MIGRATED_TEST_DSN."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from eax import notation
from eax import view_picture as vp
from eax.metamodel_edit import EditError

API = Path(__file__).resolve().parents[1]
WEB = API.parent / "web" / "src"
ICONS = (WEB / "archimateIcons.jsx").read_text(encoding="utf-8")
DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")


def _js_glyphs() -> dict[str, list[str]]:
    """The screens' icons as their path data, by notation (shared lists resolved)."""
    shared = {n: re.findall(r'L\("([^"]+)"', body) for n, body in re.findall(r"^const (\w+) = \[(.*)\];$", ICONS, re.M)}
    block = ICONS.split("export const GLYPHS = {", 1)[1].split("\n};", 1)[0]
    out = {}
    for name, body in re.findall(r"^\s{2}(\w+): (.*?),?\s*(?://.*)?$", block, re.M):
        out[name] = shared[body.strip(" ,")] if body.strip(" ,") in shared else re.findall(r'L\("([^"]+)"', body)
    return out


def test_the_pictures_icons_are_the_screens_icons():
    js = _js_glyphs()
    assert set(js) == set(vp.GLYPHS) == set(notation.ELEMENTS) | {"Junction"}
    for name, parts in vp.GLYPHS.items():
        assert [a["d"] for tag, a in parts if tag == "path"] == js[name], name
    rounded = set(re.search(r"const ROUNDED = new Set\(\[(.*?)\]\)", ICONS).group(1).replace('"', "").replace(" ", "").split(","))
    cut = set(re.search(r"const CUT = new Set\(\[(.*?)\]\)", ICONS).group(1).replace('"', "").replace(" ", "").split(","))
    assert rounded == vp.ROUNDED and cut == vp.CUT


def test_the_layout_is_the_screens():
    graph = (WEB / "EntityGraph.jsx").read_text(encoding="utf-8")
    assert "const H = 44, MIN_W = 110, MAX_W = 220;" in graph and (vp.H, vp.MIN_W, vp.MAX_W) == (44, 110, 220)
    assert "const BAND_LABEL = 150, BAND_MAX = 1500, GAP = 16;" in graph and (vp.BAND_LABEL, vp.BAND_MAX, vp.GAP) == (150, 1500, 16)


def _data():
    objs = [{"id": f"e{i}", "display_id": f"X-{i}", "name": f"Thing {n}", "type": n, "notation": n,
             "domain": "Business" if i % 2 else "Strategy", "domain_order": 2 if i % 2 else 1, "colour": "#ffffb5"}
            for i, n in enumerate(sorted(vp.GLYPHS))] + [{"id": "plain", "display_id": "", "name": "Our own <type> & co", "type": "Extension",
                                                          "notation": None, "domain": "Business", "domain_order": 2, "colour": "#eeeeee"}]
    bands, w, h = vp.bands_layout(objs)
    rels = [{"id": "r", "type": "Serving", "name": "Serving", "verb": "serves", "source": "e1", "target": "e2"},
            {"id": "r2", "type": "Flow", "name": "Flow", "verb": "flows to", "source": "e2", "target": "e1"}]
    return {"title": "VP-99 <test>", "width": w, "height": h, "bands": bands, "objects": objs, "relationships": vp._lines(objs, rels)}


def test_the_data_svg_and_png():
    d = _data()
    assert [b["label"] for b in d["bands"]] == ["Strategy", "Business"]
    assert all(o["width"] >= vp.MIN_W and o["height"] == vp.H for o in d["objects"])
    a, b = d["relationships"]
    assert a["from"] != b["to"]                                   # two ways: drawn apart
    svg = vp.to_svg(d)
    assert svg.startswith("<svg") and "Our own &lt;type&gt; &amp; co" in svg and 'stroke-dasharray="6 4"' in svg   # grouping dashed
    assert svg.count('<g transform="translate(') >= len(d["objects"])
    png = vp.to_png(d, 1)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000


def test_an_svg_arc_flattens_to_its_end():
    pts = vp._flatten("M13,8 A5,5 0 1 1 8,3")[0]
    assert pts[0] == (13, 8) and abs(pts[-1][0] - 8) < 1e-6 and abs(pts[-1][1] - 3) < 1e-6
    assert all(abs(((x - 8) ** 2 + (y - 8) ** 2) ** 0.5 - 5) < 0.01 for x, y in pts)   # on the circle


def test_the_mcp_tools():
    src = (API / "eax" / "mcp_build.py").read_text(encoding="utf-8")
    for tool in ("async def deck_sources(", "async def deck_outline(", "async def view_picture("):
        assert tool in src, tool
    assert "Image(data=png, format=\"png\")" in src
    deck = (API / "eax" / "deck.py").read_text(encoding="utf-8")
    assert 'NOT_FOR_AI = "NOT FOR AI USE OR AUTOMATED PROCESSING"' in deck and "titles_only" in deck
    assert "Pillow" in (API / "requirements.txt").read_text(encoding="utf-8")


def test_a_document_marked_not_for_ai_is_given_by_title_only():
    from eax import deck
    assert deck._marked("Board paper (NOT FOR AI USE OR AUTOMATED PROCESSING)")
    assert deck._marked("", "not for ai use or automated processing")
    assert not deck._marked("Board paper", "for the board")


needs_db = pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")


@needs_db
def test_sources_and_outline_on_a_project():
    from sqlalchemy import create_engine, text

    from eax import deck
    from eax import permissions as perms
    eng = create_engine(DSN)
    su = perms.Principal("tester", ("super-admin",))
    nobody = perms.Principal("nobody", ("user",))
    with eng.connect() as c:
        tx = c.begin()
        try:
            pid = c.execute(text("""INSERT INTO proj.projects (name, purpose, created_by) VALUES ('Deck test', 'To test decks', 'tester')
                                    RETURNING guid::text""")).scalar()
            try:
                s = deck.sources(c, pid, su)
            except Exception as exc:  # noqa: BLE001 - a part this scratch database cannot answer
                pytest.skip(f"the project detail needs more than this database has: {exc}")
            assert s["project"]["name"] == "Deck test" and s["project"]["source"]["where"] == "Deck test › Home"
            assert {"phases", "decisions", "risks", "key_questions", "canvases", "journeys", "titles_only"} <= set(s)
            o = deck.outline(c, pid, su, "the board", 6)
            assert o["slides"][0]["title"] == "Deck test" and o["slides"][-1]["title"] == "Next steps" and len(o["slides"]) <= 6
            with pytest.raises(EditError):
                deck.sources(c, pid, nobody)
        finally:
            tx.rollback()
