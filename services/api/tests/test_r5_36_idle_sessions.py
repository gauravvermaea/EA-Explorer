"""R5.36 (owner, 15 Nov 2026, 22:25: "sample data doesnt seem to be loading and I cant see projects I can see models is
this working ?"). The API's log: at 20:16:07, 20:20:25 and 20:25:04, just as eax.db_idle_sessions ran, every database
connection ended with "terminating connection due to administrator command", the sample data's loader among them. The
job's query put pg_terminate_backend(pid) in its WHERE: PostgreSQL may call it before testing the other conditions, so
it ended every session on the server, of every database, its own included."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import dbmaint  # noqa: E402


class Cur:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0]


class Conn:
    def __init__(self):
        self.sql = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        return Cur([(101,), (102,)]) if "FROM pg_stat_activity" in sql else Cur([(True,)])


def test_the_sessions_are_chosen_first_then_ended_one_by_one(monkeypatch):
    c = Conn()
    monkeypatch.setattr(dbmaint, "connect", lambda name: c)
    assert dbmaint.end_idle(30) == [101, 102]
    choose, params = c.sql[0]
    assert "pg_terminate_backend" not in choose and params == (30,)        # never in the WHERE again
    assert "datname = current_database()" in choose and "backend_type = 'client backend'" in choose
    assert "state = 'idle in transaction'" in choose and "pid <> pg_backend_pid()" in choose
    assert [s for s, _ in c.sql[1:]] == ["SELECT pg_terminate_backend(%s)"] * 2
    assert [p for _, p in c.sql[1:]] == [(101,), (102,)]


def test_off_ends_nothing(monkeypatch):
    monkeypatch.setattr(dbmaint, "connect", lambda name: (_ for _ in ()).throw(AssertionError("no connection")))
    assert dbmaint.end_idle(0) == []
