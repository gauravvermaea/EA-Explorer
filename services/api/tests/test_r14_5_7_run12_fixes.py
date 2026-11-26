"""Release 14.5, the fixes after run 12 (25 Nov 2026, 13:42; owner, 16:13: "Please fix the issues"). Each failure of the
run, with what the testing code had wrong, held here so it does not come back."""

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax.testing import api_writes as A  # noqa: E402
from eax.testing import ui_flows as U  # noqa: E402

M, OTHER = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
P = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SID = "e4fa1d33dfd8"
TAG = f"self_test_{SID}"
API_STEPS = {s["what"]: s for s in A.platform_writes(M, OTHER, SID, TAG) + A.project_workspace(P, TAG)}
JOURNEYS = {j["name"]: j for j in U.PROJECT_JOURNEYS + U.AREA_JOURNEYS}


def test_a_post_that_makes_something_may_answer_201():
    for what in ("add a status of the project's own", "add a kind of record", "remove that kind", "comment on it"):
        assert 201 in API_STEPS[what]["ok"], what


def test_a_tag_made_at_once_may_answer_202_with_the_tag():
    assert 202 in API_STEPS["tag the model at once"]["ok"]


def test_a_models_backup_answers_its_task_itself():
    s = API_STEPS["back up the model (in the background)"]
    assert "save_at" not in s and s["save"] == "mbtask" and s["until"]["path"] == "/api/v1/tasks/{mbtask}"
    assert A.ident({"id": "fad06d9d-6daf-4513-b732-f49f22b446d1", "kind": "backup.model", "status": "queued"})


def test_the_logs_name_a_container_and_a_day_kept():
    """Run 13 (25 Nov 2026, 16:48): the read answered 400 without a day; the day is now one the API's logs were kept."""
    files = API_STEPS["the API's kept log files"]
    assert files["path"].endswith("/admin/logs/files?service=api") and files["save_from"] == "files.0.day" and files["optional"]
    read = API_STEPS["read a day of the API's logs"]["path"]
    assert "services=api" in read and "day={logday}" in read


def test_a_failed_task_says_why(monkeypatch):
    """Run 13: "stopped at failed" alone did not say why a task failed; its message is now in the result."""
    monkeypatch.setattr(A, "call", lambda *a, **k: (200, {"status": "failed", "message": "There is no document here."}))
    out = A.wait_for("https://x", "t", {"path": "/api/v1/tasks/{t}", "status": ["done"], "seconds": 1}, {"t": "1"})
    assert out == ("failed", "stopped at failed, expected done: There is no document here.")


def test_a_merge_is_planned_into_the_runs_project_model():
    """Merging is for project models: the run's second model is a child, so it is merged from, never into; and by the
    Super Admin, who reads both (run 14: the first model's Model Admin may not read the second)."""
    s = API_STEPS["plan a merge from the run's second model (in the background; never applied)"]
    assert s["path"] == f"/api/v1/models/{M}/merges" and s["body"] == {"source_model": OTHER} and s["who"] == "super-admin"


def _steps(name):
    return JOURNEYS[name]["steps"]


def test_a_task_keeps_a_status_that_leaves_it_in_the_list():
    st = _steps("project tasks: add one, change its status, delete it")
    assert {"select": "Status of self_test_{sid} task {role}", "option": "Open"} in st


def test_a_placeholder_is_never_waited_for_as_text():
    for name in ("project organisation: add a person, find them, take them out",
                 "project governance: log a decision, open it, take it out"):
        assert "expect" not in _steps(name)[0], name


def test_power_is_chosen_on_the_position_tab():
    st = _steps("project stakeholders: add one, open it, take it out")
    i = st.index({"select": "Power", "option": "High", "within": ".ed-dialog"})
    assert st[i - 1] == {"click": "Position", "exact": True, "within": ".ed-dialog"}


