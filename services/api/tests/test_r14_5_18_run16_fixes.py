"""Release 14.5, the fixes after run 16 (26 Nov 2026, 04:26; owner: "test done 8 failed"). Each failure the testing code
caused, held here so it does not come back. (The two package failures of the run's dev check are in test_r14_5_17.)"""

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax.testing import api_writes as A  # noqa: E402
from eax.testing import ui_flows as U  # noqa: E402

M, P, TAG = "11111111-1111-1111-1111-111111111111", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "self_test_sid"
JOURNEYS = {j["name"]: j for j in U.PROJECT_JOURNEYS + U.AREA_JOURNEYS}
WEB = API.parent / "web" / "src"


def _steps(name: str) -> list[dict]:
    return JOURNEYS[name]["steps"]


def test_a_load_may_answer_202_with_its_preview_task():
    """The route answers 202: the load is kept and previewed in the background (api/sheets.py, Loads.post)."""
    load = {x["what"]: x for x in A.model_extras(M, None, "sid", TAG)}["load an Excel file"]
    assert 202 in load["ok"] and load["save_from"] == "load.id"
    assert "@blp.response(202, Free)" in (API / "eax/api/sheets.py").read_text(encoding="utf-8")


def test_an_upload_waits_longer_than_the_api_waits_on_documents():
    """Run 16: the project's upload answered "no answer" (599) after 120 s; the API itself waits up to 300 s."""
    assert A.UPLOAD_WAIT > 300
    assert A.upload.__defaults__[-1] == A.UPLOAD_WAIT
    assert "timeout=300" in (API / "eax/mayan.py").read_text(encoding="utf-8")


def test_the_library_is_opened_without_waiting_for_a_placeholder():
    """"Search the library" is only the search box's placeholder and label: waited for as text, it timed out at 60 s."""
    name = "project tabs that show: the report's CSV, the library's search, a phase opened"
    opened = [s for s in _steps(name) if s.get("open") == "#/projects/{p}/library"]
    assert opened and "expect" not in opened[0]
    assert any(s.get("fill") == "Search the library" for s in _steps(name))
    for f in ("TemplateBrowser.jsx", "ReferenceLibrary.jsx"):
        assert 'placeholder="Search the library"' in (WEB / f).read_text(encoding="utf-8")


def test_the_charter_is_changed_by_the_super_admin():
    """The charter's ✎ Change is for the Project Admin and the Lead Architect: the Architect never saw it."""
    more = _steps("project tabs that show more: choose, open a change and cancel, a phase, download")
    assert not any(s.get("open") == "#/projects/{p}/charter" for s in more)
    j = JOURNEYS["project tabs that show the charter: a section opened for a change and cancelled"]
    assert j["roles"] == ["super-admin"] and {"click": "✎ Change"} in j["steps"]
    assert '"may_edit": _may(conn, p, user, "admin")' in (API / "eax/governance.py").read_text(encoding="utf-8")


def test_the_models_step_is_opened_on_a_kind_of_project():
    """#/projects/new is the gallery of kinds; the wizard, with its "+ Select existing models", is a kind's."""
    steps = [s for j in U.PROJECT_JOURNEYS + U.AREA_JOURNEYS for s in j["steps"]]
    assert not any(s.get("open") == "#/projects/new" for s in steps)
    i = next(k for k, s in enumerate(steps) if s.get("open") == "#/projects/new?template=blank")
    assert steps[i + 1] == {"click": "+ Select existing models"}
    src = (WEB / "Projects.jsx").read_text(encoding="utf-8")
    assert 'href="#/projects/new?template=blank"' in src and "+ Select existing models" in src


class _Page:
    def __init__(self, said):
        self.said = said

    def evaluate(self, _js):
        return self.said


