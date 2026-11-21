"""D823: what the first attack test (21 Nov 2026) found and could be fixed without changing anything people see.

  nan-injection    System Admin's resource history took ?days=nan or inf: now a 400 with what is wanted
  tainted env      eax's menu ran whatever EAX_FORM_EXE named: now only PowerShell, as eax.ps1 sets it
  defused XML      the attack test's own reading of Schemathesis' JUnit report: defusedxml, not the standard parser
  dulwich          1.2.5 or later (PYSEC-2026-2462 to 2466 and the GHSAs pip-audit and Trivy found)"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "services/api"))


def test_the_resource_history_refuses_nan_and_inf():
    src = (REPO / "services/api/eax/api/admin.py").read_text(encoding="utf-8")
    body = src.split('days = float(request.args.get("days") or 1)', 1)[1][:400]
    assert "if not (math.isfinite(days) and days > 0):" in body and 'raise ValueError("days: a number of days greater than 0.")' in body
    assert "\nimport math\n" in src
    import math
    for bad in ("nan", "inf", "-inf", "0", "-3"):
        d = float(bad)
        assert not (math.isfinite(d) and d > 0), bad
    assert math.isfinite(float("1.5")) and float("1.5") > 0


def test_the_menu_runs_only_powershell(monkeypatch):
    from eaxcli import menu
    ran = []
    monkeypatch.setattr(subprocess, "call", lambda args, **k: ran.append(args) or 0)
    monkeypatch.setenv("EAX_FORM", "ps1")
    for exe, want in ((r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
                      ("/usr/bin/pwsh", "/usr/bin/pwsh"), (r"C:\evil\payload.exe", "powershell"), ("rm", "powershell")):
        monkeypatch.setenv("EAX_FORM_EXE", exe)
        ran.clear()
        menu.run(["status"])
        assert ran and ran[0][0] == want, exe


def test_the_junit_report_is_read_with_defusedxml(tmp_path):
    src = (REPO / "services/api/eax/testing/security_gate.py").read_text(encoding="utf-8")
    assert "from defusedxml import ElementTree as ET" in src and "xml.etree.ElementTree" not in src
    from eax.testing import security_gate
    (tmp_path / "schemathesis").mkdir()
    bomb = ('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
            '<testsuites><testcase name="x"><failure message="&b;"/></testcase></testsuites>')
    (tmp_path / "schemathesis" / "bomb.xml").write_text(bomb)
    (tmp_path / "schemathesis" / "ok.xml").write_text('<testsuites><testcase name="GET /a"><failure message="Server error"/></testcase></testsuites>')
    got = security_gate.from_junit(tmp_path)
    assert [x["where"] for x in got] == ["GET /a"]                      # the entity bomb refused, the real one read


def test_dulwich_at_a_fixed_version():
    req = (REPO / "services/api/requirements.txt").read_text(encoding="utf-8")
    assert "\ndulwich>=1.2.5,<2" in req and "dulwich>=0.22,<1" not in req
