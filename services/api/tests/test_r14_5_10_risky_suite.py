"""The risky suite (D927; owner, 25 Nov 2026, 16:37: "Build additional test suite from api and UI to allow running risky
things, they will not always run, they will run if and only if someone in full test enables risky option"; 16:41: "risky
should not allow restart, allow installation down, roatate secrets, or allow full infrastructure restore. Model restore is
ok, deleting anything like logs models etc is ok"): its API writes (api_writes.risky_writes) and journeys
(ui_flows.RISKY_JOURNEYS) join a run only with --risky; the routes and the screen it runs then count."""

import json
import re
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))
sys.path.insert(0, str(API / "tests"))

from test_r14_5_3_project_workspace_writes import ROUTES  # noqa: E402

from eax.testing import api_writes as A  # noqa: E402
from eax.testing import run as R  # noqa: E402
from eax.testing import screen_coverage as S  # noqa: E402
from eax.testing import ui_flows as U  # noqa: E402

M, OTHER, P = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "p3"
SID = "e4fa1d33dfd8"
TAG = f"self_test_{SID}"
IDS = {"model": M, "other_model": OTHER, "project": P, "sid": SID, "model_name": f"{TAG}_1"}
STEPS = A.risky_writes(M, f"{TAG}_1", SID, TAG)


def test_only_when_the_run_asks_for_it_and_last_of_all():
    plain, risky = A.plan(IDS, SID), A.plan({**IDS, "risky": "yes"}, SID)
    assert not any(w.get("risky") for w in plain)
    extra = [w for w in risky if w.get("risky")]
    assert extra == STEPS and risky[-len(extra):] == extra and risky[:len(plain)] == plain
    names = [j["name"] for j in U.journeys(IDS)]
    assert not any(n.startswith("risky ") for n in names)
    with_risky = [j["name"] for j in U.journeys({**IDS, "risky": "yes"})]
    assert {j["name"] for j in U.RISKY_JOURNEYS} <= set(with_risky)


def test_every_step_calls_a_route_that_is_there_and_uses_what_an_earlier_step_made():
    made: set[str] = set()
    for s in STEPS:
        path = re.sub(r"\{[a-z0-9_]+\}", "x-id", s["path"].split("?", 1)[0])
        assert any(r.match(path) and s["method"] in m for r, m in ROUTES), f"no {s['method'].upper()} {s['path']}"
        for name in re.findall(r"\{([a-z0-9_]+)\}", json.dumps([s["path"], s.get("body")])):
            assert name in made, f"{s['what']}: {{{name}}} is made by no earlier step"
        if s.get("save"):
            made.add(s["save"])


def test_never_a_restart_the_installation_down_the_secrets_or_a_full_restore():
    never = ("/restart", "restart-runner", "/secrets", "/front-certificate", "/restore-all",
             "/backups/infrastructure", "/servers", "/services/", "/persist/delete", "/first-run", "/stop",
             "/maintenance", "/updates", "/rollback")
    for s in STEPS:
        assert not any(n in s["path"] for n in never), s["path"]
        assert s["path"].split("?")[0] != "/api/v1/admin/backups/restore", s["path"]          # the full restore
        assert (s.get("body") or {}).get("restart") in (None, False), s
    restore = [s for s in STEPS if s["path"] == "/api/v1/admin/backups/restore-model" and not s.get("refused")]
    assert restore and all(s["body"]["model"] == M and s["body"]["mode"] == "over" for s in restore)   # its own model


def test_deletions_reach_only_what_is_old_or_the_runs_own():
    by = {s["what"]: s for s in STEPS}
    assert by["delete the logs older than ten years"]["body"] == {"days": 3650}
    assert "older_than_days=3650" in by["delete the finished jobs older than ten years"]["path"]
    assert "from=2000-01-01&to=2000-01-02" in by["delete a day of resource history in 2000"]["path"]
    assert by["reset the run's no-role account's second factor"]["body"] == {"usernames": [f"svc-self-test-{SID}-no-role"]}
    assert by["delete the backup"]["path"].endswith("/backups/{rbfile}/delete")
    assert by["find the backup"]["find"] == {"where": "model", "why": f"{TAG} risky"}
    assert by["send the test email"]["body"]["to"].endswith("@example.invalid")


def test_settings_are_saved_back_as_they_were():
    by = {s["what"]: s for s in STEPS}
    assert by["save the log sizes as they are"]["same_as"] == "/api/v1/admin/logs/rolling"
    assert by["save the allow lists as they are"]["same_as"] == "/api/v1/admin/allow"
    assert by["and off again"]["body"] == {"minutes": 0}
    imp = by["take the same settings in"]
    assert imp["body"]["file"] == "{stfile}" and by["export the application settings"].get("save_whole")


