"""R5.33 (owner, 15 Nov 2026, 22:07: "In the UI give me ability to increase or decrease job slots with warnings if they
are more than number of available threads. This should be where I can add or remove api containers and in the auto
scaling")."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import jobqueue as Q  # noqa: E402


def test_slots_from_the_settings_then_the_config_file_then_4_and_2(monkeypatch):
    monkeypatch.delenv("EAX_JOB_CONCURRENCY", raising=False)
    monkeypatch.delenv("EAX_SCHEDULED_CONCURRENCY", raising=False)
    assert Q.per_server({}) == {"tasks": 4, "scheduled": 2, "watch": 1}
    monkeypatch.setenv("EAX_JOB_CONCURRENCY", "6")
    assert Q.per_server({})["tasks"] == 6
    assert Q.per_server({"jobs_slots_tasks": 8, "jobs_slots_scheduled": 3}) == {"tasks": 8, "scheduled": 3, "watch": 1}


def test_a_warning_past_the_machine_s_cpu_threads():
    per = {"tasks": 4, "scheduled": 2, "watch": 1}
    assert Q.threads_warning(per, 1, 16) == ""                      # 7 slots + 2 web workers on 16 threads
    w = Q.threads_warning(per, 2, 12)                                 # 18 at once on 12 threads
    assert "18 at once" in w and "12 CPU threads" in w
    assert Q.threads_warning(per, 4, None) == ""                      # not known: no warning


def test_read_at_each_start_and_shown_where_servers_are_set():
    entry = (REPO / "services/api/entrypoint.sh").read_text()
    assert "python -m eax.jobqueue slots" in entry and '--concurrency "${TASK_SLOTS:-4}" --queues tasks' in entry
    assert '--concurrency "${SCHEDULED_SLOTS:-2}" --queues default' in entry
    api = (REPO / "services/api/eax/api/jobs.py").read_text()
    assert '@blp.route("/slots")' in api and 'action="jobs.slots"' in api
    assert '"host_cpus": H["host_cpus"]()' in (REPO / "services/ops/scaling.py").read_text()
    for page in ("Scaling.jsx", "ContainerConsole.jsx", "Jobs.jsx"):
        assert "<JobSlots" in (REPO / "services/web/src" / page).read_text(), page
    jsx = (REPO / "services/web/src/Jobs.jsx").read_text()
    assert "is more than the {d.threads} CPU threads" in jsx and "up to {d.most_servers} servers by the scaling rules" in jsx
