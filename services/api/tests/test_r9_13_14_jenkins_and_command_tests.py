"""R9.13 and R9.14 (D854; owner, 22 Nov 2026, 09:51): `eax test jenkins` starts every pipeline through Jenkins' API as a
probe, which the agent checks and records but never runs, and compares the command recorded with the one expected;
`eax test commands` runs each safe eax command for real and checks it, every other command listed with why."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import command_tests as CT  # noqa: E402
from eaxcli import commands as C  # noqa: E402
from eaxcli import jenkins as J  # noqa: E402
from eaxcli import jenkins_test as JT  # noqa: E402

TOKEN = "t0ken"


class _Runs(J.Runs):
    """The agent's runs in a folder of the test's; a real start would fail the test."""

    def start(self, argv, by, run=None):
        raise AssertionError(f"a probe must never run anything: {argv}")


def _agent(tmp_path):
    return _Runs(tmp_path / "jenkins" / "runs")


# ---------------------------------------------------------------- the agent's probe
def test_a_probe_is_checked_and_recorded_but_not_run(tmp_path):
    runs = _agent(tmp_path)
    code, out = J.handle({"pipeline": "status", "values": {}, "by": "jenkins-admin", "probe": "ab12-001"}, TOKEN, TOKEN, runs)
    assert code == 202 and out["probe"] == "ab12-001" and out["command"] == "eax status"
    line = (tmp_path / "jenkins" / "runs.log").read_text(encoding="utf-8").strip().split("\t")
    assert line[2:] == ["jenkins-admin", "status", "probe=ab12-001"]
    assert json.loads((tmp_path / "jenkins" / "runs" / f"{out['run']}.json").read_text())["exit"] == 0
    assert "(checked, not run)" in runs.read(out["run"])["output"] and runs.read(out["run"])["done"]


def test_a_probe_gets_every_check_a_run_gets(tmp_path):
    runs = _agent(tmp_path)
    assert J.handle({"pipeline": "status", "probe": "p-1"}, TOKEN, "wrong", runs)[0] == 401
    assert J.handle({"pipeline": "no-such", "probe": "p-1"}, TOKEN, TOKEN, runs)[0] == 404
    wipe = next(p["name"] for p in J.pipelines() if p["confirm"] and p["name"] == "clean-restart")
    code, out = J.handle({"pipeline": wipe, "values": {}, "probe": "p-1"}, TOKEN, TOKEN, runs)
    assert code == 403 and "installation's name" in out["message"]
    assert J.handle({"pipeline": "status", "probe": "no spaces; rm"}, TOKEN, TOKEN, runs)[0] == 400


def test_the_agent_says_it_knows_probes_and_the_pipelines_send_them():
    assert '"probe": True' in (REPO / "eaxcli" / "jenkins.py").read_text(encoding="utf-8")
    seed = (REPO / "deploy" / "jenkins" / "seed.groovy").read_text(encoding="utf-8")
    assert "stringParam('EAX_PROBE', ''" in seed
    assert "probe: (params.EAX_PROBE ?: '')]" in seed


# ---------------------------------------------------------------- eax test jenkins
def test_samples_fill_required_fields_and_the_name_for_what_changes_everything():
    p = {"name": "x", "confirm": True, "params": [
        {"key": "--to", "type": "flag-value", "required": True},
        {"key": "kind", "type": "choice", "required": True, "choices": ["a", "b"]},
        {"key": "--quiet", "type": "flag"}, {"key": "--note", "type": "flag-value"}]}
    jk, original = JT.sample_values(p)
    assert jk == {"to": "probe", "kind": "a", "quiet": "false", "note": "", "CONFIRM": J.installation()}
    assert original == {"--to": "probe", "kind": "a", "CONFIRM": J.installation()}
    assert JT.job_path({"name": "status"}) == "/job/eax/job/status"
    assert JT.job_path({"name": "admin-x", "display": "x", "folder": "eax-admin/backups"}) == "/job/eax-admin/job/backups/job/x"


def test_only_this_runs_probes_are_read_back():
    log = ("2026\tr1\tjenkins-admin\tstatus\tprobe=abcd1234-001\n"
           "2026\tr2\tjenkins-admin\tbackups\n"                       # a real run: not a probe
           "2026\tr3\tjenkins-admin\turl\tprobe=other999-001\n")
    assert JT.recorded(log, "abcd1234") == {"abcd1234-001": "eax status"}


class _FakeJenkins:
    """Jenkins as the test sees it: each start goes to the real agent code, which records the probe."""

    def __init__(self, runs, fields=("EAX_PROBE",), wrong=None):
        self.runs, self.extra, self.wrong, self.started = runs, list(fields), wrong or {}, []

    def sign_in(self):
        pass

    def fields(self, path):
        return self.extra + ["CONFIRM", "COMMAND", "ARGS"]

    def start(self, path, values):
        p = next(x for x in J.pipelines() if JT.job_path(x) == path)
        _, original = JT.sample_values(p)
        self.started.append(p["name"])
        if p["name"] in self.wrong:
            return 201 if J.handle({"pipeline": self.wrong[p["name"]], "values": {}, "by": "jenkins-admin",
                                    "probe": values["EAX_PROBE"]}, TOKEN, TOKEN, self.runs)[0] == 202 else 500
        J.handle({"pipeline": p["name"], "values": original, "by": "jenkins-admin", "probe": values["EAX_PROBE"]},
                 TOKEN, TOKEN, self.runs)
        return 201


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(JT, "WORK", tmp_path)
    monkeypatch.setattr(J, "answering", lambda: True)
    monkeypatch.setattr(JT, "agent_knows_probes", lambda: True)
    monkeypatch.setattr(JT, "say", lambda *a, **k: None)
    return _agent(tmp_path)


def test_every_pipeline_probed_and_the_commands_compared(monkeypatch, tmp_path):
    runs = _setup(monkeypatch, tmp_path)
    fake = _FakeJenkins(runs)
    JT.run([], jenkins=fake, sleep=lambda s: None, wait_minutes=0.01)
    report = json.loads(next((tmp_path / "tests").glob("jenkins-*/report.json")).read_text())
    assert report["counts"]["passed"] >= 100
    assert not any(r["outcome"] == "passed" and r["expected"] != r["recorded"] for r in report["pipelines"])
    # what the test found on its first run (22 Nov 2026), a bug for Release 12 (R12.18): these pipelines start a
    # command that takes EA Explorer offline but have no CONFIRM field, so the agent always refuses them
    assert {r["pipeline"] for r in report["pipelines"] if r["outcome"] == "failed"} == KNOWN_BROKEN
    assert {r["pipeline"] for r in report["pipelines"] if r["outcome"] == "skipped"} == {"footprint", "restore-model"}


KNOWN_BROKEN = {"admin-start", "admin-maintenance-page-on", "admin-maintenance-page-off", "admin-maintenance-clear"}


def test_the_known_broken_pipelines_have_no_confirm_field_but_need_one():
    for p in J.pipelines():
        if p["name"] in KNOWN_BROKEN:
            _, original = JT.sample_values(p)
            argv = J.argv_for(p["name"], original)
            assert not p["confirm"] and C.kind_of_argv(argv) in ("offline", "wipe"), p["name"]


def test_a_pipeline_that_starts_the_wrong_command_fails(monkeypatch, tmp_path):
    runs = _setup(monkeypatch, tmp_path)
    fake = _FakeJenkins(runs, wrong={"status": "url"})
    assert JT.run(["--only", "status,url"], jenkins=fake, sleep=lambda s: None, wait_minutes=0.01) == 1
    rows = {r["pipeline"]: r for r in json.loads(next((tmp_path / "tests").glob("jenkins-*/report.json")).read_text())["pipelines"]}
    assert rows["status"]["outcome"] == "failed" and rows["status"]["recorded"] == "eax url"
    assert rows["url"]["outcome"] == "passed"


def test_nothing_is_started_when_a_probe_could_run_for_real(monkeypatch, tmp_path):
    runs = _setup(monkeypatch, tmp_path)
    old = _FakeJenkins(runs, fields=())                          # a pipeline from before EAX_PROBE
    with pytest.raises(J.Failure, match="no EAX_PROBE field"):
        JT.run([], jenkins=old, sleep=lambda s: None, wait_minutes=0.01)
    assert old.started == []
    monkeypatch.setattr(JT, "agent_knows_probes", lambda: False)  # an agent from before probes
    with pytest.raises(J.Failure, match="does not know probes"):
        JT.run([], jenkins=_FakeJenkins(runs), sleep=lambda s: None, wait_minutes=0.01)


# ---------------------------------------------------------------- eax test commands
def test_every_command_is_tested_or_said_why_not():
    every = {c["name"] for g in C.catalogue()["groups"] for c in g["commands"]}
    tested = {args[0] for args, *_ in CT.CASES}
    assert not tested & set(CT.NOT_RUN), "a command both run and not run"
    assert every - tested - set(CT.NOT_RUN) == set(), "a command neither tested nor said why not"
    assert set(CT.NOT_RUN) <= every and tested <= every
    for name in ("cleanup", "clean-restart", "restore", "update", "rollback", "drill", "stop"):
        assert name in CT.NOT_RUN                                 # nothing that changes everything is run


def test_a_command_passes_on_its_exit_code_and_words():
    assert CT.check(["status"], ["ea explorer"], 0, "EA Explorer 8.0.0, build x", False) == ("passed", "")
    assert CT.check(["status"], ["ea explorer"], 0, "nothing", False)[0] == "failed"
    assert CT.check(["status"], [], 2, "ERROR: no\nreally", False) == ("failed", "it ended with 2: ERROR: no really")
    assert CT.check(["diag"], [], 0, "", True) == ("failed", "it did not end in time")


def test_the_commands_run_through_this_machines_launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(CT, "WORK", tmp_path)
    monkeypatch.setattr(CT, "say", lambda *a, **k: None)
    seen = []

    class P:
        def __init__(self, argv):
            self.returncode, self.stdout, self.stderr = 0, "EA Explorer 8.0.0 https:// eax-auth-001", ""

    def runner(cmd, **kw):
        seen.append(cmd)
        assert kw["timeout"] and kw["stdin"] is not None and kw["env"]["EAX_NONINTERACTIVE"] == "1"
        return P(cmd)
    assert CT.run(["--only", "status,url"], runner=runner) == 0
    assert [c[-1] for c in seen] == ["status", "problems", "url"]
    assert all(c[:len(CT.launcher())] == CT.launcher() for c in seen)


def test_the_launchers_and_the_help_know_both():
    ps1 = (REPO / "eax.ps1").read_text(encoding="utf-8")
    assert '$RestArgs[0] -eq "jenkins" -or $RestArgs[0] -eq "commands"' in ps1
    assert '*" test jenkins "*|*" test commands "*' in (REPO / "eax.sh").read_text(encoding="utf-8")
    main = (REPO / "eaxcli" / "main.py").read_text(encoding="utf-8")
    assert 'rest[:1] == ["jenkins"]' in main and 'rest[:1] == ["commands"]' in main
    text = (REPO / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert "jenkins [--only NAMES]|commands [--only NAMES]" in text and "  jenkins  every Jenkins pipeline" in text
    assert all(ord(c) < 128 for c in text + ps1)
