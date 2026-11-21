"""D800: SQL built from text is accepted for good (owner, 19 Nov 2026, 18:24: "SQL built from text is ok with what we
want to do, so ignore them all"): bandit B608 and SonarQube python:S2077 no longer count against a run; everything
else still does."""

from __future__ import annotations

import json
from pathlib import Path

from eax.testing import codescan, security_gate, sonar

HERE = Path(security_gate.__file__).resolve().parent


def _bandit(test_id: str, severity: str = "MEDIUM") -> dict:
    return {"test_id": test_id, "issue_severity": severity, "issue_confidence": "MEDIUM", "issue_text": "x",
            "filename": "/app/eax/reports.py", "line_number": 10}


def test_bandit_sql_from_text_is_accepted_and_nothing_else_is():
    # before: with no acceptance, B608 is a finding like any other
    assert not codescan.bandit_accepted(_bandit("B608"), accept=[])
    # after: the written acceptance covers B608, and only B608
    assert codescan.bandit_accepted(_bandit("B608"))
    assert not codescan.bandit_accepted(_bandit("B110", "LOW"))
    assert not codescan.bandit_accepted(_bandit("B310"))


def test_the_code_scan_line_leaves_out_accepted_sql_from_text(tmp_path, monkeypatch):
    data = {"results": [_bandit("B608"), _bandit("B608"), _bandit("B310")]}
    monkeypatch.setattr(codescan, "bandit", lambda root, out: data)
    monkeypatch.setattr(codescan, "secrets", lambda root: [])
    monkeypatch.setattr(codescan, "licences", lambda: [])
    got = {}
    codescan.run(tmp_path, tmp_path, lambda name, status, detail, ms: got.setdefault(name, (status, detail)))
    status, detail = got["code: Python static analysis (bandit)"]
    assert status == "warning" and detail.startswith("0 high, 1 medium (2 accepted in writing)")


def test_sonar_formatting_sql_is_accepted_everywhere_and_other_rules_are_not():
    accepted = sonar.accepted_list()
    hotspot = {"ruleKey": "python:S2077", "component": "eax:services/api/eax/reports.py", "line": 12}
    assert sonar.is_accepted(hotspot, []) is None                 # before
    assert sonar.is_accepted(hotspot, accepted) is not None       # after
    assert sonar.is_accepted({"rule": "python:S1192", "component": "eax:services/api/eax/reports.py"}, accepted) is None


def test_both_acceptances_carry_the_owners_words():
    for name, key in (("security_accepted.json", "id"), ("sonar_accepted.json", "rule")):
        rows = json.loads((HERE / name).read_text(encoding="utf-8"))["accepted"]
        sql = [r for r in rows if r[key] in ("bandit:B608", "python:S2077")]
        assert sql and all("D800" in r["by"] and r["reason"] for r in sql)
