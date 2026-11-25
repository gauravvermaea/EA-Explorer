"""Release 14.5, R14.5.1 (D924): the screens' coverage measured by the journeys, not by code (owner, 25 Nov 2026,
09:39 to 09:45). A screen is covered when a journey acts on it, or when it is read only and opens; each screen's
controls and how many the journeys used are shown; risky controls are left out and listed."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API = REPO / "services/api"
sys.path.insert(0, str(API))

from eax.testing import screen_coverage as S  # noqa: E402


def test_one_name_for_a_kind_of_screen():
    assert S.screen("#/projects/6e71cb6a-f3ca-4ebf-8266-407c3a6ac9ca/phases?phase=B") == "#/projects/{id}/phases"
    assert S.screen("#/metamodel/{m}/views") == "#/metamodel/{id}/views"
    assert S.screen("#/surveys/{$survey}/answer") == "#/surveys/{id}/answer"
    assert S.screen("#/admin/jobs/42") == "#/admin/jobs/{id}"
    assert S.screen("#/") == "#" and S.screen("") == "#"


def test_the_risky_controls_are_known_by_their_words():
    for w in ("Stop", "Restart all", "Restore this backup", "Delete the model", "Switch to certificates", "Update now",
              "Roll back", "Reset the password", "Clean up"):
        assert S.risky(w), w
    for w in ("Save", "Add", "Mark the phase complete", "Change…", "Status", "Search", "Report"):
        assert not S.risky(w), w


def test_which_steps_act():
    assert S.acted({"click": "Save", "exact": True}) == ("click", "Save")
    assert S.acted({"fill": "Milestone name", "value": "x"}) == ("fill", "Milestone name")
    assert S.acted({"choose": "B", "checked": True}) == ("choose", "B")
    assert S.acted({"press": "Escape"}) == ("press", "Escape")
    assert S.acted({"open": "#/projects/{p}", "expect": "x"}) is None
    assert S.acted({"expect": "settings are saved"}) is None


def _collect():
    c = S.Collector()
    # a screen with work on it, a journey uses two of its three safe controls; it also has a risky one
    c.page("#/projects/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/projectplan",
           [{"words": "Save the settings", "kind": "button"}, {"words": "Milestone name", "kind": "field"},
            {"words": "Add", "kind": "button"}, {"words": "Delete the milestone", "kind": "button"}], True)
    # a read-only screen (nothing to act on) that loaded, and one that failed to load
    c.page("#/admin/logs", [], True)
    c.page("#/change-log", [], False)
    # a screen with controls no journey acts on
    c.page("#/admin/users", [{"words": "Add a person", "kind": "button"}, {"words": "Search", "kind": "field"}], True)
    # a screen with only risky controls: read only for the count
    c.page("#/admin/containers", [{"words": "Restart", "kind": "button"}, {"words": "Stop", "kind": "button"}], True)
    c.action("#/projects/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/projectplan?x=1", {"click": "Save the settings", "wait": 1500})
    c.action("#/projects/{p}/projectplan", {"fill": "Milestone name", "value": "m"})
    c.action("#/projects/{p}/projectplan", {"expect": "saved"})               # looks only: not an action
    return c


def test_the_coverage_counts_acted_on_and_read_only_screens():
    got = S.summarise(_collect())
    rows = {r["screen"]: r for r in got["by_screen"]}
    plan = rows["#/projects/{id}/projectplan"]
    assert (plan["controls"], plan["used"], plan["left_out"], plan["covered"]) == (3, 2, 1, True)
    assert plan["not_used"] == ["Add"]
    assert rows["#/admin/logs"]["read_only"] and rows["#/admin/logs"]["covered"]          # opened and loaded
    assert rows["#/change-log"]["read_only"] and not rows["#/change-log"]["covered"]     # read only but it failed
    assert not rows["#/admin/users"]["covered"] and rows["#/admin/users"]["used"] == 0
    assert rows["#/admin/containers"]["read_only"] and rows["#/admin/containers"]["covered"]
    assert (got["screens"], got["covered"], got["acted_on"]) == (5, 3, 1)
    assert got["percent"] == 60.0
    assert (got["controls"], got["controls_used"]) == (5, 2) and got["controls_percent"] == 40.0
    assert {x["words"] for x in got["left_out"]} == {"Delete the milestone", "Restart", "Stop"}
    assert set(got["not_covered"]) == {"#/change-log", "#/admin/users"}


def test_the_result_line_and_the_summary(tmp_path):
    got = S.summarise(_collect())
    outcome, detail = S.line(got)
    assert outcome == "warning"                              # under the bar of 90% (owner, 25 Nov 2026, 12:12)
    assert "60.0% of 5 screens covered (1 acted on by a journey, 3 read only and opened)" in detail
    assert "controls used 2 of 5 (40.0%)" in detail and "3 risky controls left out" in detail
    S.save(tmp_path, got)
    back = json.loads((tmp_path / S.FILE).read_text(encoding="utf-8"))
    assert S.summary(back) == {"screens": 5, "covered": 3, "percent": 60.0, "acted_on": 1, "read_only": 3, "controls": 5,
                               "controls_used": 2, "controls_percent": 40.0, "left_out": 3, "bar": 90.0,
                               "screens_left_out": 0}
    assert S.line({"screens": 0}) [0] == "skipped" and S.summary(None) is None


def test_the_run_summary_carries_the_screens(tmp_path):
    from eax.testing import run_summary
    S.save(tmp_path, S.summarise(_collect()))
    made = run_summary.make({"run": {"id": 9}}, tmp_path)
    assert made["screens"]["percent"] == 60.0 and made["screens"]["controls_used"] == 2


class _Page:
    """The page's two answers: its address, and the controls it shows then (the same list for every screen here)."""
    def __init__(self, hashes, controls=None):
        self.hashes = list(hashes)
        self.controls = controls or []

    def evaluate(self, js):
        return self.controls if js == S.CONTROLS_JS else self.hashes.pop(0)


