"""R5.29 (owner, 15 Nov 2026, 19:22: "I dont want full test to run performance test please ensure this"): the full test
(eax test full, the Self-test page's Full test, "all") runs every suite but performance; performance runs only when
asked for by name (eax test performance) and in CI's nightly job. Security stays in the full test."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax.testing import FULL_SUITES, ON_DEMAND, SUITES, WEB_FULL_SUITES, store  # noqa: E402


def _ops_testruns():
    spec = importlib.util.spec_from_file_location("ops_testruns_r529", REPO / "services/ops/testruns.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_full_test_has_every_suite_but_performance():
    assert ON_DEMAND == ("performance",) and "performance" in SUITES
    assert "performance" not in FULL_SUITES and "performance" not in WEB_FULL_SUITES
    assert {"api", "ui", "db", "security", "reports", "backup"} <= set(FULL_SUITES)       # security stays in it
    assert store.clean_suites(None) == list(FULL_SUITES) and store.clean_suites("all") == list(FULL_SUITES)
    assert store.clean_suites("performance") == ["performance"]                          # by name, it runs


def test_the_helper_s_full_test_too():
    ops = _ops_testruns()
    assert "performance" not in ops.suites_of(None) and "performance" not in ops.suites_of("all")
    assert "security" in ops.suites_of("all") and ops.suites_of("performance") == ["performance"]
    src = (REPO / "services/ops/testruns.py").read_text()
    assert 'run_sequence("smoke", list(FULL_SUITES)' in src


def test_the_self_test_page_s_full_test_leaves_it_out():
    jsx = (REPO / "services/web/src/TestRuns.jsx").read_text()
    perf = next(line for line in jsx.splitlines() if line.strip().startswith('["performance"'))
    assert perf.rstrip().endswith("true],")                                             # marked: on demand
    assert 'suites: SUITES.filter((x) => !x[3]).map(([k]) => k)' in jsx
    assert "part of full, R5.18" not in (REPO / "eaxcli/help.txt").read_text()
