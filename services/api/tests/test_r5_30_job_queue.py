"""R5.30 (owner, 15 Nov 2026, 21:35 to 21:42): the full test's backup waited an hour for a job slot ("stuck for almost an
hour"); "if a job is stuck for too long I should see in the dashboard number of jobs stuck and advise to clear them or
delete them from queue or add more api servers"; "a jobs view which clearly shows what is in job queue"; "Jobs in queue
how many are worked on, abilty to kill, move things down in priority. User friendly description"; "I want a UI"."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import jobqueue as Q  # noqa: E402

NOW = datetime(2026, 11, 15, 19, 54, tzinfo=UTC)


def _job(status, minutes, task="eax.run_task", kind="backup.infrastructure", **kw):
    at = NOW - timedelta(minutes=minutes)
    return {"id": kw.get("id", 1), "task_name": task, "kind": kind, "status": status, "label": kw.get("label", ""),
            "deferred_at": at, "started_at": at if status == "doing" else None}


def test_stuck_waiting_and_running_with_more_time_for_long_kinds():
    w = Q.judge(_job("todo", 60), NOW, 5, 60)
    assert w["stuck"] and "waiting for 60 minutes" in w["why"]          # the full test's backup: waited an hour
    assert not Q.judge(_job("todo", 2), NOW, 5, 60)["stuck"]
    assert not Q.judge(_job("doing", 120), NOW, 5, 60)["stuck"]          # a backup may run three times as long
    assert Q.judge(_job("doing", 200), NOW, 5, 60)["stuck"]
    assert Q.judge(_job("doing", 61, task="eax.keycloak_upkeep", kind=None), NOW, 5, 60)["stuck"]


def test_advice_in_words_for_each_case():
    every_slot = Q.advice(waiting=3, running=7, stuck_waiting=1, stuck_running=7, slot_count=7)
    assert {a["action"] for a in every_slot} >= {"kill", "restart", "cancel"}
    assert any("Every one of the 7 job slots is held by a stuck job" in a["text"] for a in every_slot)
    idle = Q.advice(waiting=1, running=0, stuck_waiting=1, stuck_running=0, slot_count=7)
    assert any(a["action"] == "restart" and "may not be working" in a["text"] for a in idle)
    busy = Q.advice(waiting=5, running=7, stuck_waiting=2, stuck_running=0, slot_count=7)
    assert any(a["action"] == "scale" and "add an API server" in a["text"] for a in busy)
    assert Q.advice(0, 1, 0, 0, 7) == [{"action": "", "text": "Nothing is stuck."}]


def test_user_friendly_descriptions_and_counts():
    shaped = Q._shape({"task_name": "eax.keycloak_upkeep", "status": "doing", "args": {"timestamp": 1}, "label": None})
    assert shaped["what"] == "Keep sign-in (Keycloak) in step" and shaped["status_words"] == "Being worked on"
    assert shaped["periodic"] and shaped["who"] == "the schedule"
    asked = Q._shape({"task_name": "eax.run_task", "status": "todo", "args": {"actor": "ann"}, "label": "Infrastructure backup",
                      "requested_by": "ann"})
    assert asked["what"] == "Infrastructure backup" and asked["who"] == "ann" and asked["status_words"] == "Waiting"
    jobs = [{**Q.judge(_job("doing", 5, id=1), NOW, 5, 60)}, {**Q.judge(_job("todo", 30, id=2), NOW, 5, 60)}]
    s = Q.summary(jobs, [{"status": "failed"}], 5, 60, slot_count=7)
    assert (s["running"], s["waiting"], s["stuck"], s["free_slots"], s["failed_recently"]) == (1, 1, 1, 6, 1)


def test_people_s_work_has_slots_of_its_own_and_the_alerts_too():
    jobs = (REPO / "services/api/eax/jobs.py").read_text()
    assert '@app.task(name="eax.run_task", queue="tasks")' in jobs
    assert '@app.task(name="eax.alerts_run", queue="watch", queueing_lock="alerts_run", lock="alerts_run")' in jobs
    entry = (REPO / "services/api/entrypoint.sh").read_text()
    for q in ("--queues tasks", "--queues default", "--queues watch"):
        assert q in entry
    assert '"jobs_stuck"' in (REPO / "services/api/eax/alerts.py").read_text()


def test_the_jobs_page_and_the_dashboard():
    api = (REPO / "services/api/eax/api/jobs.py").read_text()
    for r in ('"/queue"', "any(cancel, kill, up, down)", '"/queue/restart-runner"', 'require_auth("system.operate")'):
        assert r in api
    jsx = (REPO / "services/web/src/Jobs.jsx").read_text()
    for t in ("being worked on", "Kill", "Move down", "Move up", "Cancel", "Restart the job runner", "Add API servers"):
        assert t in jsx
    assert "<JobsSummary />" in (REPO / "services/web/src/Heartbeat.jsx").read_text()
    assert '"#/admin/jobs"' in (REPO / "services/web/src/menu.js").read_text()
