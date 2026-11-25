"""Release 14.5, batch 2 (owner, 25 Nov 2026, 14:12: "build all i will test everything in one go"): the rest of the API's
writes (eax/testing/api_writes.platform_writes) and the runner's three new abilities: a setting saved back as it is read
(same_as), a value taken from where the answer keeps it (save_from), an item found in a list (find)."""

import json
import re
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
sys.path.insert(0, str(API / "tests"))

from test_r14_5_3_project_workspace_writes import ROUTES  # noqa: E402

from eax.testing import api_writes as A  # noqa: E402

M, OTHER = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
SID = "e4fa1d33dfd8"
TAG = f"self_test_{SID}"
STEPS = A.platform_writes(M, OTHER, SID, TAG)


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
            made.add(s["save"])


def test_only_the_runs_own_models_and_names():
    for s in STEPS:
        for u in re.findall(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", json.dumps([s["path"], s.get("body")])):
            assert u in (M, OTHER), s
        body = s.get("body") or {}
        for k in ("name", "keycloak_role"):
            if isinstance(body.get(k), str):
                assert body[k].startswith(TAG), s
    assert all(SID in s["path"] for s in STEPS if "/alerting/custom:" in s["path"])


def test_what_is_made_is_removed_again():
    pairs = {"mtag": "delete", "tagbg": "delete", "rmap": "delete"}
    for key, how in pairs.items():
        assert any(s["method"] == how and "{" + key + "}" in s["path"] for s in STEPS), key
    assert any(s["path"].endswith("/{mbfile}/delete") for s in STEPS)                          # the model's backup
    assert any(s["path"].endswith(f"custom:self-test-{SID}/delete") for s in STEPS)            # the alert check
    assert any(s["method"] == "delete" and "/people/" in s["path"] for s in STEPS)             # the role on the model
    drafts = [s["what"] for s in STEPS if s["area"] == "metamodel drafts" and not s.get("refused")]
    assert drafts[-1] == "reject it for good"


def test_nothing_restarts_restores_or_rewrites_the_installation():
    risky = ("/restart", "/restore-all", "/backups/restore", "/secrets", "/front-certificate", "/persist/delete",
             "/config-file/save", "/config-copies", "/logs/rolling", "/admin/allow", "/web-debug", "/apply", "/repair",
             "/queue/clear-stuck", "/restart-runner", "/updates/start", "/rollback")
    for s in STEPS:
        assert not any(r in s["path"] for r in risky), s["path"]
    tag_restore = [s for s in STEPS if s["path"].endswith("/{mtag}/restore")]
    assert tag_restore and all(M in s["path"] for s in tag_restore)                            # the run's own model only
    assert all(not s["path"].endswith("/apply") for s in STEPS)                                # the merge only planned


def test_each_area_has_a_refusal():
    areas = {s["area"] for s in STEPS}
    no_refusal: set[str] = set()                         # every area is refused for a role that may not
    for a in areas - no_refusal:
        assert any(s.get("refused") for s in STEPS if s["area"] == a), a


def test_background_work_is_followed_to_its_end():
    bg = [s for s in STEPS if s.get("until")]
    assert len(bg) >= 7
    for s in bg:
        assert s["until"]["path"].endswith("{" + s["save"] + "}")
    hb = next(s for s in STEPS if s["path"] == "/api/v1/jobs/heartbeat")
    assert hb["save_from"] == "job_id" and hb["until"]["status"] == ["succeeded"]


def test_the_runners_new_abilities():
    assert A.same_as({"a": 1, "b": 2, "c": 3}, ["a", "c", "z"]) == {"a": 1, "c": 3}
    assert A.same_as({"a": 1}) == {"a": 1}
    assert A.pick({"job_id": 42}, "job_id") == "42"
    assert A.pick({"items": [{"key": "k1"}]}, "items.0.key") == "k1"
    assert A.pick({"items": []}, "items.0.key") is None and A.pick({"x": True}, "x") is None
    answer = {"runs": [{"id": 7, "state": "passed"}, {"id": 9, "state": "running"}], "journeys": [{"name": "x"}]}
    assert A.find(answer, {"state": "running"}) == "9"
    assert A.find({"backups": [{"where": "application", "file": "a"}, {"where": "model", "file": "b"}]},
                  {"where": "model"}, "file") == "b"
    assert A.find({"tags": []}, {"name": "x"}) is None


def test_they_run_with_the_runs_models():
    plan = A.plan({"model": M, "other_model": OTHER, "sid": SID}, SID)
    assert any(w["area"] == "model tags" for w in plan) and any(w["area"] == "model merges" for w in plan)
    assert not any(w["area"] == "model people" for w in A.platform_writes(M, None, SID, TAG))
