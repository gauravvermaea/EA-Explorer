"""R5.5.3 (owner, 15 Nov 2026, 20:32: "When tests are running we dont know how many are left on the dashboard in UI can
you say How many have run and how many are left in this phase"; "I dont see them. Make it big and fat on screen"):
each phase of a run going on, done and about how many left, the running one big on the Self-test page and in Watch."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax.testing import store  # noqa: E402


class Conn:
    """The questions phases() asks: this run's results by phase, by phase and outcome (R5.47), and the last finished
    run's count of a phase."""
    def __init__(self, mine, before, outcomes=()):
        self.mine, self.before, self.outcomes = mine, before, list(outcomes)

    def execute(self, stmt, params=None):
        sql, params = str(stmt), params or {}

        class R:
            def __init__(self, rows=None, one=None):
                self.rows, self.one = rows or [], one

            def mappings(self):
                return self

            def all(self):
                return self.rows

            def scalar(self):
                return self.one
        if "GROUP BY suite, outcome" in sql:
            return R(rows=self.outcomes)
        if "GROUP BY suite" in sql:
            return R(rows=self.mine)
        return R(one=self.before.get(params.get("s")))


def test_each_phase_done_left_and_which_is_running():
    run = {"id": 9, "state": "running", "level": "detailed", "suites": ["api", "ui", "db", "security"]}
    conn = Conn([{"suite": "api", "n": 900, "last": 900}, {"suite": "db", "n": 12, "last": 950}],
                {"api": 900, "db": 40, "security": 25})
    got = {p["suite"]: p for p in store.phases(conn, run)}
    assert [p["suite"] for p in store.phases(conn, run)] == ["api", "ui", "db", "security"]
    assert got["db"]["state"] == "running" and got["db"]["done"] == 12 and got["db"]["left"] == 28 and got["db"]["total"] == 40
    assert got["api"]["state"] == "finished" and got["api"]["left"] == 0
    assert got["security"]["state"] == "waiting" and got["security"]["total"] == 25
    assert got["ui"]["total"] is None and got["ui"]["left"] is None                        # never run before: not known
    assert got["db"]["name"] == "Database"


def test_shown_big_on_the_page_and_in_watch():
    jsx = (REPO / "services/web/src/TestPhases.jsx").read_text()
    assert "test-phase-now" in jsx and "left of about" in jsx
    assert "<Phases phases={d.phases} />" in (REPO / "services/web/src/TestRuns.jsx").read_text()
    assert "<Phases phases={s.phases} />" in (REPO / "services/web/src/TestWatch.jsx").read_text()
    assert ".test-phase-now .big { font-size: 56px" in (REPO / "services/web/src/styles.css").read_text()
    assert '"phases": phases(conn, run)' in (REPO / "services/api/eax/testing/store.py").read_text()
    assert '"phases": store.phases(conn, run)' in (REPO / "services/api/eax/testing/live.py").read_text()