def test_the_status_csv_is_named_by_its_whole_words():
    j = next(j for n, j in JOURNEYS.items() if n.startswith("project tabs that show"))
    assert {"click": "⬇ CSV (opens in Excel)", "exact": True} in j["steps"]       # a click since run 14 (made in the page)
    src = (API / "eax/testing/ui_flows.py").read_text(encoding="utf-8")
    assert '_clickable(root, s["download"], bool(s.get("exact")))' in src
    js = (API.parents[1] / "services/web/src/selfTestDriver.js").read_text(encoding="utf-8")
    assert "clickable(root, s.download, s.exact)" in js


def test_the_mapping_is_a_drop_down_and_the_slow_pages_are_waited_for():
    st = [s for j in U.AREA_JOURNEYS for s in j["steps"]]
    assert {"select": "Map a Keycloak role or a directory group", "option": "Directory group"} in st
    assert {"open": "#/admin/estate/logical", "expect": "Download SVG"} in st
    assert {"open": "#/projects/new?template=blank", "expect": "Kind of project"} in st      # the wizard (run 16)


def test_the_key_question_is_read_back_as_the_tab_reads_it():
    """Run 12: the tab said "Key question added." and listed none; the API reads the project and the questions again."""
    reads = [s for s in A.project_workspace(P, TAG) if s.get("shows") and "what do we decide" in s["shows"]]
    assert [s["path"] for s in reads] == [f"/api/v1/projects/{P}", f"/api/v1/projects/{P}/key-questions"]
    assert all(s["shows"] == f"{TAG} what do we decide?" for s in reads)
    src = (API / "eax/testing/api_writes.py").read_text(encoding="utf-8")
    assert 'if outcome == "passed" and w.get("shows"):' in src


# the measure on the screens (owner, 25 Nov 2026, 16:24: "On the screens can you show the actual measure that you say here")
COV12 = {"percent": 63.8, "goal": 90.0, "api": 83.3, "api_lines": 11649, "api_run": 9702, "jobs": 53.7, "jobs_lines": 1669,
         "jobs_run": 897}
SCR12 = {"screens": 211, "covered": 163, "percent": 77.3, "bar": 90.0, "controls": 2519, "controls_used": 253,
         "controls_percent": 10.0}


def test_how_far_from_the_bar_in_the_owners_words():
    from eax.testing import coverage_view as cv
    sys.path.insert(0, str(API.parents[1]))
    from eaxcli import fullreport as F
    for f in (cv.to_reach, F.to_reach):
        assert f(83.3, 90, 11649, 9702) == "short by 6.7 points: about 783 more lines to run"
        assert f(77.3, 90, 211, 163, "screens") == "short by 12.7 points: about 27 more screens covered"
        assert f(91.0, 90, 100, 91) == "at or over the goal of 90%" and f(95, 90, 10, 9, "screens") == "at or over the bar of 90%"
        assert f(None, 90, 10, 1) == "-"


def test_the_summary_page_and_the_pictures_say_it():
    from eaxcli import fullreport as F

    from eax.testing import coverage_view as cv
    s = {"selftest": {"coverage": COV12, "screens": SCR12}}
    top = F.where_it_stands(s)
    assert "The API 83.3% of 11649 lines, goal 90%: short by 6.7 points: about 783 more lines to run" in top
    assert "the screens 77.3% (163 of 211), bar 90%: short by 12.7 points: about 27 more screens covered" in top
    page = F.page({"finished_at": "x", "steps": [], **s})
    assert "Where it stands" in page and "to reach the goal" in page and "to reach the bar" in page
    c = {"percent": 63.8, "goal": 90.0, "goal_percent": 83.3, "goal_lines": 11649, "goal_run": 9702}
    assert "short by 6.7 points: about 783 more lines to run" in cv.rings_svg(c)
    assert "short by 12.7 points: about 27 more screens covered" in cv.screens_svg(SCR12)
    line = cv.summary_line({"coverage": c, "screens": SCR12})
    assert "about 783 more lines to run" in line and "about 27 more screens covered" in line


