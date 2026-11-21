"""R8.1, D807 (owner, 20 Nov 2026: "Both combined"): code coverage counts a line when either the live run (eax test full,
the API measured from inside) or the unit tests (eax dev check, pytest --cov) ran it; the goal is 90% (D802)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from eax import coverage_probe as P

ROOT = Path(__file__).resolve().parents[3]


def _report(files: dict) -> dict:
    """A coverage.py JSON report's files: {name: (executed, missing)}."""
    return {name: {"executed_lines": ran, "missing_lines": miss,
                   "summary": {"num_statements": len(ran) + len(miss), "covered_lines": len(ran)}}
            for name, (ran, miss) in files.items()}


def test_the_probe_keeps_which_lines_ran():
    s = P.summarise(_report({"/app/eax/a.py": ([1, 2], [3, 4])}))
    row = s["files"][0]
    assert row["file"] == "eax/a.py" and row["ran"] == [1, 2] and row["statements"] == [1, 2, 3, 4]
    assert s["percent"] == 50.0 and s["on"] is True


def test_a_line_counts_when_either_ran_it():
    live = P.summarise(_report({"/app/eax/a.py": ([1, 2], [3, 4]), "/app/eax/api/b.py": ([1], [2, 3, 4])}))
    unit = P.summarise(_report({"eax/a.py": ([3], [1, 2, 4]), "eax/api/b.py": ([1, 2, 3, 4], [])}))
    both = P.combine(live, unit)
    rows = {r["file"]: r for r in both["files"]}
    assert rows["eax/a.py"]["ran"] == [1, 2, 3] and rows["eax/api/b.py"]["run"] == 4
    assert both["run"] == 7 and both["lines"] == 8 and both["percent"] == 87.5      # before: live 37.5%, unit 62.5%
    assert both["live"] == 37.5 and both["unit"] == 62.5 and both["joined"] == 2 and both["not_joined"] == []
    assert {a["area"]: a["percent"] for a in both["areas"]} == {"core": 75.0, "api": 100.0}


def test_a_file_changed_between_the_two_is_not_joined():
    live = P.summarise(_report({"eax/a.py": ([1], [2, 3])}))
    unit = P.summarise(_report({"eax/a.py": ([1, 2, 3, 4], [])}))          # another version: 4 statements
    both = P.combine(live, unit)
    assert both["run"] == 1 and both["not_joined"] == ["eax/a.py"] and both["joined"] == 0


def test_code_only_the_unit_tests_loaded_counts_too():
    both = P.combine(P.summarise(_report({"eax/a.py": ([1], [2])})), P.summarise(_report({"eax/setup/x.py": ([1, 2], [3])})))
    assert {r["file"] for r in both["files"]} == {"eax/a.py", "eax/setup/x.py"} and both["lines"] == 5 and both["run"] == 3


def test_the_self_test_joins_the_last_dev_checks_figure(tmp_path):
    from eax.testing import run
    live = P.summarise(_report({"eax/a.py": ([1], [2, 3, 4])})) | {"scope": "full"}
    assert run.with_unit_tests(live, tmp_path) is live                         # none yet: the live run's alone
    raw = {"files": _report({"eax/a.py": ([2, 3], [1, 4])}), "totals": {}}
    (tmp_path / "unit-coverage.json").write_text(json.dumps(raw), encoding="utf-8")
    both = run.with_unit_tests(live, tmp_path)
    assert both["percent"] == 75.0 and both["live"] == 25.0 and both["unit"] == 50.0 and both["scope"] == "full"


def test_dev_check_measures_the_unit_tests_and_says_the_figure(tmp_path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import dev_cli as D
    steps = dict((t, c) for t, c, _w in D.commands(False, False, compose_args=lambda a: ["docker", "compose", *a]))
    assert steps["tests"][-3:] == ["--cov", "--cov-report", "json:/repo/work/tests/unit-coverage.json"]
    assert "--cov" not in steps["lint"]
    f = tmp_path / "u.json"
    f.write_text(json.dumps({"totals": {"percent_covered": 63.25, "num_statements": 1000}}), encoding="utf-8")
    assert D.unit_coverage(f).startswith("63.2% of 1000 lines") and D.unit_coverage(tmp_path / "none.json") == ""
    src = (ROOT / "eaxcli/dev_cli.py").read_text(encoding="utf-8")
    assert "(ROOT / UNIT_COVERAGE).unlink(missing_ok=True)" in src                  # never last time's figure
    pyproject = (ROOT / "services/api/pyproject.toml").read_text(encoding="utf-8")
    assert 'source = ["eax"]' in pyproject and 'omit = ["eax/testing/*"]' in pyproject   # the live run's code, the same
