"""R9.10: the DR drill as the last step of eax test full, and the full test from Jenkins.

The owner (Release 9): the restore drill runs at the end of the full test, after SonarQube (--no-dr leaves it out), in
fixed folders beside the installation; the smoke test runs on the DR copy; then the DR copy is stopped and kept and the
installation started again and signed in to, so the full test leaves the machine as it found it. The drill's report is a
card on the full test's summary page; the full test is an admin task in Jenkins (Upkeep), asked to be confirmed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import commands as C  # noqa: E402
from eaxcli import fullreport as F  # noqa: E402
from eaxcli import jenkins as J  # noqa: E402
from eaxcli import main as M  # noqa: E402

DR = REPO / "dr"
needs_bash = pytest.mark.skipif(not shutil.which("bash"), reason="bash is not here")


# ---------------------------------------------------------------- the step in eax test full
def test_the_drill_folders_sit_beside_the_installation_never_inside_it(tmp_path):
    inst = tmp_path / "EA-Enterpise"
    dr, temp = M.drill_folders(inst)
    assert dr == tmp_path / "EA-Enterpise-drill-dr" and temp == tmp_path / "EA-Enterpise-drill-temp"
    for p in (dr, temp):
        assert inst not in p.parents and p.parent == inst.parent


def test_the_full_tests_drill_runs_eax_drill_with_the_smoke_after_and_back_again(monkeypatch):
    seen = {}

    class R:
        returncode = 0

    def run(argv, **k):
        seen["argv"], seen["cwd"] = argv, k.get("cwd")
        return R()

    assert M.dr_drill(run) == 0
    a = seen["argv"]
    assert seen["cwd"] == M.ROOT
    joined = " ".join(a)
    assert "eax-drill" in joined
    if a[0].endswith(("pwsh", "pwsh.exe", "powershell", "powershell.exe")):
        assert "-SmokeAfter" in a and "-ThenBack" in a and "-Smoke" not in a
    else:
        assert a[0] == "bash" and "--smoke-after" in a and "--then-back" in a and "--smoke" not in a
    dr, temp = M.drill_folders()
    assert str(dr) in a and str(temp) in a and str(M.ROOT) in a

    class Bad:
        returncode = 1
    assert M.dr_drill(lambda *x, **k: Bad()) == 1


def test_the_drill_is_the_full_tests_last_step_after_sonarqube_and_no_dr_leaves_it_out():
    src = (REPO / "eaxcli" / "main.py").read_text(encoding="utf-8")
    full = src[src.index('no_sonar, no_dr = "--no-sonar" in rest, "--no-dr" in rest'):src.index("return full_summary(steps, began)")]
    assert full.index('"SonarQube scan"') < full.index('full_step("DR drill", dr_drill)')
    assert "if not no_dr and not part:" in full and '"--no-dr")]' in full            # never passed on to the self-test
    assert F.KINDS["DR drill"] == "dr"


def test_ps_options_are_named_as_the_powershell_drill_takes_them():
    assert J._ps_arg("--smoke-after") == "-SmokeAfter" and J._ps_arg("--then-back") == "-ThenBack"
    ps = (DR / "eax-drill.ps1").read_text(encoding="utf-8")
    assert "[switch]$SmokeAfter" in ps and "[switch]$ThenBack" in ps
    assert all(ord(c) < 128 for c in ps)


def test_no_dr_is_a_known_option_of_eax_test():
    src = (REPO / "eaxcli" / "commands.py").read_text(encoding="utf-8")
    assert '"--no-dr"' in src
    help_ = (REPO / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert "--no-dr leaves it out" in help_ and all(ord(c) < 128 for c in help_)


# ---------------------------------------------------------------- the drill scripts
@needs_bash
def test_then_back_stops_the_dr_copy_and_starts_the_installation_again(tmp_path):
    from test_r5_6_dr import _backup, _code_source, _offline
    inst = _code_source(tmp_path)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    dr = tmp_path / "dr1"
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(dr), "--temp",
                        str(tmp_path / "temp"), "--smoke-after", "--then-back"],
                       env={**_offline(tmp_path), **{k: v for k, v in os.environ.items() if k == "HOME"}},
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "PASSED" in r.stdout
    dr_calls = (dr / "work" / "calls.txt").read_text().splitlines()
    assert dr_calls[-2:] == ["test smoke", "stop"], dr_calls            # the smoke test on the DR copy, then stopped
    calls = (inst / "work" / "calls.txt").read_text().splitlines()
    shut = calls.index("drill shutdown")
    assert calls[shut + 1:][-2:] == ["up --wait-all", "drill signin"], calls
    assert "test smoke" not in calls                                    # --smoke-after: not on the installation
    report = next((inst / "work" / "tests").glob("drill-*/report.md")).read_text()
    assert "the DR copy stopped (kept)" in report and "the installation started again and a real sign-in" in report
    assert "Your installation is running again." in report and "left running" not in report
    got = F.drill_report(next((inst / "work" / "tests").glob("drill-*/report.md")))
    assert got["passed"] is True and got["recovery"] is not None
    assert [s["step"] for s in got["steps"]][-2:] == ["the DR copy stopped (kept)",
                                                      "the installation started again and a real sign-in"]


@needs_bash
def test_without_then_back_the_drill_still_leaves_the_dr_copy_running(tmp_path):
    from test_r5_6_dr import _backup, _code_source, _offline
    inst = _code_source(tmp_path)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    dr = tmp_path / "dr1"
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(dr), "--temp",
                        str(tmp_path / "temp")],
                       env={**_offline(tmp_path), **{k: v for k, v in os.environ.items() if k == "HOME"}},
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "stop" not in (dr / "work" / "calls.txt").read_text().splitlines()
    assert (inst / "work" / "calls.txt").read_text().splitlines()[-1] == "drill shutdown"
    assert "left running" in r.stdout


@needs_bash
def test_then_back_when_the_drill_fails_after_the_dr_copy_began_still_goes_back(tmp_path):
    from test_r5_6_dr import _backup, _code_source, _offline
    inst = _code_source(tmp_path)
    # nobody can sign in to the DR copy: the drill fails there, after the DR copy began
    eax = (inst / "eax.sh").read_text().replace(
        "  'drill signin')", "  'drill signin') [ \"$here\" = \"${FAIL_IN:-}\" ] && { echo '{\"error\": \"nobody\"}'; exit 1; };")
    (inst / "eax.sh").write_text(eax)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    dr = tmp_path / "dr1"
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(dr), "--temp",
                        str(tmp_path / "temp"), "--then-back"],
                       env={**_offline(tmp_path), "FAIL_IN": str(dr),
                            **{k: v for k, v in os.environ.items() if k == "HOME"}},
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 1, r.stdout[-3000:]
    assert "FAILED" in r.stdout
    assert (dr / "work" / "calls.txt").read_text().splitlines()[-1] == "stop"
    assert (inst / "work" / "calls.txt").read_text().splitlines()[-1] == "up --wait-all"
    assert "Your installation is running again." in r.stdout


def test_the_powershell_drill_goes_back_the_same_way():
    ps = (DR / "eax-drill.ps1").read_text(encoding="utf-8")
    body = ps[ps.index("if ($ThenBack) {"):ps.index("$exit = 0\n} catch") if "$exit = 0\n} catch" in ps else None]
    assert body.index('Step "the DR copy stopped (kept)"') < body.index("$Install = $Original") < body.index(
        'Step "the installation started again and a real sign-in"')
    assert 'Eax @("stop")' in body and 'Eax @("up", "--wait-all")' in body and 'Eax @("drill", "signin")' in body
    fin = ps[ps.index("if ($drStarted -and $ThenBack) {"):]
    assert "Your installation is running again." in fin and "} elseif ($drStarted) {" in fin
    assert "if ($Smoke -or $SmokeAfter)" in ps


# ---------------------------------------------------------------- the summary page
def test_the_drills_report_is_a_card_on_the_full_tests_summary_page(tmp_path):
    import time
    tests = tmp_path / "tests"
    d = tests / "drill-20261122T100000Z"
    d.mkdir(parents=True)
    (d / "report.md").write_text(
        "﻿# EA Explorer restore drill, 2026-11-22 10:00\n\n**Passed with 1 warning(s)** in 41 minutes. Installation x.\n\n"
        "Recovery time (from shutting the installation down to the DR copy restored and sign-in working): 12 minutes.\n\n"
        "| | Step | Seconds | Detail |\n| --- | --- | --- | --- |\n| ok | checks (nothing touched yet) | 3 | version 9.0.0 |\n"
        "| warn | the key items compared with before | 4 | 2 lost |\n| ok | the DR copy stopped (kept) | 20 | stopped |\n",
        encoding="utf-8")
    s = F.gather(tests, time.time() - 5, [("DR drill", True, "")], version="9.0.0")
    assert s["dr"]["folder"] == d.name and s["dr"]["passed"] is True and s["dr"]["recovery"] == 12
    assert s["dr"]["warnings"] == 1 and len(s["dr"]["steps"]) == 3
    html = "".join(F.cards(s))
    assert "DR drill" in html and "12 minutes" in html and "drill-20261122T100000Z/report.md" in html


def test_a_failed_drill_reads_as_failed_and_a_missing_report_says_so(tmp_path):
    p = tmp_path / "report.md"
    p.write_text("# drill\n\n**Failed in 3 minutes. Installation x.**\n\n| | Step | Seconds | Detail |\n"
                 "| --- | --- | --- | --- |\n| FAILED | eax-dr | 100 | eax-dr failed |\n")
    got = F.drill_report(p)
    assert got["passed"] is False and got["steps"][0]["state"] == "FAILED" and got["recovery"] is None
    assert F.drill_report(tmp_path / "none.md")["passed"] is None
    html = "".join(F.cards({"steps": [{"title": "DR drill", "passed": False, "why": "ended with 1", "kind": "dr"}]}))
    assert "DR drill" in html and "ended with 1" in html


# ---------------------------------------------------------------- from Jenkins
def test_the_full_test_is_an_upkeep_task_in_jenkins_and_asks_to_be_confirmed():
    t = J.ADMIN_BY_NAME["admin-full-test"]
    assert t["group"] == "Upkeep" and t["confirm"] is True
    assert J.admin_argv("admin-full-test", {}) == ["test", "full"]
    got = J.admin_argv("admin-full-test", {"DEV_CHECK": "--no-dev-check", "SONAR": "--no-sonar", "DR_DRILL": "--no-dr",
                                     "ATTACK": "--no-attack"})
    assert got == ["test", "full", "--no-dev-check", "--no-attack", "--no-sonar", "--no-dr"]
    with pytest.raises(C.Refused):
        J.admin_argv("admin-full-test", {"DR_DRILL": "--yes; rm -rf /"})
    C.check_argv(got)                                                   # every option a known one


def test_the_drill_pipeline_offers_the_new_options():
    keys = {p["key"] for p in J.DR_TOOLS["eax-drill"]["params"]}
    assert {"--smoke", "--smoke-after", "--then-back"} <= keys
