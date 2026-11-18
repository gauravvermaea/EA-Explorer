"""The 24 printed guides (Release 7, D783; the owner, 18 Nov 2026, 19:11: "Please make pdf's professional with cover,
purpose, TOC ... as seperate pdf documents from the content we have created"): the list is whole, every guide says who
it is for and what it is for, and everything each one is made of is there, so `eax site pdfs` cannot print half a guide.
Printing itself needs Chromium (eax site pdfs, in the test runner); these tests need only the repository."""

from __future__ import annotations

import html
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("build_manuals", REPO / "tools/build_manuals.py")
M = importlib.util.module_from_spec(spec)
sys.modules["build_manuals"] = M
spec.loader.exec_module(M)


def guides() -> list[dict]:
    return json.loads((REPO / "docs/manuals/manuals.json").read_text(encoding="utf-8"))["manuals"]


def test_twenty_four_guides_each_with_its_purpose_and_reader():
    specs = guides()
    assert len(specs) == 25                                  # the 25th: the error code guide (D790)
    assert [s["id"].split("-")[0] for s in specs] == [f"{n:02d}" for n in range(1, 26)]
    for s in specs:
        assert s["title"] and len(s["purpose"]) > 60 and s["audience"] and s["chapters"], s["id"]
        assert all(ch["title"] and ch["sources"] for ch in s["chapters"]), s["id"]


def test_everything_a_guide_is_made_of_is_there():
    names = M.titles()
    for s in guides():
        g = M.Guide(s, names)
        assert not g.problems, g.problems
        assert sum(len(ch["sections"]) for ch in g.chapters) >= 3, s["id"]


def test_notes_for_the_builders_are_left_out_of_the_print():
    out = M.for_print("Starts in two tiers (D255). Deploy is `eax deploy` (phase 36, [deployment.md](deployment.md)): "
                      "a pipeline (R6.6-J1). The core (sign-in, the database). See [[data-quality|quality]].\n\n"
                      "## Related\n\n- [x](y.md)\n\n## Next\n\nmore", {})
    assert "D255" not in out and "phase 36" not in out and "R6.6" not in out and "deployment.md" not in out
    assert "(sign-in, the database)" in out and "See quality." in out
    assert "## Related" not in out and "## Next" in out


def test_the_contents_get_page_numbers_and_the_pictures_their_place():
    s = next(x for x in guides() if x["id"] == "14-emergency")
    g = M.Guide(s, M.titles())
    first = g.body_html(None)
    assert "zzqm c1 zzqm" in first and "zzqm c1s1 zzqm" in first      # the markers the first printing is read for
    second = g.body_html({"c1": 3, "c1s1": 3})
    assert '<span class="n">3</span>' in second
    assert "About this guide" in first and "Contents" in first and html.escape(s["purpose"]) in first
    assert "Guide 14 of 25" in g.cover_html()


def test_the_command_reference_comes_from_the_help():
    md = M.help_markdown(commands=["jenkins"])
    assert "### eax jenkins" in md and "`eax jenkins [up|down|status" in md and "{eax}" not in md
    assert "### eax up" not in md
