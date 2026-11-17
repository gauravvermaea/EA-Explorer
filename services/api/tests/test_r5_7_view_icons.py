"""R5.7-V1, a bug (owner, 16 Nov 2026): the views EA Explorer draws on its screens showed no ArchiMate icons on the
boxes, though draw.io showed them. Now the graph's nodes carry the type's notation, and the screen draws the
ArchiMate box (square, rounded or cut corners) and the icon in its corner for every notation eax/notation.py knows.
Each check fails without the fix."""
from __future__ import annotations

import re
from pathlib import Path

from eax import notation
from eax.api.schemas import GraphNodeOut

API = Path(__file__).resolve().parents[1]
WEB = API.parent / "web" / "src"
ICONS = (WEB / "archimateIcons.jsx").read_text(encoding="utf-8")
GRAPH = (WEB / "EntityGraph.jsx").read_text(encoding="utf-8")


def _glyph_names() -> set[str]:
    block = ICONS.split("export const GLYPHS = {", 1)[1].split("\n};", 1)[0]
    return set(re.findall(r"^\s{2}([A-Za-z]+):", block, re.M))


def _set(name: str) -> set[str]:
    body = re.search(rf"const {name} = new Set\(\[(.*?)\]\)", ICONS, re.S).group(1)
    return set(re.findall(r'"([A-Za-z]+)"', body))


def test_every_archimate_element_and_the_junction_has_an_icon():
    assert _glyph_names() == set(notation.ELEMENTS) | {"Junction"}


def test_the_box_corners_follow_the_archimate_families():
    rounded = {k for k, v in notation.ELEMENTS.items() if v[1] == "rounded"}
    cut = {k for k, v in notation.ELEMENTS.items() if v[1] == "oct"}
    assert _set("ROUNDED") == rounded
    assert _set("CUT") == cut


def test_the_view_drawing_uses_the_box_and_the_icon():
    assert 'from "./archimateIcons"' in GRAPH
    assert "<BoxShape notation={n.notation}" in GRAPH
    assert "<Glyph notation={n.notation}" in GRAPH
    # the old plain box is gone from the node drawing
    assert 'rx="6" fill={`#${n.colour' not in GRAPH


def test_the_graph_nodes_carry_the_notation():
    assert "notation" in GraphNodeOut().fields
    out = GraphNodeOut().dump({"id": None, "name": "Pay", "notation": "Process"})
    assert out["notation"] == "Process"
    repo = (API / "eax" / "repository.py").read_text(encoding="utf-8")
    # both graph queries (the neighbourhood and the paths) select it
    assert repo.count("l.sort_order AS domain_order, et.notation") == 2
