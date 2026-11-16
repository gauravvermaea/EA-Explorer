"""R5.48 (owner, 16 Nov 2026, 10:09: "the database is at the API's version: the API is 5.1.0; the database has 3.5.0,
4.0.0, 5.0.0. AS A BUG"; 10:10: "A mismatch should show on screen on startup").

The installation had been rebuilt at 09:25 from code still at 5.0.0 (migrations to 0091); the version moved to 5.1.0
after it, and the self-test's runner, built from the newer code, compared the database with its own version, not the
installation's. Now: (1) the database is checked against the running API's version, and a runner built from code other
than what runs fails a check of its own that says to rebuild; (2) the start-up status has a Versions row: down when the
API and its database differ, a warning when the code on this machine is not what runs, shown on the chip."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import startup_status as ss  # noqa: E402

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]


def test_all_agree_is_up():
    p = ss.version_part("5.1.0", "5.1.0", "5.1.0")
    assert p["status"] == "up" and p["key"] == "version" and "API 5.1.0, database 5.1.0" in p["detail"]


def test_api_and_database_differ_is_down():
    p = ss.version_part("5.1.0", "5.0.0", "5.1.0")
    assert p["status"] == "down" and "do not match" in p["detail"] and "clean-restart" in p["detail"]


def test_code_newer_than_what_runs_is_a_warning():
    p = ss.version_part("5.0.0", "5.0.0", "5.1.0")
    assert p["status"] == "warning" and "code on this machine 5.1.0" in p["detail"] and "not what runs" in p["detail"]


def test_a_warning_does_not_hold_up_everything_up_but_shows():
    data = {"parts": [{"key": "reports", "status": "up"}], "later": None, "packs": None,
            "version": ss.version_part("5.0.0", "5.0.0", "5.1.0")}
    out = ss._finish(data)
    assert out["overall"] == "up" and any(p["key"] == "version" for p in out["all"])   # eax up --wait-all still ends
    down = ss._finish({"parts": [], "version": ss.version_part("5.1.0", "5.0.0", None)})
    assert down["overall"] == "down"
    web = (REPO / "services" / "web" / "src" / "StartupStatus.jsx").read_text(encoding="utf-8")
    assert 'warning: "amber"' in web and 'p.status === "warning"' in web


def test_the_unsigned_status_shows_no_versions():
    src = (API / "eax" / "api" / "startup.py").read_text()
    assert '[{"key": p["key"], "status": p["status"]} for p in out["all"]]' in src


def test_the_operations_helper_reads_the_codes_version(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "services" / "ops"))
    import importlib
    ops = importlib.import_module("ops")
    (tmp_path / "services" / "api").mkdir(parents=True)
    (tmp_path / "services" / "api" / "version.toml").write_text('# x\nversion = "5.1.0"\n')
    monkeypatch.setattr(ops, "REPO", str(tmp_path))
    assert ops.code_version() == "5.1.0"
    assert '"code_version": code_version()' in (REPO / "services" / "ops" / "ops.py").read_text()


def test_the_self_test_checks_the_running_version():
    run = (API / "eax" / "testing" / "run.py").read_text()
    assert run.count("_version_checks(conn, r.recorder(\"db\"))") == 2 and "db_checks.run(conn, _version()" not in run
    assert '/api/v1/operations/health"' in run and "the test runner is the installation's version" in run
