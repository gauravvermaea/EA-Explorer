"""Coverage as pictures (R3.10): the run's files, the trend, the four charts, the summary line and where they are shown."""

from __future__ import annotations

import json
from pathlib import Path

from eax.testing import coverage_view as cv

REPO = Path(__file__).resolve().parents[3]
COV = {"on": True, "percent": 72.4, "run": 724, "lines": 1000, "goal": 90.0, "before": 70.1, "scope": "full api",
       "areas": [{"area": "core", "percent": 91.0, "run": 91, "lines": 100}, {"area": "api", "percent": 60.5, "run": 60, "lines": 99},
                 {"area": "<b>odd</b>", "percent": 10.0, "run": 1, "lines": 10}]}
NEG = {"bad JSON": {"passed": 40, "warning": 1, "failed": 2}, "unknown id": {"passed": 10, "warning": 0, "failed": 0},
       "too long": {"passed": 0, "warning": 0, "failed": 0}}


def reader_of(files: dict[tuple[str, str], object]):
    def read(folder, name):
        v = files.get((folder, name))
        return None if v is None else v if isinstance(v, bytes) else json.dumps(v).encode()
    return read


def test_run_files_reads_both_and_tolerates_missing_or_broken():
    read = reader_of({("r1", "coverage.json"): COV, ("r1", "negative.json"): b"{broken", ("r2", "negative.json"): [1, 2]})
    assert cv.run_files("r1", read) == {"coverage": COV, "negative": None, "screens": None}
    assert cv.run_files("r2", read) == {"coverage": None, "negative": None, "screens": None}   # a list is not a negative.json
    assert cv.run_files("", read) == {"coverage": None, "negative": None, "screens": None}


def test_trend_oldest_first_same_kind_only_and_limited():
    runs = [{"id": i, "folder": f"r{i}", "finished_at": f"t{i}"} for i in range(9, 0, -1)]     # newest first
    files = {(f"r{i}", "coverage.json"): {"percent": 50 + i, "scope": "full api" if i % 2 else "smoke"} for i in range(1, 9)}
    read = reader_of(files)
    pts = cv.trend(runs, read, scope="full api")
    assert [p["run"] for p in pts] == [1, 3, 5, 7] and pts[-1]["percent"] == 57.0 and pts[0]["goal"] == 85.0
    assert [p["run"] for p in cv.trend(runs, read, scope="full api", limit=2)] == [5, 7]
    assert len(cv.trend(runs, read)) == 8
    assert cv.trend([{"id": 1, "folder": ""}], read) == []


def test_colour_by_distance_from_the_goal():
    assert cv.colour(85) == cv.GOOD and cv.colour(75) == cv.NEAR and cv.colour(69.9) == cv.LOW     # goal 85% (D934)


def test_negative_totals():
    assert cv.negative_totals(NEG) == {"passed": 50, "warning": 1, "failed": 2}
    assert cv.negative_totals(None) == {"passed": 0, "warning": 0, "failed": 0}


def test_gauge_shows_the_share_and_the_goal():
    svg = cv.gauge_svg(80.5, 90)
    assert svg.startswith("<svg") and "80.5%" in svg and "goal 90%" in svg and cv.LOW not in svg and cv.NEAR in svg
    assert cv.LOW in cv.gauge_svg(72.4, 90) and cv.GOOD in cv.gauge_svg(95, 90)
    assert "stroke-linecap" in cv.gauge_svg(0)              # nothing run: the empty ring only
    assert cv.gauge_svg(0).count("<path") == 1


def test_areas_worst_first_and_names_escaped():
    svg = cv.areas_svg(COV["areas"])
    assert svg.index("&lt;b&gt;odd") < svg.index(">api<") < svg.index(">core<")
    assert "<b>odd" not in svg and "stroke-dasharray" in svg
    assert cv.areas_svg([]) == ""


def test_trend_line_points_and_goal():
    pts = [{"run": 3, "percent": 60.0}, {"run": 5, "percent": 70.0}, {"run": 8, "percent": 92.0}]
    svg = cv.trend_svg(pts)
    assert svg.count("<circle") == 3 and "<polyline" in svg and "run 3" in svg and "run 8" in svg
    assert "<polyline" not in cv.trend_svg(pts[:1]) and cv.trend_svg([]) == ""


def test_negative_stacked_bars_skip_empty_kinds():
    svg = cv.negative_svg(NEG)
    assert "bad JSON: 40 passed" in svg and "bad JSON: 2 failed" in svg and "too long" not in svg
    assert ">43<" in svg and cv.negative_svg({}) == ""


