"""D825: one summary page for the full test, its summaries kept in the database, and the detailed files deletable from
the web, the command line and the Command centre's Scheduled upkeep (owner, 21 Nov 2026: "Please add them in one summary
page for anyone to check. We also need the ability to only keep summary in a DB table or something and delete detailed
result files form UI or command line. Please also build that"; 13:30: "In the regular mantiance tab please add ability
to clean up logs and all these test result files etc").

Before: the full test ended with a list of its steps in the terminal only; each step's figures were in its own files,
and deleting a run's files (eax test delete) deleted its results and record too. After: a page with a card a step, its
figures kept as a row (tests.full_tests) and in each run's row (tests.test_runs.summary); eax test prune, the Self-test
page's "Keep summary only" and the Scheduled upkeep's clean-up delete only the files."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eax.testing import full_tests, run_summary  # noqa: E402


def _ops(name: str):
    spec = importlib.util.spec_from_file_location(f"ops_{name}_d825", REPO / f"services/ops/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _w(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------- a run's summary
def test_a_runs_summary_holds_its_figures_never_its_lines(tmp_path):
    _w(tmp_path / "coverage.json", {"percent": 71.26, "live": 55.0, "unit": 64.4, "goal": 90, "lines": 1000, "run": 713,
                                    "joined": True, "files": {"eax/x.py": [1, 2, 3]}})
    _w(tmp_path / "security-findings.json", {
        "findings": [{"source": "nuclei", "severity": "low", "id": "a", "where": ""},
                     {"source": "nuclei", "severity": "low", "id": "b", "where": ""},
                     {"source": "trivy", "severity": "high", "id": "c", "where": ""}],
        "gate": {"failing": [{"id": "c"}], "accepted": [{}, {}], "expired": [], "no_fix": [{}]}, "new": [{}]})
    _w(tmp_path / "attack-tools.json", {"tools": {"nuclei": {"pulled": True, "present": True, "created": "2026-11-20T10:00:00Z"},
                                                  "zap": {"pulled": False, "present": True}}})
    detail = {"run": {"id": 12, "folder": "20261121T084649Z", "state": "failed", "suites": ["api", "attack"]},
              "tally": {"passed": 10, "failed": 2, "warning": 1, "skipped": 0},
              "health": {"health": "amber", "reason": "2 non-critical failed",
                         "suites": {"api": {"passed": 10, "failed": 2, "warning": 1, "skipped": 0}}}}
    s = run_summary.make(detail, tmp_path)
    assert s["run"] == 12 and s["tally"]["failed"] == 2 and s["health"] == "amber"
    assert s["coverage"] == {"percent": 71.3, "live": 55.0, "unit": 64.4, "goal": 90.0, "lines": 1000, "run": 713, "joined": True}
    assert "files" not in json.dumps(s)                               # which lines ran stays out: a few kilobytes
    assert s["security"]["failing"] == 1 and s["security"]["accepted"] == 2 and s["security"]["new"] == 1
    assert s["attack"]["findings"] == {"nuclei": {"low": 2}}          # only the attack test's own scanners
    assert s["attack"]["tools"]["zap"]["pulled"] is False


def test_a_run_with_no_files_still_has_a_summary():
    s = run_summary.make({"run": {"id": 3}, "tally": {}, "health": {}}, None)
    assert s["coverage"] is None and s["security"] is None and s["attack"] is None and s["tally"]["passed"] == 0


def test_the_runner_keeps_the_summary_at_the_end_of_every_run():
    src = (REPO / "services/api/eax/testing/run.py").read_text(encoding="utf-8")
    assert "run_summary.save(conn, r.id, run_summary.make(store.run_detail(conn, r.id, \"none\"), r.dir), r.dir)" in src


# ---------------------------------------------------------------- the database
def test_the_migration_adds_the_summary_columns_and_the_full_tests_table():
    sql = (REPO / "services/api/migrations/sql/0111_test_summaries.sql").read_text(encoding="utf-8")
    for x in ("summary          jsonb", "files_deleted_at timestamptz", "CREATE TABLE IF NOT EXISTS tests.full_tests",
              "folder ~ '^full-"):
        assert x in sql
    assert "FUNCTION" not in sql.upper() and "TRIGGER" not in sql.upper()     # no logic in the database (D248)
    py = (REPO / "services/api/migrations/versions/0111_test_summaries.py").read_text(encoding="utf-8")
    assert 'down_revision = "0110_selftest_attack_suite"' in py and "DROP TABLE IF EXISTS tests.full_tests" in py


def test_a_full_tests_summary_is_checked_before_it_is_kept():
    with pytest.raises(ValueError):
        full_tests.clean({"folder": "../etc"})
    s = full_tests.clean({"folder": "full-20261121T120000Z",
                          "details": ["20261121T110000Z", "sonar-1", "../x", "a/b", "full-20261120T000000Z", 3]})
    assert s["details"] == ["20261121T110000Z", "sonar-1"]


@pytest.mark.parametrize("which", ["bogus", "12a", "full-x", "../1"])
def test_prune_takes_a_run_a_full_test_or_all(which):
    with pytest.raises(ValueError):
        full_tests.pick(None, which)
    with pytest.raises(ValueError):
        full_tests.pick(None, "")
    with pytest.raises(ValueError):
        full_tests.pick(None, "all", 0)


class _Res:
    def __init__(self, rows=None, n=0):
        self.rows, self.rowcount = rows or [], n

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class _Conn:
    def __init__(self, runs):
        self.runs, self.sql = runs, []

    def execute(self, stmt, params=None):
        q = str(stmt)
        self.sql.append((q, params))
        if q.startswith("SELECT state"):
            r = self.runs.get(params["id"])
            return _Res([r] if r else [])
        if "screenshot = NULL" in q:
            return _Res(n=4)
        return _Res(n=1)


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        yield self.conn


def test_prune_deletes_only_the_files_and_marks_what_went(monkeypatch):
    monkeypatch.setattr(full_tests, "text", lambda q: q)                 # the SQL as written, whatever sqlalchemy is here
    conn = _Conn({5: {"state": "passed", "folder": "20261121T110000Z", "files_deleted_at": None},
                  6: {"state": "running", "folder": "20261121T120000Z", "files_deleted_at": None}})
    picked = {"runs": [{"id": 6, "folder": "20261121T120000Z"}],
              "fulls": [{"id": 2, "folder": "full-20261121T130000Z", "run_id": 5,
                         "summary": {"details": ["20261121T110000Z", "sonar-20261121T125000Z", "dev-check-x.log", "../no"]}}],
              "loose": ["backup-restore-20261101T000000Z", "../nope"]}
    asked = []
    out = full_tests.prune(_Engine(conn), picked, "admin", lambda names: asked.append(names) or {"removed": names, "left": []})
    assert asked == [["backup-restore-20261101T000000Z", "20261121T110000Z", "sonar-20261121T125000Z", "dev-check-x.log"]]
    assert out["runs"] == 1 and out["fulls"] == 1 and out["screenshots"] == 4
    assert any("run 6 is still going" in n for n in out["notes"])          # a run going on keeps its files
    sql = " ".join(q for q, _p in conn.sql)
    assert "DELETE FROM" not in sql.upper()                               # the rows and results stay
    assert "files_deleted_at = now()" in sql and "UPDATE tests.full_tests" in sql
    assert "summaries, counts and results stay" in full_tests.message(out)


def test_the_steps_run_by_themselves_are_found_by_age(tmp_path):
    for name in ("sonar-old", "sonar-new", "backup-restore-old", "dev-check-old.log", "sonar", "unit-coverage.json",
                 "20261121T110000Z", "full-20261121T130000Z"):
        p = tmp_path / name
        p.mkdir() if "." not in name else p.write_text("x")
        if "old" in name:
            os.utime(p, (time.time() - 30 * 86400, time.time() - 30 * 86400))
    assert full_tests.loose(tmp_path, 14) == ["backup-restore-old", "dev-check-old.log", "sonar-old"]
    assert "sonar" not in full_tests.loose(tmp_path)                       # SonarQube's own password folder stays
    assert "unit-coverage.json" not in full_tests.loose(tmp_path)          # the next full test joins it
    assert full_tests.loose(tmp_path / "missing") == []


def test_the_helper_removes_a_file_or_a_folder_under_work_tests_only(tmp_path, monkeypatch):
    T = _ops("testruns")
    monkeypatch.setattr(T, "WORK", str(tmp_path))
    (tmp_path / "tests" / "sonar-1").mkdir(parents=True)
    (tmp_path / "tests" / "dev-check-1.log").write_text("x")
    (tmp_path / "keep.txt").write_text("x")
    out = T.delete_results(["sonar-1", "dev-check-1.log", "..", ".", "../keep.txt"])
    assert out["removed"] == ["sonar-1", "dev-check-1.log"] and set(out["left"]) == {"..", ".", "../keep.txt"}
    assert (tmp_path / "keep.txt").exists()


# ---------------------------------------------------------------- the summary page
def _full_folder(tmp_path: Path) -> Path:
    t = tmp_path / "tests"
    _w(t / "dev-check-20261121-120000.json", {"log": "dev-check-20261121-120000.log", "passed": True,
                                              "coverage": {"percent": 64.4, "lines": 900, "run": 580},
                                              "steps": [{"title": "lint", "passed": True, "why": ""}]})
    _w(t / "20261121T121000Z" / "summary.json", {
        "run": 14, "state": "failed", "tally": {"passed": 900, "failed": 3, "warning": 5, "skipped": 2},
        "health": "amber", "reason": "3 non-critical", "by_suite": {"api": {"passed": 900, "failed": 3, "warning": 5}},
        "coverage": {"percent": 82.5, "live": 70.1, "unit": 64.4, "goal": 90, "lines": 1000, "run": 825},
        "security": {"findings": 4, "failing": 0, "accepted": 4, "expired": 0, "no_fix": 0, "new": 0},
        "attack": {"tools": {"zap": {"pulled": True, "present": True}}, "findings": {"nuclei": {"low": 10}}}})
    _w(t / "backup-restore-20261121T130000Z" / "report.json", {"passed": False, "results": [
        {"name": "B1 taken", "ok": True}, {"name": "B2 restored: files", "ok": False}, {"name": "skipped", "ok": None}]})
    _w(t / "sonar-20261121T140000Z" / "summary.json", {"passed": True, "to_fix": 0, "issues": 12, "hotspots": 2,
                                                       "accepted": 14, "by_severity": {"MAJOR": 12}})
    old = _w(t / "sonar-20261101T000000Z" / "summary.json", {"passed": False})
    os.utime(old.parent, (time.time() - 86400 * 20, time.time() - 86400 * 20))
    return t


def test_the_summary_page_has_a_card_a_step_from_their_own_files(tmp_path):
    from eaxcli import fullreport as F
    t = _full_folder(tmp_path)
    steps = [("dev check", True, ""), ("self-test", False, "ended with 1"), ("backup and restore test", False, "ended with 1"),
             ("SonarQube scan", True, "")]
    s = F.gather(t, time.time() - 3600, steps, version="7.9.0", by="gaura")
    assert s["passed"] is False and [x["kind"] for x in s["steps"]] == ["dev", "selftest", "backup", "sonar"]
    assert s["selftest"]["folder"] == "20261121T121000Z" and s["selftest"]["coverage"]["percent"] == 82.5
    assert s["backup"] == {"folder": "backup-restore-20261121T130000Z", "passed": False, "checks": 3, "failed": 1,
                           "failures": ["B2 restored: files"]}
    assert s["sonar"]["folder"] == "sonar-20261121T140000Z"               # this test's scan, not an older one
    assert set(s["details"]) == {"dev-check-20261121-120000.json", "dev-check-20261121-120000.log", "20261121T121000Z",
                                 "backup-restore-20261121T130000Z", "sonar-20261121T140000Z"}
    folder = F.write(t, s)
    page = (folder / "index.html").read_text(encoding="utf-8")
    for card in ("Dev check", "Code coverage", "Self-test", "Security gate", "Attack test", "Backup and restore", "SonarQube"):
        assert f"<h2>{card}" in page
    assert 'aria-label="our code: 82.5% of the lines run, goal 90%"' in page
    assert 'href="../20261121T121000Z/report.html"' in page and 'href="../sonar-20261121T140000Z/report.md"' in page
    assert "<script" not in page and "http" not in page                   # nothing from outside: it opens anywhere
    assert json.loads((folder / "summary.json").read_text(encoding="utf-8"))["folder"] == folder.name
    assert full_tests.clean(s)["folder"] == folder.name                   # what the database keeps


def test_a_step_that_wrote_nothing_still_shows_why(tmp_path):
    from eaxcli import fullreport as F
    s = F.gather(tmp_path / "none", time.time(), [("SonarQube scan", False, "Docker refused")])
    page = F.page(s)
    assert "Docker refused" in page and "no figure" in page


def test_the_full_test_ends_with_the_page_and_keeps_it(tmp_path, monkeypatch):
    from eaxcli import main as M
    t = _full_folder(tmp_path)
    monkeypatch.setattr(M, "WORK", tmp_path)
    monkeypatch.setattr(M, "version", lambda: "7.9.0")
    kept = []
    code = M.full_summary([("dev check", True, "")], time.time() - 3600, keep=kept.append)
    assert code == 0 and len(kept) == 1 and (t / kept[0] / "index.html").is_file()
    assert M.full_summary([("dev check", False, "x")]) == 1             # no page without began: the old list only
    src = (REPO / "eaxcli/main.py").read_text(encoding="utf-8")
    assert "return full_summary(steps, began)" in src and '"eax.testing.cli", "full-save"' in src


def test_a_page_that_cannot_be_kept_never_fails_the_full_test(tmp_path, monkeypatch):
    from eaxcli import main as M
    monkeypatch.setattr(M, "WORK", tmp_path)
    monkeypatch.setattr(M, "version", lambda: "7.9.0")

    def broken(_f):
        raise RuntimeError("the api is down")
    assert M.full_summary([("self-test", True, "")], time.time(), keep=broken) == 0


def test_the_dev_check_writes_its_figures_beside_its_log(tmp_path):
    from eaxcli import dev_cli as D
    log = tmp_path / "dev-check-20261121-120000.log"
    log.write_text("x")
    unit = _w(tmp_path / "unit.json", {"totals": {"percent_covered": 64.44, "num_statements": 900, "covered_lines": 580}})
    out = D.save_summary(log, [("lint", True, ""), ("tests", False, "2 failed")], unit)
    d = json.loads(out.read_text(encoding="utf-8"))
    assert out.name == "dev-check-20261121-120000.json" and d["passed"] is False and d["log"] == log.name
    assert d["coverage"] == {"percent": 64.4, "lines": 900, "run": 580} and d["steps"][1]["why"] == "2 failed"
    assert json.loads(D.save_summary(log, [], tmp_path / "missing").read_text())["coverage"] is None


# ---------------------------------------------------------------- the command line
class _TEng:
    @contextmanager
    def connect(self):
        yield None


def test_the_command_line_checks_what_it_is_given():
    from eax.testing import cli
    said = []
    assert cli.summaries("full-save", ["../x"], out=said.append, teng=_TEng()) == 2
    assert cli.summaries("prune", ["bogus"], out=said.append, teng=_TEng()) == 2
    assert cli.summaries("prune", ["--older-than", "x"], out=said.append, teng=_TEng()) == 2
    assert any("eax test prune <run|full-N|all>" in s for s in said)


def test_prune_and_summary_are_eax_commands_everywhere():
    help_ = (REPO / "eaxcli/help.txt").read_text(encoding="utf-8")
    assert "|prune <run|full-N|all> [--older-than DAYS]|summary [full-N]|" in help_
    assert "  prune   deletes only the detailed files" in help_ and "$ {eax} test prune --older-than 14" in help_
    help_.encode("ascii")
    ps1 = (REPO / "eax.ps1").read_bytes().decode("ascii")
    assert '$RestArgs[0] -eq "prune" -or $RestArgs[0] -eq "summary"' in ps1
    sh = (REPO / "eax.sh").read_text(encoding="utf-8")
    assert '[ "${1:-}" = "prune" ] || [ "${1:-}" = "summary" ]' in sh
    main = (REPO / "eaxcli/main.py").read_text(encoding="utf-8")
    assert 'rest[:1] in (["prune"], ["summary"])' in main
    cmds = (REPO / "eaxcli/commands.py").read_text(encoding="utf-8")
    assert '"delete", "prune", "summary"' in cmds


# ---------------------------------------------------------------- the web
def test_the_api_has_the_summaries_and_prune():
    src = (REPO / "services/api/eax/api/platform_tests.py").read_text(encoding="utf-8")
    for route in ('"/tests/prune"', '"/tests/full"', '"/tests/full/<int:full_id>"', '"/tests/full/<int:full_id>/page"'):
        assert f"@blp.route({route})" in src
    assert 'action="selftest.prune"' in src                              # in the audit trail


def test_the_self_test_page_has_the_summary_and_keep_summary_only():
    runs = (REPO / "services/web/src/TestRuns.jsx").read_text(encoding="utf-8")
    assert '["summary", "Summary"]' in runs and "<FullSummary onOpen={setOpen} />" in runs
    assert "Keep summary only" in runs and "Delete the detailed files, keep the summaries..." in runs
    page = (REPO / "services/web/src/FullSummary.jsx").read_text(encoding="utf-8")
    for x in ("/api/v1/admin/tests/full", "<Ring percent={cov.percent}", "Attack test", "SonarQube", "Keep the summary only..."):
        assert x in page


def test_scheduled_upkeep_cleans_up_the_logs_and_the_test_files():
    sys.path.insert(0, str(REPO / "services" / "ops"))
    import commandcentre as CC
    s = next(x for x in CC.SYSTEM_SCHEDULES if x["id"] == "r12tests")
    assert s["enabled"] is False and s["argv"] == ["test", "prune", "--older-than", "14", "--yes"]   # off until chosen
    up = (REPO / "services/web/src/Upkeep.jsx").read_text(encoding="utf-8")
    assert "export function CleanUp()" in up and "schedules/r12tests/" in up
    for url in ("/api/v1/admin/logs/clean", "/api/v1/admin/tests/prune", "/api/v1/admin/tests/delete"):
        assert url in up
    assert "<UpkeepChoices cleanup />" in (REPO / "services/web/src/CommandCentre.jsx").read_text(encoding="utf-8")
