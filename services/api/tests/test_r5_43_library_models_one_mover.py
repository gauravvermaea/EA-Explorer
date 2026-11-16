"""R5.43: sample data showed "down" with UniqueViolation on layers_pkey (owner, 16 Nov 2026, 07:58). The start-up step
"Library models into their schema" and the five-minute job eax.library_models_move moved the same models at the same
moment (the API's log, 05:26:36 and 05:26:45). Now one mover at a time: the second waits, then finds what is left."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import db  # noqa: E402
from eax import library_models as lm

said = []


class Conn:
    def __init__(self):
        self.opts = {}

    def execution_options(self, **kw):
        self.opts.update(kw)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "advisory" in sql:
            said.append(("unlock" if "unlock" in sql else "lock", self.opts.get("isolation_level")))


class Engine:
    def connect(self):
        return Conn()

    def begin(self):
        return Conn()


def test_one_mover_at_a_time(monkeypatch):
    said.clear()
    monkeypatch.setattr(db, "base_engine", lambda: Engine())
    monkeypatch.setattr(db, "installer_engine", lambda: Engine())
    monkeypatch.setattr(lm, "waiting", lambda c: said.append(("waiting", None)) or [])
    monkeypatch.setattr(lm, "drop_core_history", lambda c: 0)
    lm.move_all()
    assert [s[0] for s in said] == ["lock", "waiting", "unlock"]
    assert said[0][1] == "AUTOCOMMIT"


def test_the_lock_goes_back_when_the_move_fails(monkeypatch):
    said.clear()
    monkeypatch.setattr(db, "base_engine", lambda: Engine())
    monkeypatch.setattr(lm, "_move_all", lambda p, b: (_ for _ in ()).throw(RuntimeError("failed")))
    try:
        lm.move_all()
    except RuntimeError:
        pass
    assert [s[0] for s in said] == ["lock", "unlock"]