def test_each_area_has_a_refusal():
    for a in {s["area"] for s in STEPS}:
        assert any(s.get("refused") for s in STEPS if s["area"] == a), a


def test_the_whole_answer_is_kept_for_the_next_step(monkeypatch):
    calls = []
    exported = {"format": "eax-settings/1", "parts": {"application": {"currency": "ZAR"}}}

    def call(base, method, path, token, body=None, **_kw):
        calls.append((method.lower(), path, body))
        return (200, exported) if path.endswith("/export") else (200, {})
    monkeypatch.setattr(A, "call", call)
    A.run("https://x", {"super-admin": "t"}, {**IDS, "risky": "yes"}, lambda *a, **k: None, area="risky: settings transfer")
    imp = next(b for m, p, b in calls if p.endswith("/import"))
    assert json.loads(imp["file"]) == exported and imp["picks"] == {"application": "all"}


def test_the_routes_it_runs_count_only_in_a_risky_run():
    keys = {(f, r) for f, r, _m, _w in R.LEFT_OUT_ROUTES}
    assert R.RISKY_RUNS <= keys
    _, plain = R.left_out_lines(API)
    _, risky = R.left_out_lines(API, risky=True)
    gone = {x["route"] for x in plain} - {x["route"] for x in risky}
    assert gone == {r for _f, r in R.RISKY_RUNS}
    for route in ("/admin/secrets/rotate", "/admin/restart", "/admin/backups/restore", "/admin/backups/infrastructure",
                  "/queue/restart-runner", "/admin/front-certificate"):
        assert route in {x["route"] for x in risky}, route                # always left out
    for _f, route in R.RISKY_RUNS:                                         # each one the risky suite really calls
        pat = re.compile("^/api/v1(?:/jobs)?" + re.sub(r"<[^>]+>", "[^/]+", route) + "$")
        assert any(pat.match(s["path"].split("?", 1)[0]) for s in STEPS if not s.get("refused")), route


def test_the_journeys_are_headless_and_their_words_are_on_the_screens():
    web = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "services/web/src").glob("*.jsx"))
    for j in U.RISKY_JOURNEYS:
        assert j.get("risky") and j["name"].startswith("risky ")
        if any("click" in st for st in j["steps"]):
            assert j.get("headless_only"), j["name"]                      # each Delete asks window.confirm
    for words in ("Back up now", "Why, e.g. before reorganising capabilities", "Clean up now", "older than {box(\"logs\")}",
                  'aria-label="days"', ">Delete<", '{b.pinned ? "Unpin" : "Pin"}'):
        assert words in web, words
    steps = [st for j in U.RISKY_JOURNEYS for st in j["steps"]]
    assert not any(re.search(r"restart|rotate|restore", str(st.get("click", "")), re.I) for st in steps)


def test_the_screens_count_what_the_risky_suite_opens_and_presses():
    def seen():
        c = S.Collector()
        c.page("#/admin/restores", [], True)
        c.page("#/metamodel/x/backups", [{"words": "Back up now", "kind": "button"}, {"words": "Delete", "kind": "button"}], True)
        c.action("#/metamodel/x/backups", {"click": "Delete"})
        return c
    plain, risky = S.summarise(seen()), S.summarise(seen(), risky=True)
    assert [x["screen"] for x in plain["screens_left_out"]] == ["#/admin/restores"] and len(plain["left_out"]) == 1
    assert risky["screens_left_out"] == [] and risky["left_out"] == [] and risky["risky"] is True
    assert risky["screens"] == plain["screens"] + 1 and risky["controls_used"] == plain["controls_used"] + 1


def test_the_command_line_and_the_runner_carry_it():
    ops = (ROOT / "services/ops/testruns.py").read_text(encoding="utf-8")
    assert 'risky = "--risky" in args' in ops and 'cmd.append("--risky")' in ops and "attack_allowed()" in ops
    run = (API / "eax/testing/run.py").read_text(encoding="utf-8")
    assert 'a.add_argument("--risky"' in run and 'ids = {**ids, "risky": "yes"}' in run
    assert "goal_figures(c, risky=" in run
    help_ = (ROOT / "eaxcli/help.txt").read_text(encoding="utf-8")
    assert "--risky adds the risky suite" in help_ and "$ {eax} test full --risky" in help_
    help_.encode("ascii")
    assert '"--risky"' in (ROOT / "eaxcli/commands.py").read_text(encoding="utf-8")
    assert "the risky suite (--risky)" in (ROOT / "eaxcli/fullreport.py").read_text(encoding="utf-8")
    assert "the risky suite (--risky)" in (ROOT / "services/web/src/FullSummary.jsx").read_text(encoding="utf-8")
