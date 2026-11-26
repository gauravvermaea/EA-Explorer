"""D947: a failed browser step says what the database was busy with (run 20, 26 Nov 2026: the project page stayed on
"Loading..." for 25 s while the API answered its health check, which reads no database, at once)."""

from __future__ import annotations

import inspect

from eax.testing import run, ui_flows


class Conn:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        self.sql, self.params = str(sql), params
        return type("R", (), {"mappings": lambda _s: type("M", (), {"all": lambda _m: self.rows})()})()


class Engine:
    def __init__(self, rows):
        self.rows = rows

    def connect(self):
        return Conn(self.rows)


def test_what_waits_and_on_whom():
    rows = [{"pid": 41, "app": "", "waits": "Lock:relation", "secs": 24.8, "blocked_by": [77],
             "query": "SELECT m.guid::text AS id, m.name FROM core.models m"},
            {"pid": 77, "app": "procrastinate", "waits": "running", "secs": 61.0, "blocked_by": [], "query": "INSERT INTO core.entities"}]
    said = run.db_waits(Engine(rows))()
    assert said.startswith(" · the database: 24.8 s Lock:relation blocked by [77] [41] SELECT m.guid")
    assert "61.0 s running [77 procrastinate] INSERT INTO core.entities" in said


def test_nothing_slow_is_said_too():
    assert run.db_waits(Engine([]))() == " · the database: nothing running longer than 2 s"


def test_a_failed_look_says_nothing(monkeypatch):
    def boom():
        raise RuntimeError("no database")
    monkeypatch.setattr(ui_flows, "DB_LOOK", boom)
    assert ui_flows._db_says() == ""
    monkeypatch.setattr(ui_flows, "DB_LOOK", None)
    assert ui_flows._db_says() == ""


def test_the_run_sets_it_and_a_failed_step_says_it():
    assert "_uf.DB_LOOK = db_waits(repo)" in inspect.getsource(run.cmd_run)
    assert "{_api_answers(state.get('tab') or page)}{_db_says()}" in inspect.getsource(ui_flows)