def test_a_journey_notes_the_screen_each_action_was_on(monkeypatch):
    """The screen is the one before the step moves on: a click that opens another page counts on the page it was on."""
    from eax.testing import ui_flows
    c = S.Collector()
    page = _Page(["#/projects/x/projectplan", "#/projects/x/phases"])
    page._eax_screens = c
    page._eax_caster = None
    monkeypatch.setattr(ui_flows, "step", lambda *_a, **_k: "")
    j = {"role": "super-admin", "steps": [{"click": "Settings"}, {"expect": "x"}, {"fill": "Start of B", "value": "1"}]}
    assert ui_flows.run_one(page, j, lambda *_a: None)[0] == "passed"
    assert c.actions == [("#/projects/x/projectplan", "click", "Settings"), ("#/projects/x/phases", "fill", "Start of B")]


def test_a_failed_step_is_not_counted(monkeypatch):
    from eax.testing import ui_flows
    c = S.Collector()
    page = _Page(["#/a"])
    page._eax_screens = c
    page._eax_caster = None
    page.screenshot = lambda **_k: b""
    monkeypatch.setattr(ui_flows, "step", lambda *_a, **_k: "no button")
    monkeypatch.setattr(ui_flows, "_page_says", lambda _p: "")
    assert ui_flows.run_one(page, {"role": "r", "steps": [{"click": "Save"}]}, lambda *_a: None)[0] == "failed"
    assert c.actions == []


def test_the_sweep_gives_each_page_its_controls():
    src = (API / "eax/testing/ui_pages.py").read_text(encoding="utf-8")
    assert "screens.page(route, _controls(page), outcome != \"failed\")" in src
    j = (API / "eax/testing/ui_journeys.py").read_text(encoding="utf-8")
    assert "whole = not repeat and not journeys and not pages_only" in j          # only a whole browser suite
    assert 'rec("coverage: the screens used by the journeys", outcome, detail' in j
    assert "page._eax_screens = screens" in j and "screens=screens" in j


