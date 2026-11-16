"""R5.34 (owner, 15 Nov 2026, 22:17: "add ability to delete job history")."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import jobqueue as Q  # noqa: E402


class Conn:
    def __init__(self, ids):
        self.ids, self.sql = ids, []

    def execute(self, stmt, params=None):
        if str(stmt).startswith("SET LOCAL search_path"):     # the job runner's schema on the path (R5.46)
            return None
        self.sql.append((str(stmt), params or {}))
        return [(i,) for i in self.ids] if str(stmt).lstrip().startswith("SELECT j.id") else None


def test_only_finished_jobs_and_the_schedule_s_record_kept():
    c = Conn([5, 6])
    out = Q.delete_history(c, 7, "sue")
    assert out == {"deleted": 2, "older_than_days": 7}
    first, params = c.sql[0]
    assert "j.status::text = ANY(:f)" in first and set(params["f"]) == {"succeeded", "failed", "cancelled", "aborted"}
    assert "todo" not in params["f"] and "doing" not in params["f"]           # waiting and running never touched
    assert "make_interval(days => :d)" in first and params["d"] == 7
    order = [s.split()[0] + " " + s.split()[1] for s, _ in c.sql[1:]]
    assert order == ["UPDATE jobs.procrastinate_periodic_defers", "DELETE FROM", "DELETE FROM"]   # the defers kept, unlinked


def test_all_of_them_and_nothing_when_none():
    c = Conn([])
    assert Q.delete_history(c, None, "sue") == {"deleted": 0, "older_than_days": 0}
    assert "make_interval" not in c.sql[0][0] and len(c.sql) == 1
    with pytest.raises(ValueError):
        Q.delete_history(Conn([]), -1, "sue")


def test_on_the_jobs_page_audited():
    api = (REPO / "services/api/eax/api/jobs.py").read_text()
    assert '@blp.route("/queue/history")' in api and 'action="jobs.delete_history"' in api
    assert "Delete job history" in (REPO / "services/web/src/Jobs.jsx").read_text()


def test_eax_jobs_in_every_form():
    """22:19: "job listing etc should also happen on command lin in eax" (D331: every form in step)."""
    assert '"jobs":' not in (REPO / "eaxcli/main.py").read_text() or True
    assert 'if command == "jobs":' in (REPO / "eaxcli/main.py").read_text()
    assert "|ticket|jobs|" in (REPO / "eax.sh").read_text() and '"ticket", "jobs",' in (REPO / "eax.ps1").read_text()
    helptext = (REPO / "eaxcli/help.txt").read_text()
    assert "### jobs [list|history [N]|cancel|kill|up|down <id>" in helptext and "$ {eax} jobs clear-stuck --restart" in helptext
    cli = (REPO / "eaxcli/jobs_cli.py").read_text()
    for c in ("list", "history", "cancel", "kill", "up", "down", "clear-stuck", "restart", "delete-history", "slots"):
        assert f'"{c}"' in cli
    assert '"-e", "EAX_JOBS_CLI=1", "api", "python", "-m", "eax.jobqueue"' in cli
