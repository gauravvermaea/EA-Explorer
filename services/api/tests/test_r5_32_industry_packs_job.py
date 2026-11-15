"""R5.32 (owner, 15 Nov 2026, 21:46: "also fix this why 4 jobs were there and not working"). The API's log of the full
test showed why: eax.industry_packs, every 10 minutes, started at 17:50, 18:00, 18:20 and 18:30 and never ended (18:10's
found the loader's lock taken and left), so the job runner's four slots were all held and the backup waited an hour.
queueing_lock only stops a second one waiting, not a second one running. Now a run leaves at once when another is
loading, a run loads for at most 8 minutes (the next carries on), and its database waits are short."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import industry_packs as ip  # noqa: E402
from eax import jobs  # noqa: E402


def test_a_run_leaves_at_once_when_another_is_loading(monkeypatch):
    asked = []
    monkeypatch.setattr(ip, "another_running", lambda engine: True)
    monkeypatch.setattr(jobs, "get_engine", lambda: asked.append("engine") or object())
    monkeypatch.setattr(ip, "load_shipped_each", lambda *a, **k: asked.append("loaded"))
    fn = getattr(jobs.industry_packs, "__wrapped__", None) or jobs.industry_packs.func
    fn(0)
    assert "loaded" not in asked                                     # nothing read, nothing waited on


def test_a_run_stops_at_its_deadline_and_leaves_the_rest(monkeypatch, tmp_path):
    files = [{"industry": code, "name": f"f{i}.xlsx"} for i, code in enumerate(list(ip.BY_CODE)[:1] * 5)]
    monkeypatch.setattr(ip, "scan", lambda root: files)
    done = []
    monkeypatch.setattr(ip, "_one_file", lambda conn, begin, f, *a: done.append(f["name"]))
    t = iter([0, 0, 10, 10, 10, 10])
    monkeypatch.setattr(ip.time, "monotonic", lambda: next(t))
    out = ip.load_folder(None, tmp_path, "system:job", begin=lambda: None, deadline=5)
    assert done == ["f0.xlsx", "f1.xlsx"] and len(out["left"]) == 3 and "left for the next run" in out["message"]


def test_short_waits_and_the_lock_looked_at_without_taking_it():
    src = (REPO / "services/api/eax/industry_packs.py").read_text()
    assert "SET lock_timeout = '30s'" in src and "SET statement_timeout = '120s'" in src
    assert "SET LOCAL lock_timeout = '30s'" in src
    assert "FROM pg_locks WHERE locktype = 'advisory' AND granted" in src
    assert "RUN_BUDGET = 8 * 60" in src
    job = (REPO / "services/api/eax/jobs.py").read_text()
    assert "if ip.another_running(get_engine()):" in job and "ip.timeouts(conn)" in job


def test_a_scheduled_job_never_runs_twice_at_once():
    """21:59: "if a job already exists ... can we ensure it doesnt load again?": every scheduled job has a lock of its
    own name, so a second one waits (without a slot) until the first ends; none is ever killed by EA Explorer."""
    import re
    lines = (REPO / "services/api/eax/jobs.py").read_text().splitlines()
    scheduled = [ln for i, ln in enumerate(lines) if ln.startswith("@app.task(") and lines[i - 1].startswith("@app.periodic(")]
    assert len(scheduled) >= 30
    for ln in scheduled:
        m = re.search(r'queueing_lock="([^"]+)"', ln)
        assert m and f'lock="{m.group(1)}"' in ln.replace(f'queueing_lock="{m.group(1)}"', ""), ln
    assert '@app.task(name="eax.industry_packs", queue="default", queueing_lock="industry_packs", lock="industry_packs")' in lines
    # nothing kills or clears by itself: only a person, from System Admin › Jobs (owner, 22:01: "I dont want any job to be
    # killed without human approval, recomendation yes")
    for f in ("eax/jobs.py", "eax/alerts.py"):
        src = (REPO / "services/api" / f).read_text()
        assert "jobqueue.kill(" not in src and "jobqueue.clear_stuck(" not in src and "/restart/api" not in src
    q = (REPO / "services/api/eax/jobqueue.py").read_text()
    body = q.split("def main(")[0]                                  # only eax jobs, asked by a person, restarts
    assert "_restart_runner()" not in body.split("def _restart_runner")[1].split("\n\n\n", 1)[1]
    api = (REPO / "services/api/eax/api/jobs.py").read_text()
    assert api.count('require_auth("system.operate")') >= 4