def test_a_page_with_no_heading_says_its_first_words_or_that_it_is_blank():
    """Run 16: the organisation tab's failure said only where it was; now it says what was on it."""
    base = {"at": "#/projects/x/organisation", "h1": [], "status": [], "dialog": "", "dialog_said": []}
    assert 'its first words "Loading..."' in U._page_says(_Page({**base, "text": "Loading..."}))
    assert "a blank page" in U._page_says(_Page({**base, "text": ""}))
    said = U._page_says(_Page({**base, "h1": ["Project"], "text": "Project"}))
    assert "first words" not in said and "blank" not in said


def test_the_project_library_page_is_acted_on_and_the_setting_pages_are_not():
    """Run 16: the project library's page opened and a library opened; the system, application, scaling, secrets and
    console pages are not, as each of their controls changes a setting, restarts, rotates or opens a shell."""
    j = next(x for x in U.AREA_JOURNEYS if x["name"].startswith("the project content library"))
    assert j["steps"] == [{"open": "#/project-admin/library"}, {"click": "Open", "exact": True}]
    opened = {s.get("open") for x in U.AREA_JOURNEYS + U.PROJECT_JOURNEYS for s in x["steps"]}
    assert not opened & {"#/admin/system", "#/admin/secrets", "#/admin/scaling", "#/admin/commands/console"}


PLATFORM = {s["what"]: s for s in A.platform_writes(M, None, "sid", TAG)}


def test_the_database_upkeep_is_looked_at_and_planned_only():
    """More cases toward 90% (owner, 26 Nov 2026): the upkeep's reads and plans; no compact or stop is ever confirmed."""
    ups = [s for s in PLATFORM.values() if s["area"] == "database upkeep"]
    paths = {s["path"].rsplit("/", 1)[-1] for s in ups}
    assert {"locks", "check", "tidy", "compact-preview", "stop-preview"} <= paths
    assert not paths & {"compact", "stop", "clear"}
    assert PLATFORM["what a tidy would do"]["body"] == {"dry_run": True}
    assert PLATFORM["a compact preview of a table that is not there"]["ok"] == {400}
    assert PLATFORM["a stop preview of a session that is not there"]["ok"] == {400}
    assert any(s.get("refused") and s["who"] == "architect" for s in ups)


def test_a_saved_estimate_is_read_only_when_there_is_one():
    saved = PLATFORM["the saved sizing estimates"]
    assert saved["optional"] and saved["save_from"] == "saved.0.id" and saved["method"] == "get"
    for fmt in ("json", "xlsx", "override"):
        assert any(s["path"] == f"/api/v1/admin/sizing/{{sizing}}/{fmt}" for s in PLATFORM.values()), fmt
    assert not any(s["path"] == "/api/v1/admin/sizing" and (s.get("body") or {}).get("save") for s in PLATFORM.values())


def test_this_run_is_read_as_it_stands_and_watched():
    assert PLATFORM["this run as it stands"]["path"].startswith("/api/v1/admin/tests/{thisrun}?")
    assert PLATFORM["this run, watched as it happens"]["path"].startswith("/api/v1/admin/tests/{thisrun}/live")
    assert PLATFORM["a screenshot this run does not have"]["ok"] == {404}


def test_a_request_is_raised_worked_and_cancelled_by_the_one_who_asked():
    desk = [s for s in A.platform_writes(M, None, "sid", TAG) if s["area"] == "service desk"]
    what = [s["what"] for s in desk]
    assert what[0] == "raise a request" and what[-1] == "my requests, cancelled ones too"
    raised = desk[0]
    assert raised["who"] == "architect" and raised["body"]["type"] == "other" and raised["body"]["fields"]["what"]
    assert raised["save"] == "ticket" and raised["save_from"] == "id"
    cancel = next(s for s in desk if s["what"] == "cancel it")
    assert cancel["who"] == "architect"                   # only the person who asked cancels (servicedesk.act)
    assert what.index("cancel it") > what.index("the desk sets its priority")
    assert any(s.get("refused") and s["who"] == "report-viewer" for s in desk)
    assert not any(s["method"] == "delete" for s in desk)
    src = (API / "migrations/sql/0082_r5_service_desk.sql").read_text(encoding="utf-8")
    assert "('other', 'Help', 'Something else'" in src and '"name": "what"' in src