def test_charts_and_summary_line():
    files = {"coverage": COV, "negative": NEG}
    ch = cv.charts(files, [{"run": 1, "percent": 70.1}, {"run": 2, "percent": 72.4}])
    assert all(ch[k] for k in ("gauge", "areas", "trend", "negative"))
    line = cv.summary_line(files)
    assert "Coverage 72.4% of the API's lines (goal 90%, was 70.1%)" in line
    assert "least covered: <b>odd</b> 10%" in line and "negative tests 53: 50 passed, 1 warnings, 2 failed" in line
    assert cv.summary_line({}) == "" and cv.charts({}) == {"overall": "", "rings": "", "screens": "", "gauge": "", "areas": "", "trend": "", "negative": ""}


def test_html_section_with_and_without():
    assert "kept no code coverage" in cv.html_section({})
    out = cv.html_section({"coverage": COV, "negative": NEG})
    assert out.count("<figure>") == 4 and "Negative tests by kind" in out and "&lt;b&gt;odd" in out   # the ring too (D824)


class _Conn:
    pass


def _detail():
    t = {"passed": 1, "failed": 0, "warning": 0, "skipped": 0}
    hs = {"health": "Healthy", "reason": "ok", "suites": {"api": t}, "critical": t, "non_critical": t,
          "security": {"failed": 0, "warning": 0}}
    run = {"id": 7, "state": "passed", "level": "full", "suites": ["api"], "role": "", "area": "", "folder": "f7",
           "started_by": "me", "trigger": "eax", "started_at": "now", "queued_at": "now", "finished_at": "later",
           "version": "3.0.0", "message": "", "journeys": [], "pages_only": False, "watch": False}
    return {"run": run, "results": [{"id": 1, "suite": "api", "name": "x", "outcome": "passed", "detail": "", "request": "",
                                     "response": "", "browser": "", "video": "", "duration_ms": 1}], "tally": t, "health": hs}


def test_the_reports_carry_the_charts(monkeypatch):
    from eax.testing import report, store
    monkeypatch.setattr(store, "run_detail", lambda conn, rid, *a: _detail())
    monkeypatch.setattr(report, "_shots", lambda conn, rid: {})
    files = {"coverage": COV, "negative": NEG}
    page = report.to_html(_Conn(), 7, files, [{"run": 7, "percent": 72.4, "goal": 90.0}])
    assert "<h2>Code coverage</h2>" in page and "Share of the API&#x27;s lines run" not in page
    assert "Share of the API's lines run" in page and "72.4%" in page
    assert "kept no code coverage" in report.to_html(_Conn(), 7)
    import io

    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(report.to_xlsx(_Conn(), 7, files, [{"run": 7, "percent": 72.4, "goal": 90.0}])))
    ws = wb["Code coverage"]
    assert ws["B1"].value == 72.4 and len(ws._charts) == 2
    assert "Code coverage" not in load_workbook(io.BytesIO(report.to_xlsx(_Conn(), 7))).sheetnames


def test_eax_test_prints_the_coverage_line():
    from eax.testing import run
    text = run.summary_text(_detail(), "Coverage 72.4% of the API's lines (goal 90%)")
    assert "Coverage 72.4% of the API's lines (goal 90%)" in text
    assert "Coverage" not in run.summary_text(_detail())


def test_the_run_reads_its_own_folder(tmp_path, monkeypatch):
    from eax.testing import run, store
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    for name, pct in (("f6", 70.1), ("f7", 72.4)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "coverage.json").write_text(json.dumps({**COV, "percent": pct}))
    (tmp_path / "f7" / "negative.json").write_text(json.dumps(NEG))
    monkeypatch.setattr(store, "runs", lambda conn, n: [{"id": 7, "folder": "f7"}, {"id": 6, "folder": "f6"}])

    class R:
        folder = "f7"
    files, points = run.coverage_for(None, R())
    assert files["negative"] == NEG and [p["run"] for p in points] == [6, 7]
    assert run.local_reader(tmp_path)("f7", "missing.json") is None


def test_the_api_reads_run_files_inside_work_tests_only(tmp_path, monkeypatch):
    import pytest
    flask = pytest.importorskip("flask")
    if not hasattr(flask, "Response"):
        pytest.skip("needs the real Flask")
    from eax import filestore
    from eax.api import platform_tests as pt
    monkeypatch.setattr(pt, "WORK_TESTS", tmp_path / "tests")
    monkeypatch.setattr(filestore, "in_database", lambda: False)
    (tmp_path / "tests" / "f1").mkdir(parents=True)
    (tmp_path / "tests" / "f1" / "coverage.json").write_text("{}")
    (tmp_path / "secret.txt").write_text("no")
    assert pt._run_file("f1", "coverage.json") == b"{}"
    assert pt._run_file("f1", "../../secret.txt") is None
    assert pt._run_file("f1", "nothing.json") is None


