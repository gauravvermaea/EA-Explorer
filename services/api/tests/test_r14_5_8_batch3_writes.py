"""Release 14.5, batch 3 (owner, 25 Nov 2026, 16:20: "Please add more test cases to acheive this goal as you see fit"):
the model's own KPIs, report designs, saved views, data quality and publishing (model_extras); a project's placeholder
views and reference folders (project_extras); webhooks, sites, job priorities, the API harness and an application backup's
pin (admin_extras); the runner's optional find; and the routes left out of the goal because no test may run them on a live
installation (run.LEFT_OUT_ROUTES)."""

import json
import re
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
sys.path.insert(0, str(API / "tests"))

from test_r14_5_3_project_workspace_writes import ROUTES  # noqa: E402

from eax.testing import api_writes as A  # noqa: E402

M, ENT = "11111111-1111-1111-1111-111111111111", "33333333-3333-3333-3333-333333333333"
P = "44444444-4444-4444-4444-444444444444"
SID = "e4fa1d33dfd8"
TAG = f"self_test_{SID}"
STEPS = A.model_extras(M, ENT, SID, TAG) + A.project_extras(P, TAG) + A.admin_extras(SID, TAG)


def test_every_step_calls_a_route_that_is_there_with_its_method():
    for s in STEPS:
        path = re.sub(r"\{[a-z0-9_]+\}", "x-id", s["path"].split("?", 1)[0])
        assert any(r.match(path) and s["method"] in m for r, m in ROUTES), f"no {s['method'].upper()} {s['path']}"


def test_every_id_a_step_uses_is_made_by_an_earlier_step():
    made: set[str] = set()
    for s in STEPS:
        for name in re.findall(r"\{([a-z0-9_]+)\}", json.dumps([s["path"], s.get("body")])):
            assert name in made, f"{s['what']}: {{{name}}} is made by no earlier step"
        if s.get("save"):
            assert re.fullmatch(r"[a-z_]+", s["save"]), s["save"]        # the runner fills only {[a-z_]+}
            made.add(s["save"])