def test_the_metamodel_is_read_and_a_framework_move_only_asked_about():
    mm = [s for s in A.model_extras(M, None, "sid", TAG) if s["area"] == "metamodel"]
    assert {s["method"] for s in mm} == {"get"}
    assert any(s["path"].endswith("/metamodel-spec") and s["ok"] == {200} for s in mm)
    bad = [s for s in mm if "framework-preview" in s["path"]]
    assert len(bad) == 2 and all(200 not in s["ok"] for s in bad)    # never a move: what is asked is refused
    assert not any("framework-move" in s["path"] for s in A.model_extras(M, None, "sid", TAG))


def test_the_upkeep_route_is_in_the_goal_now():
    from eax.testing import run
    assert not any(r[1] == "/admin/db-maintenance/<string:what>" for r in run.LEFT_OUT_ROUTES)


def test_the_first_words_are_the_open_tabs_own():
    """Run 17: the organisation tab's failure quoted the app's header; the tab's panel is read first now."""
    src = (API / "eax/testing/ui_flows.py").read_text(encoding="utf-8")
    js = src[src.index("def _page_says"):src.index("parts = [f", src.index("def _page_says"))]
    assert '[".tab-panel", ".wizard-body", "main .page", "main", "#root"]' in js
    assert 'className="tab-panel"' in (WEB / "Projects.jsx").read_text(encoding="utf-8")


class _Health:
    def __init__(self, answer):
        self.answer = answer

    def evaluate(self, _js, *args):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def test_a_failed_step_says_how_fast_the_api_was_answering():
    """Run 17 (D933): nine project tabs failed in twelve minutes while the API timed out; a failure now says whether
    the API was answering just then."""
    assert U._api_answers(_Health(240)) == " · the API answered its health check in 0.2 s"
    assert U._api_answers(_Health(None)) == f" · the API did not answer its health check in {U.API_WAIT_MS // 1000} s"
    assert U._api_answers(_Health(-502)) == " · the API answered its health check with HTTP 502"
    assert U._api_answers(_Health(RuntimeError("page closed"))) == ""
    src = (API / "eax/testing/ui_flows.py").read_text(encoding="utf-8")
    assert '{_api_answers(state.get(\'tab\') or page)}' in src and 'fetch("/api/health"' in src
    assert '@app.get("/api/health")' in (API / "eax/app.py").read_text(encoding="utf-8")


def test_force_it_is_chosen_only_when_there_is_a_version_to_push():
    steps = [s for j in U.AREA_JOURNEYS + U.PROJECT_JOURNEYS for s in j["steps"] if s.get("choose") == "Force it"]
    assert len(steps) == 2 and all(s.get("optional") for s in steps)


class _At:
    def __init__(self, url):
        self.url = url


def test_a_script_error_says_the_page_it_happened_on():
    """Run 18 (D939): "s.map is not a function" on one of a journey's four tabs, which one not said."""
    assert U._script_error(TypeError("s.map is not a function"), _At("https://localhost/#/projects/x/library")) == \
        "script error at #/projects/x/library: s.map is not a function"
    assert U._script_error(TypeError("boom"), _At("about:blank")) == "script error at about:blank: boom"
    src = (API / "eax/testing/ui_flows.py").read_text(encoding="utf-8")
    assert 'errs.append(_script_error(e, pg))' in src


def test_a_choice_is_waited_for_as_a_field_is():
    """Run 18 (D939): the merge page's "Without data" was looked for before the page had drawn it."""
    src = (API / "eax/testing/ui_flows.py").read_text(encoding="utf-8")
    part = src[src.index('elif "choose" in s:'):src.index('elif "fill" in s:')]
    assert "while loc is None and time.time() < end:" in part and "page.wait_for_timeout(300)" in part