def test_the_browser_side_leaves_out_how_one_moves_about():
    js = S.CONTROLS_JS
    for part in ("[role=tablist]", ".nav-groups", ".nav-menu", ".help-panel", "header", "!e.disabled",
                 "input:not([type=hidden])", "select", "textarea"):
        assert part in js, part


def test_the_summary_page_shows_the_screens():
    src = (REPO / "eaxcli/fullreport.py").read_text(encoding="utf-8")
    assert "<h2>Screens covered by journeys</h2>" in src and 'run.get("screens")' in src


# 25 Nov 2026, 10:41 (the first reading, run 9): three faults in the measuring, fixed in the testing code only


def test_a_drawn_views_generated_id_is_one_screen():
    """#/drawio/open/<id> counted as a screen of its own for each diagram opened."""
    assert S.screen("#/drawio/open/mwvv5exurqmy2g7g") == "#/drawio/open/{id}"
    assert S.screen("#/drawio/open/mwvv5mi1fmy9liuv") == "#/drawio/open/{id}"
    for kept in ("#/admin/self-test/harness", "#/admin/settings-transfer", "#/projects/{id}/projectplan",
                 "#/admin/machine-access/service-accounts", "#/metamodel/{id}/drawn-views"):
        assert S.screen(kept) == kept                     # words, even long ones, stay words


def test_the_controls_a_journey_meets_in_a_dialog_count():
    """The sweep reads a page as it opens; an action in a dialog or a later state matched nothing (12 of 32 screens acted
    on showed no controls). The journeys now read the screen's controls before each action, the open dialog's too."""
    from eax.testing import ui_flows
    c = S.Collector()
    page = _Page(["#/surveys/abc1234567/answer"], [{"words": "Send my answers", "kind": "button"},
                                                    {"words": "Delete my answers", "kind": "button"}])
    page._eax_screens = c
    page._eax_caster = None
    ui_step = ui_flows.step
    try:
        ui_flows.step = lambda *_a, **_k: ""
        assert ui_flows.run_one(page, {"role": "r", "steps": [{"click": "Send my answers"}]}, lambda *_a: None)[0] == "passed"
    finally:
        ui_flows.step = ui_step
    row = {r["screen"]: r for r in S.summarise(c)["by_screen"]}["#/surveys/{id}/answer"]
    assert (row["controls"], row["used"], row["left_out"], row["covered"]) == (1, 1, 1, True)


def test_the_browser_side_reads_the_open_dialog():
    js = S.CONTROLS_JS
    assert "querySelectorAll('[role=dialog]')" in js and "!main.contains(d)" in js
    assert "!e.closest('[role=dialog]')" in js            # a dialog's own header buttons count; the page's header not


def test_a_full_test_of_one_suite_runs_no_backup_restore_sonar_or_dr():
    """eax test full --detailed --suite ui went on to the backup and restore test (25 Nov 2026, 10:41)."""
    sys.path.insert(0, str(REPO))
    from eaxcli import main as M
    assert M.narrowed(["full", "--detailed", "--suite", "ui"])
    assert M.narrowed(["full", "--suite=api,ui"]) and M.narrowed(["full", "--role", "architect"])
    assert M.narrowed(["full", "--journey", "drawn view"]) and M.narrowed(["full", "--pages-only"])
    assert not M.narrowed(["full"]) and not M.narrowed(["full", "--suite", "all"])
    assert not M.narrowed(["full", "--no-sonar", "--no-dr"])
    src = (REPO / "eaxcli/main.py").read_text(encoding="utf-8")
    assert "part = last and narrowed(rest)" in src
    for gate in ("if not part:\n                    steps.append(full_step(\"backup and restore test\"",
                 "if not no_sonar and not part:", "if not no_dr and not part:"):
        assert gate in src, gate
    assert "or --pages-only only the dev check and that part of" in (REPO / "eaxcli/help.txt").read_text(encoding="utf-8")


# the screens' bar (owner, 25 Nov 2026, 12:12: "Bar for screens is currently 90%") and the screens left out of the count


