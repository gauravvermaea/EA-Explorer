"""Every self-test suite is allowed by the tests database (owner, 16 Nov 2026, 14:11: a run from the UI answered "A
server error (IntegrityError)", and from the command line the test ended with exit 1: the MCP suite was added to the
code but not to the constraint on tests.test_runs.suites). This test fails whenever a suite is added without its
migration."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
SQL = Path(__file__).resolve().parents[1] / "migrations" / "sql"


def _newest(constraint: str) -> str:
    files = sorted(f for f in SQL.glob("*.sql") if f"ADD CONSTRAINT {constraint}" in f.read_text(encoding="utf-8"))
    return files[-1].read_text(encoding="utf-8")


def test_every_suite_may_be_a_runs_suite_and_a_results_suite():
    from eax import testing
    runs = _newest("test_runs_suites_check")
    allowed = set(re.findall(r"'([a-z-]+)'", runs.split("ADD CONSTRAINT test_runs_suites_check", 1)[1].split(";", 1)[0]))
    assert set(testing.SUITES) <= allowed, f"not allowed for a run: {sorted(set(testing.SUITES) - allowed)}"
    results = _newest("test_results_suite_check")
    allowed_r = set(re.findall(r"'([a-z-]+)'", results.split("ADD CONSTRAINT test_results_suite_check", 1)[1].split(";", 1)[0]))
    assert set(testing.SUITES) | {"smoke"} <= allowed_r, f"not allowed for a result: {sorted(set(testing.SUITES) - allowed_r)}"