def test_the_apps_summary_screen_says_it():
    js = (API.parents[1] / "services/web/src/FullSummary.jsx").read_text(encoding="utf-8")
    for x in ("export function toReach(", '["to reach the goal", toReach(api, goal, cov.api_lines, cov.api_run, "lines")]',
              '["to reach the bar", toReach(scr.percent, scr.bar, scr.screens, scr.covered, "screens")]',
              "<b>Where it stands:</b>", "more ${what === \"screens\" ? \"screens covered\" : \"lines to run\"}",
              "Math.ceil((b * Number(total)) / 100 - Number(done || 0))"):
        assert x in js, x


def test_run_14_fixes():
    """Run 14 (25 Nov 2026, 18:30): the steps that failed for the testing code's own reasons."""
    zip_at = next(i for i, x in enumerate(A.project_workspace(P, TAG)) if x["what"] == "the documents' zip (in the background)")
    before = [x["what"] for x in A.project_workspace(P, TAG)[:zip_at]]
    assert "upload a file to the project" in before                 # a document with a file to zip
    up = next(x for x in A.project_workspace(P, TAG) if x["what"] == "upload a file to the project")
    assert up["data"] == "deliveries/good.xlsx" and up["save_from"] == "uploads.0.id"
    starters = {x["what"]: x for x in A.job_starters(M, OTHER, P, TAG)}
    assert all(f"model={M}" in x["path"] for x in starters.values() if "change-log/export" in x["path"])   # the run's model only
    decide = starters["decide no close names: refused in words (in the background)"]
    assert decide["until"]["said"] == "Confirm or reject at least one suggestion."
    assert '{"click": "⬇ CSV (opens in Excel)", "exact": True}' in (API / "eax/testing/ui_flows.py").read_text(encoding="utf-8")
    src = (API / "eax/testing/ui_journeys.py").read_text(encoding="utf-8")
    assert src.count('grant_permissions(["clipboard-read", "clipboard-write"], origin=base)') == 2


def test_a_task_that_must_fail_says_why(monkeypatch):
    until = {"path": "/api/v1/tasks/{t}", "status": ["failed"], "seconds": 1, "said": "Confirm or reject"}
    monkeypatch.setattr(A, "call", lambda *a, **k: (200, {"status": "failed", "message": "Confirm or reject at least one."}))
    assert A.wait_for("https://x", "t", until, {"t": "1"})[0] == "passed"
    monkeypatch.setattr(A, "call", lambda *a, **k: (200, {"status": "failed", "message": "Something else broke."}))
    assert A.wait_for("https://x", "t", until, {"t": "1"})[0] == "failed"


def test_run_15_fixes():
    """Run 15 (25 Nov 2026, 22:09): the testing code's own failures, and the new steps."""
    ws = {x["what"]: x for x in A.project_workspace(P, TAG)}
    folder = {x["what"]: x for x in A.project_extras(P, TAG)}
    assert folder["take the folder away"]["ok"] == {200, 201}
    assert ws["replace it with a second version"]["data"] == "uploads/document-v2.pdf"
    mx = {x["what"]: x for x in A.model_extras(M, None, "sid", TAG)}
    load = mx["load an Excel file"]
    assert load["data"] == "deliveries/good.xlsx" and load["save_from"] == "load.id"
    assert mx["its preview"]["until"]["status"] == ["previewed"]
    order = [x["what"] for x in A.model_extras(M, None, "sid", TAG)]
    assert order.index("delete the load before it is added") > order.index("map its columns as they are")
    assert not any("/add" in x["path"] for x in mx.values() if "loads" in x["path"])        # never added to the model
    src = (API / "eax/testing/ui_flows.py").read_text(encoding="utf-8")
    assert '{"click": "+ Select existing models"}' in src and '{"click": "🔗 Add a link", "optional": True}' in src