def test_only_the_runs_own_model_project_and_names():
    for s in STEPS:
        for u in re.findall(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", json.dumps([s["path"], s.get("body")])):
            assert u in (M, ENT, P), s
        body = s.get("body") or {}
        if isinstance(body.get("name"), str):
            assert body["name"].startswith(TAG), s


def test_what_is_made_is_removed_again():
    for key in ("kpi", "design", "sview", "phcode", "hook", "site", "hcase"):
        made = [i for i, s in enumerate(STEPS) if s.get("save") == key]
        gone = [i for i, s in enumerate(STEPS) if not s.get("refused") and "{" + key + "}" in s["path"]
                and (s["method"] == "delete" or s["path"].endswith("/delete"))]
        assert made and gone and gone[-1] > made[0], key
    folder = [s for s in STEPS if s["area"] == "reference folders" and (s.get("body") or {}).get("delete")]
    assert folder and folder[0]["body"]["path"] == "{rfolder}"
    pins = [s["body"]["pinned"] for s in STEPS if s["area"] == "application backups" and s["method"] == "post"
            and not s.get("refused")]
    assert pins == [True, False]                                     # left as it was found
    favs = [s["body"]["favourite"] for s in STEPS if s["path"] == "/api/v1/me/favourites" and s["method"] == "post"]
    assert favs == [True, False]


def test_nothing_is_sent_backed_up_or_changed_for_good():
    hook = next(s for s in STEPS if s["what"].startswith("add a webhook"))
    assert hook["body"]["enabled"] is False and ".invalid/" in hook["body"]["url"]
    site = next(s for s in STEPS if s["what"] == "add a site")
    assert site["body"]["url"].endswith(".invalid")
    assert not any(s["method"] == "post" and s["path"] in ("/api/v1/admin/backups/application",
                                                           "/api/v1/admin/backups/infrastructure") for s in STEPS)
    assert not any("/publish" in s["path"] and "request" not in s["path"] and "publishing" not in s["path"] for s in STEPS)
    level = next(s for s in STEPS if s["what"] == "save its level as it is")
    assert level["body"] == {"level": "{jplevel}"}                   # the level it has, read just before
    assert not any("/sessions" in s["path"] for s in STEPS)          # a harness session makes a whole set of test data
    assert not any("/test" in s["path"].rsplit("/", 1)[-1] for s in STEPS if "/webhooks/" in s["path"])


def test_each_area_has_a_refusal():
    for a in {s["area"] for s in STEPS}:
        assert any(s.get("refused") for s in STEPS if s["area"] == a), a


def test_the_plan_holds_them():
    plan = A.plan({"model": M, "project": P, "entity": ENT, "sid": SID}, SID)
    areas = {w["area"] for w in plan}
    assert {"model KPIs", "report designs", "saved views", "data quality", "publishing", "placeholder views",
            "reference folders", "webhooks", "sites", "job priorities", "api harness", "application backups"} <= areas
    assert any(w["path"].endswith(f"/entities/{ENT}/quality/recheck") for w in plan)
    assert not any("/entities/" in w["path"] for w in A.model_extras(M, None, SID, TAG))


def _fake(answers):
    calls = []

    def call(base, method, path, token, body=None, **_kw):
        calls.append((method.lower(), path, body))
        for (m, p), a in answers.items():
            if m == method.lower() and p == path:
                return a
        return 200, {}
    return call, calls


def test_an_optional_find_with_nothing_to_find_skips_it_and_what_needs_it(monkeypatch):
    call, calls = _fake({("get", "/api/v1/admin/backups"): (200, {"infrastructure": [{"name": "i1", "pinned": False}],
                                                                   "application": {"runs": []}})})
    monkeypatch.setattr(A, "call", call)
    got = []
    counts = A.run("https://x", {"super-admin": "t", "architect": "t"}, {"sid": SID}, lambda *a, **k: got.append(a[:2]),
                   area="application backups")
    assert [o for _, o in got] == ["skipped"] * 4 and counts["failed"] == 0
    assert calls == [("get", "/api/v1/admin/backups", None)]          # nothing pinned


def test_an_optional_find_that_finds_one_pins_and_unpins_that_one(monkeypatch):
    runs = {"runs": [{"name": "r-pinned", "format": "eax-application-backup/1", "pinned": True},
                     {"name": "r-free", "format": "eax-application-backup/1", "pinned": False}]}
    call, calls = _fake({("get", "/api/v1/admin/backups"): (200, {"infrastructure": [{"name": "i1", "pinned": False}],
                                                                   "application": runs}),
                         ("post", "/api/v1/admin/backups/application/r-free/pin"): (200, {"ok": True})})
    monkeypatch.setattr(A, "call", call)
    got = []
    A.run("https://x", {"super-admin": "t"}, {"sid": SID}, lambda *a, **k: got.append(a[:2]), area="application backups")
    pins = [(p, b) for m, p, b in calls if m == "post"]
    assert pins == [("/api/v1/admin/backups/application/r-free/pin", {"pinned": True}),
                    ("/api/v1/admin/backups/application/r-free/pin", {"pinned": False})]
    assert [o for _, o in got][:3] == ["passed"] * 3 and got[-1][1] == "skipped"       # no architect in this run


def test_the_routes_left_out_are_in_the_code_and_say_why():
    from eax.testing import run
    _, shown = run.left_out_lines(API)
    assert all(x["found"] for x in shown), [x["route"] for x in shown if not x["found"]]
    routes = {x["route"] for x in shown}
    for r in ("/people/mfa-reset", "/queue/clear-stuck", "/queue/restart-runner", "/queue/history",
              "/admin/settings-transfer/import", "/admin/settings-transfer/undo", "/admin/logs/rolling", "/admin/allow",
              "/admin/logs/web-debug", "/admin/containers/<service>/terminal", "/admin/alerting/test-email",
              "/admin/backups/restore-model", "/admin/backups/infrastructure", "/admin/backups/override"):
        assert r in routes, r
    assert all(x["why"] for x in shown)
    # a route left out is never run by the plan
    plan = A.plan({"model": M, "project": P, "entity": ENT, "other_model": "22222222-2222-2222-2222-222222222222",
                   "sid": SID}, SID)
    for x in shown:
        pat = re.compile("^/api/v1" + re.sub(r"<[^>]+>", "[^/]+", x["route"]) + "$")
        for w in plan:
            if pat.match(w["path"].split("?", 1)[0]):
                assert x["methods"] and w["method"] not in x["methods"], (x["route"], w["method"])
