"""R5.38: the industry packs showed "down" with AdminShutdown on pg_advisory_unlock (owner, 15 Nov 2026, 23:22, "Got
this error in the end"). The loader held its lock on a connection left idle in a transaction for the whole load; the
start-up load has no time budget and ran for about an hour, so database maintenance ended it after 30 minutes and the
unlock at the end failed although every file had loaded."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import industry_packs as ip  # noqa: E402


class LockConn:
    def __init__(self, unlock_fails=False):
        self.options, self.unlock_fails = {}, unlock_fails

    def execution_options(self, **kw):
        self.options.update(kw)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "pg_advisory_unlock" in sql and self.unlock_fails:
            raise RuntimeError("terminating connection due to administrator command")

        class R:
            def scalar(self_inner):
                return True
        return R()

    def commit(self):
        pass


class Engine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn

    def begin(self):
        return self.conn


def _quiet(monkeypatch, tmp_path):
    from eax import mayan
    monkeypatch.setattr(ip, "PACKS_DIR", tmp_path)
    monkeypatch.setattr(mayan, "enabled", lambda: True)
    monkeypatch.setattr(mayan, "ping", lambda: True)
    monkeypatch.setattr(ip, "_part", lambda *a, **k: None)
    monkeypatch.setattr(ip, "load_folder", lambda *a, **k: {"total": 3, "failed": [], "refused": [], "left": []})


def test_the_lock_connection_is_never_idle_in_a_transaction(monkeypatch, tmp_path):
    _quiet(monkeypatch, tmp_path)
    conn = LockConn()
    ip.load_shipped_each(engine=Engine(conn))
    assert conn.options.get("isolation_level") == "AUTOCOMMIT"


def test_a_lost_lock_connection_does_not_fail_the_packs(monkeypatch, tmp_path):
    _quiet(monkeypatch, tmp_path)
    out = ip.load_shipped_each(engine=Engine(LockConn(unlock_fails=True)))
    assert out["total"] == 3 and not out["failed"]
