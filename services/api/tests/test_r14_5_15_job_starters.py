"""Background tasks started through the API and followed to their end (api_writes.job_starters; R14.5, batch 4; owner,
25 Nov 2026, 17:01: "Yes please build 1 and 2"): every path is a route that is there with its method, every id is made by
an earlier step (the gap and common analyses by the run's earlier writes), each task is followed until it is done, each
area is refused for a role that may not, and what is made outside the run's models (the project's backup) is deleted."""

import json
import re
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
sys.path.insert(0, str(API / "tests"))

from test_r14_5_3_project_workspace_writes import ROUTES  # noqa: E402

from eax.testing import api_writes as A  # noqa: E402

M, OTHER, P = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "33333333-3333-3333-3333-333333333333"
SID = "e4fa1d33dfd8"
TAG = f"self_test_{SID}"
STEPS = A.job_starters(M, OTHER, P, TAG)


def test_every_step_calls_a_route_that_is_there_with_its_method():
    for s in STEPS:
        path = re.sub(r"\{[a-z0-9_]+\}", "x-id", s["path"].split("?", 1)[0])
        assert any(r.match(path) and s["method"] in m for r, m in ROUTES), f"no {s['method'].upper()} {s['path']}"


def test_every_id_is_made_earlier_in_the_plan():
    plan = A.plan({"model": M, "other_model": OTHER, "project": P, "sid": SID}, SID)
    made: set[str] = set()
    for s in plan:
        for name in re.findall(r"\{([a-z0-9_]+)\}", json.dumps([s["path"], s.get("body")])):
            assert name in made, f"{s['what']}: {{{name}}} is made by no earlier step"
        if s.get("save"):
            made.add(s["save"])
    assert all(s in plan for s in STEPS)
    assert all(re.fullmatch(r"[a-z_]+", s["save"]) for s in STEPS if s.get("save"))   # the runner fills {[a-z_]+}
    finds = {s["save"]: s["find"] for s in STEPS if s.get("find")}
    assert finds["gapid"] == {"name": f"{TAG} gap analysis"} and finds["comid"] == {"name": f"{TAG} common analysis"}
    earlier = [s for s in plan if s.get("save") in ("gaptask", "commontask")]
    assert {s["body"]["name"] for s in earlier} == {f"{TAG} gap analysis", f"{TAG} common analysis"}


def test_each_background_task_is_followed_until_it_is_done():
    started = [s for s in STEPS if "background" in s["what"]]
    assert len(started) >= 12
    for s in started:
        assert s["until"]["path"] == "/api/v1/tasks/{" + s["save"] + "}", s["what"]
        # done; or, where nothing can be chosen, failed with the words that refuse it (run 14)
        assert s["until"]["status"] == ["done"] or (s["until"]["status"] == ["failed"] and s["until"]["said"]), s["what"]
        assert s.get("save_at") == "task" and 202 in s["ok"], s["what"]


def test_each_area_has_a_refusal_and_the_project_backup_is_deleted():
    for a in {s["area"] for s in STEPS}:
        assert any(s.get("refused") for s in STEPS if s["area"] == a), a
    made = next(i for i, s in enumerate(STEPS) if s.get("save") == "pbfile")
    gone = next(i for i, s in enumerate(STEPS) if s["method"] == "delete" and "{pbfile}" in s["path"])
    assert gone > made and STEPS[made]["find"] == {"why": f"{TAG} project backup"}
    assert not any("/restore" in s["path"] or "over" in json.dumps(s.get("body") or {}) for s in STEPS)


def test_a_gap_found_only_when_there_is_one():
    item = next(s for s in STEPS if s.get("save") == "gapitem")
    assert item["optional"] and item["save_from"] == "items.0.id"
    before = next(s for s in STEPS if s.get("save") == "runb")
    assert before["optional"] and before["save_from"] == "runs.1.id"


def test_without_the_child_model_or_project_only_what_needs_neither():
    areas = {s["area"] for s in A.job_starters(M, None, None, TAG)}
    assert areas == {"change log export", "model package", "metamodel draft applied", "model wizards"}
