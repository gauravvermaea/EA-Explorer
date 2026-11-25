"""The overall coverage ring (owner, 25 Nov 2026, 16:34: "In the coverage while you show code and screen coverage, can
there a an overall coverage ring too, these two can be under it"): the API's figure and the screens', counted equally,
as one ring with the two under it, on the summary page (eaxcli/fullreport), the self-test's coverage pictures
(coverage_view) and the app's Summary screen (FullSummary.jsx, CoverageCharts.jsx). Checked with run 12's real figures."""

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))
sys.path.insert(0, str(ROOT))

from eaxcli import fullreport as F  # noqa: E402

from eax.testing import coverage_view as cv  # noqa: E402

COV12 = {"percent": 63.8, "goal": 90.0, "api": 83.3, "api_lines": 11649, "api_run": 9702}
SCR12 = {"screens": 211, "covered": 163, "percent": 77.3, "bar": 90.0, "controls": 2519, "controls_used": 253,
         "controls_percent": 10.0}
C12 = {"percent": 63.8, "goal": 90.0, "goal_percent": 83.3, "goal_lines": 11649, "goal_run": 9702}


def test_the_overall_figure_counts_the_two_equally():
    assert F.overall(COV12, SCR12) == 80.3                      # (83.3 + 77.3) / 2
    assert cv.overall(C12, SCR12) == 80.3
    assert F.overall(COV12, {}) == 83.3 and F.overall({}, SCR12) == 77.3 and F.overall({}, {}) is None
    assert cv.overall(C12, None) == 83.3 and cv.overall({}, None) is None
    assert cv.overall({}, {"screens": 0, "percent": 0}) is None   # no screens counted: no figure


def test_the_summary_page_shows_one_ring_over_the_two():
    s = {"finished_at": "x", "steps": [], "selftest": {"coverage": COV12, "screens": SCR12}}
    assert "Overall 80.3% (the API and the screens counted equally), bar 90%: short by 9.7 points" in F.where_it_stands(s)
    card = next(c for c in F.cards(s) if "Overall coverage" in c)
    assert "card wide overall" in card and card.count("<svg") == 3
    big, api, screens = card.index("overall:"), card.index("the API:"), card.index("the screens:")
    assert big < api < screens                                   # the overall ring first, the two under it
    cards = F.cards(s)
    assert cards.index(card) < next(i for i, c in enumerate(cards) if "<h2>Code coverage</h2>" in c)
    assert ".pair{" in F.page(s)
    only_api = {"finished_at": "x", "steps": [], "selftest": {"coverage": COV12}}
    assert not any("Overall coverage" in c for c in F.cards(only_api)) and "Overall" not in F.where_it_stands(only_api)


def test_the_coverage_pictures_put_it_first():
    ch = cv.charts({"coverage": C12, "screens": SCR12})
    assert list(ch)[0] == "overall" and ch["overall"].count("<svg") == 3
    assert "short by 9.7 points" in ch["overall"] and ch["overall"].index("Overall") < ch["overall"].index("The API")
    assert cv.charts({"coverage": C12})["overall"] == ""
    assert cv.summary_line({"coverage": C12, "screens": SCR12}).startswith("Overall 80.3% (the API and the screens")
    sec = cv.html_section({"coverage": C12, "screens": SCR12})
    assert sec.index("Overall: the API and the screens") < sec.index("The API's lines run, against the goal")


def test_the_apps_screens_show_it():
    js = (ROOT / "services/web/src/FullSummary.jsx").read_text(encoding="utf-8")
    for x in ("export function overall(", "<h3>Overall coverage</h3>", 'label="overall"', 'className="full-pair"',
              "Overall ${whole}% (the API and the screens counted equally), bar 90%"):
        assert x in js, x
    assert js.index("<h3>Overall coverage</h3>") < js.index("<h3>Code coverage</h3>")
    css = (ROOT / "services/web/src/styles.css").read_text(encoding="utf-8")
    assert ".full-pair {" in css and ".full-overall {" in css
    charts = (ROOT / "services/web/src/CoverageCharts.jsx").read_text(encoding="utf-8")
    assert charts.index('["overall"') < charts.index('["rings"')