def test_wired_into_the_page_the_endpoint_and_the_reports():
    api = (REPO / "services/api/eax/api/platform_tests.py").read_text()
    assert '@blp.route("/tests/coverage")' in api and 'd["coverage"] = {' in api
    assert "report.to_html(conn, run_id, files, points)" in api and "report.to_xlsx(conn, run_id, files, points)" in api
    page = (REPO / "services/web/src/TestRuns.jsx").read_text()
    assert 'import CoverageCharts from "./CoverageCharts"' in page and "<CoverageCharts c={d?.coverage} />" in page
    comp = (REPO / "services/web/src/CoverageCharts.jsx").read_text()
    for k in ("gauge", "areas", "trend", "negative"):
        assert f'["{k}",' in comp


# ---------------------------------------------------------------- the ring (D824; owner, 21 Nov 2026, 13:18: "Can code
# coverage of a full test be shown in a ring pie chart please? Only for our code")
def test_the_ring_shows_the_share_the_lines_and_the_goal():
    svg = cv.ring_svg(41.6, 26_960, 64_846, 190, "Our code", 90)
    assert svg.startswith("<svg") and ">41.6%</text>" in svg and "26,960 of 64,846 lines" in svg
    assert cv.LOW in svg and "stroke-dasharray" in svg and "<line " in svg             # the goal's tick
    assert cv.GOOD in cv.ring_svg(95, goal=90) and cv.NEAR in cv.ring_svg(80, goal=90)
    assert "stroke-dasharray" not in cv.ring_svg(0)                                    # nothing run: the grey ring only
    assert ">100%</text>" in cv.ring_svg(130)                                          # never more than the whole ring


def test_our_code_ring_and_when_joined_one_for_each_measurement():
    joined = {"percent": 63.0, "run": 40_853, "lines": 64_846, "live": 41.1, "unit": 42.6, "goal": 90.0}
    out = cv.rings_svg(joined)
    assert out.count("<svg") == 3 and "Our code, every line (this run and the unit tests together)" in out
    assert "This run alone" in out and "The unit tests alone (eax dev check)" in out and ">63%</text>" in out
    alone = cv.rings_svg({"percent": 26.4, "run": 14_920, "lines": 56_511})
    assert alone.count("<svg") == 1 and "together" not in alone
    assert cv.rings_svg({}) == ""


def test_the_ring_comes_first_in_the_report_and_on_the_page(monkeypatch):
    ch = cv.charts({"coverage": COV, "negative": NEG})
    assert list(ch)[:2] == ["overall", "rings"] and ch["rings"] and ch["overall"] == ""   # no screens: no overall ring
    page = cv.html_section({"coverage": COV})
    assert page.index("The API's lines run, against the goal") < page.index("Share of the API")
    comp = (REPO / "services/web/src/CoverageCharts.jsx").read_text()
    assert comp.index('["rings",') < comp.index('["gauge",')



# the goal's measure (eax/api) and the screens on the run's coverage pictures (owner, 25 Nov 2026, 16:14: "this one
# doesnt show the UI")
SCR = {"screens": 211, "covered": 163, "percent": 77.3, "controls": 2519, "controls_used": 253, "controls_percent": 10.0,
       "bar": 90.0}


def test_the_rings_lead_with_the_api_and_the_screens_have_theirs():
    c = {**COV, "goal_percent": 83.3, "goal_run": 9702, "goal_lines": 11649, "goal_left_out_lines": 711, "jobs_percent": 53.7}
    ch = cv.charts({"coverage": c, "screens": SCR})
    assert "The API (eax/api), the goal&#x27;s measure" in ch["rings"] or "The API (eax/api), the goal's measure" in ch["rings"]
    assert "711 lines left out" in ch["rings"] and "The background jobs" in ch["rings"] and "All the server" in ch["rings"]
    assert "77.3%" in ch["screens"] and "163 of 211 screens" in ch["screens"]
    line = cv.summary_line({"coverage": c, "screens": SCR})
    assert line.startswith("Overall 80.3% (the API and the screens counted equally; bar 85%: short by 4.7 points); ")
    assert ("; The API 83.3% of its 11,649 lines (goal 90%: short by 6.7 points: about 783 more lines to run), "
            "background jobs 53.7%") in line
    assert "the screens 77.3% covered by journeys (163 of 211; bar 90%: short by 12.7 points" in line
    page = cv.html_section({"coverage": c, "screens": SCR})
    assert page.index("The API's lines run") < page.index("The screens covered by journeys, against the bar")
    comp = (REPO / "services/web/src/CoverageCharts.jsx").read_text()
    assert '["screens", "The screens covered by journeys, against the bar"]' in comp
    assert cv.screens_svg(None) == "" and cv.screens_svg({"screens": 0}) == ""


def test_the_coverage_page_says_the_goals_figure_above_the_areas():
    from eax.testing import run as R
    page = R.coverage_html({"percent": 63.8, "run": 1, "lines": 2, "goal_percent": 83.3, "goal_run": 9702,
                            "goal_lines": 11649, "goal_left_out_lines": 711, "areas": [], "files": []})
    assert "The API (eax/api), the goal's measure: 83.3%" in page and "711 lines left out" in page
    assert page.index("83.3%") < page.index("All the server's code: 63.8%")