def test_the_bar_is_90_and_under_it_is_a_warning():
    assert S.BAR == 90.0
    got = S.summarise(_collect())                         # 60% of 5 screens
    outcome, detail = S.line(got)
    assert outcome == "warning" and detail.startswith("under the bar of 90% by 30.0 points: 60.0% of 5 screens")
    c = S.Collector()
    for n in range(10):
        c.page(f"#/admin/area{n}", [], True)              # ten read-only screens that open: all covered
    outcome, detail = S.line(S.summarise(c))
    assert outcome == "passed" and detail.startswith("at or over the bar of 90%")


def test_the_screens_left_out_are_not_counted_and_are_listed():
    c = _collect()
    c.page("#/admin/pairings", [{"words": "Pair with another installation", "kind": "button"}], True)
    c.page("#/admin/self-test/run", [{"words": "Start", "kind": "button"}], True)
    got = S.summarise(c)
    assert got["screens"] == 5 and got["percent"] == 60.0                       # as without them
    assert {x["screen"] for x in got["screens_left_out"]} == {"#/admin/pairings", "#/admin/self-test/run"}
    assert all(x["why"] for x in got["screens_left_out"])
    assert "2 screens left out (#/admin/pairings, #/admin/self-test/run)" in S.line(got)[1]
    s = S.summary(got)
    assert (s["bar"], s["screens_left_out"]) == (90.0, 2)


def test_the_summary_page_shows_the_bar():
    sys.path.insert(0, str(REPO))
    from eaxcli import fullreport
    page = "".join(fullreport.cards({"selftest": {"screens": {"screens": 210, "covered": 49, "percent": 23.3, "bar": 90.0,
                                                              "screens_left_out": 5, "controls": 2545, "controls_used": 108,
                                                              "controls_percent": 4.2, "left_out": 78}}}))
    assert "screens left out" in page and "The bar: 90% of the screens counted." in page


def test_a_projects_frame_counts_on_its_own_page_only():
    """Pin, Mark complete, Finish and Choose… show on every tab of a project: counted on the project's own page."""
    frame = [{"words": "Pin self_test_x_3", "kind": "button", "frame": True},
             {"words": "Finish the project…", "kind": "button", "frame": True}]
    c = S.Collector()
    c.page("#/projects/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", frame + [{"words": "Open", "kind": "button"}], True)
    c.page("#/projects/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/models", frame, True)
    c.page("#/projects/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/tasks", frame + [{"words": "A new task", "kind": "field"}], True)
    rows = {r["screen"]: r for r in S.summarise(c)["by_screen"]}
    assert rows["#/projects/{id}"]["controls"] == 3
    assert rows["#/projects/{id}/models"]["read_only"] and rows["#/projects/{id}/models"]["covered"]
    assert rows["#/projects/{id}/tasks"]["controls"] == 1 and not rows["#/projects/{id}/tasks"]["covered"]
    assert ".project-head, .iteration-bar, .model-head" in S.CONTROLS_JS and "frame: true" in S.CONTROLS_JS


def test_a_models_frame_counts_on_its_own_page_only():
    frame = [{"words": "Pin self_test_x_1", "kind": "button", "frame": True}, {"words": "Lock...", "kind": "button", "frame": True}]
    c = S.Collector()
    c.page("#/metamodel/11111111-1111-1111-1111-111111111111", frame, True)
    c.page("#/metamodel/11111111-1111-1111-1111-111111111111/business", frame, True)
    c.page("#/model-admin/11111111-1111-1111-1111-111111111111/documents", frame, True)
    rows = {r["screen"]: r for r in S.summarise(c)["by_screen"]}
    assert rows["#/metamodel/{id}"]["controls"] == 2
    assert rows["#/metamodel/{id}/business"]["read_only"] and rows["#/model-admin/{id}/documents"]["read_only"]


def test_a_download_acts_on_its_screen():
    """Pressing a download button is using the screen (25 Nov 2026: the estate pictures' only safe action)."""
    assert S.acted({"download": "Download SVG"}) == ("download", "Download SVG")
