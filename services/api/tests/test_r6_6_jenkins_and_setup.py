"""Release 6.6: Jenkins (R6.6-J1) and the guides (eax setup), D750.

Every eax command of the help and every DR tool has a pipeline (owner, 17 Nov 2026: "every eax command and the dr command
is executable from jenkins"); the agent refuses a wrong token, an unknown pipeline and a missing installation name; the
guides are a valid list with a written guide each; the external database's compose file is valid compose.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import commands as C  # noqa: E402
from eaxcli import jenkins as J  # noqa: E402
from eaxcli import setup as S  # noqa: E402


class _NoRuns:
    def __init__(self):
        self.started = []

    def start(self, argv, by):
        self.started.append((argv, by))
        return "run-1"


# ---------------------------------------------------------------- Jenkins
def test_every_command_and_dr_tool_has_a_pipeline():
    names = {p["name"] for p in J.pipelines()}
    every = {c["name"] for g in C.catalogue()["groups"] for c in g["commands"]}
    assert every <= names
    assert {"eax-dr", "eax-drill", "dr-pack", "jenkins", "setup"} <= names
    assert all(p["confirm"] for p in J.pipelines() if p["kind"] == "dr")


def test_the_agent_refuses_a_wrong_token_and_an_unknown_pipeline():
    runs = _NoRuns()
    assert J.handle({"pipeline": "status"}, "tok", "nope", runs)[0] == 401
    assert J.handle({"pipeline": "status"}, "", "", runs)[0] == 401
    assert J.handle({"pipeline": "rm -rf"}, "tok", "tok", runs)[0] == 404
    assert runs.started == []


def test_a_dr_tool_needs_the_installation_name(monkeypatch):
    monkeypatch.setattr(J, "installation", lambda: "meridian-prod")
    runs = _NoRuns()
    body = {"pipeline": "eax-drill", "values": {"--install": "/srv/eax", "--dr": "/srv/dr", "--temp": "/tmp/x"}}
    code, said = J.handle(body, "tok", "tok", runs)
    assert code == 403 and "meridian-prod" in said["message"] and runs.started == []
    body["values"]["CONFIRM"] = "meridian-prod"
    assert J.handle(body, "tok", "tok", runs)[0] == 202
    assert runs.started[0][0][:3] == ["eax-drill", "--install", "/srv/eax"]


def test_a_dr_tool_refuses_a_value_with_a_shell_in_it():
    with pytest.raises(C.Refused):
        J.argv_for("eax-drill", {"--install": "/srv;rm -rf /", "--dr": "/d", "--temp": "/t"})


# ---------------------------------------------------------------- the guides
def test_the_guides_are_a_valid_list_with_a_written_guide_each():
    ids = [g["id"] for g in S.GUIDES]
    assert len(ids) == len(set(ids))
    every = {c["name"] for g in C.catalogue()["groups"] for c in g["commands"]}
    for g in S.listing():
        assert g["title"] and g["for"] and g["steps"], g["id"]
        assert (REPO / g["doc"]).exists(), g["doc"]
        for s in g["steps"]:
            if s["command"].startswith("dr:"):                   # a DR tool, run on the machine it is for
                assert s["command"].split()[0][3:] in J.DR_TOOLS, (g["id"], s["command"])
            elif s["command"]:
                assert s["command"].split()[0] in every, (g["id"], s["command"])
            assert s["check"] in ("", "docker", "config", "running", "external_db")
    need = {"laptop", "server", "remote", "dr-site", "backups", "restores", "catastrophe", "rebuild", "switch-to-dr",
            "new-machine", "pairings", "upgrades", "move", "security", "forgotten", "external-db", "certificates",
            "jenkins"}
    assert need <= set(ids)


def test_a_guide_with_yes_does_not_run_what_changes_everything_without_the_name(monkeypatch):
    monkeypatch.setattr(S, "check", lambda name: (True, ""))
    monkeypatch.setattr(S, "setting", lambda k, d="": "meridian-prod" if k == "EAX_INSTALLATION_NAME" else d)
    ran, said = [], []
    assert S.walk("upgrades", yes=True, run=lambda c: ran.append(c) or 0, out=said.append) == 0
    assert "update" not in ran and "rollback" not in ran and "backup" in ran
    ran.clear()
    S.walk("upgrades", yes=True, confirm="meridian-prod", run=lambda c: ran.append(c) or 0, out=said.append)
    assert "update" in ran and "rollback" in ran


def test_external_db_is_refused_when_the_server_does_not_answer(monkeypatch, tmp_path):
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DB_SUPERUSER_PASSWORD=x\n", encoding="utf-8")
    monkeypatch.setattr(S, "ENV_FILE", env)
    monkeypatch.setattr(S, "setting", lambda k, d="": d)

    def fails(*a, **k):
        return subprocess.CompletedProcess(a, 2, "", "could not connect")
    with pytest.raises(S.Failure, match="prepare.sql"):
        S.external_db("db.example.org", run=fails)
    assert env.read_text(encoding="utf-8") == "EAX_DB_SUPERUSER_PASSWORD=x\n"
    with pytest.raises(S.Failure):
        S.external_db("db;rm", run=fails)


def test_external_db_writes_the_settings_once_it_answers(monkeypatch, tmp_path):
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DB_SUPERUSER_PASSWORD=x\nEAX_COMPOSE_EXTRA=standby\n", encoding="utf-8")
    monkeypatch.setattr(S, "ENV_FILE", env)
    monkeypatch.setattr(S, "setting", lambda k, d="": {"EAX_COMPOSE_EXTRA": "standby"}.get(k, d))
    import eaxcli.secrets as sec
    monkeypatch.setattr(sec, "dated_copy", lambda text: tmp_path / "copy")

    def answers(*a, **k):
        return subprocess.CompletedProcess(a, 0, "eax_admin on PostgreSQL 17.2", "")
    S.external_db("db.example.org", "6432", run=answers)
    text = env.read_text(encoding="utf-8")
    for line in ("EAX_EXTERNAL_DB_HOST=db.example.org", "EAX_EXTERNAL_DB_PORT=6432", "EAX_DB_ADMIN_USER=eax_admin",
                 "EAX_COMPOSE_EXTRA=standby,external-db"):
        assert line in text


def test_the_external_db_compose_file_is_valid_compose(tmp_path):
    if not shutil.which("docker") or subprocess.run(["docker", "compose", "version"], capture_output=True,
                                                    check=False).returncode != 0:
        pytest.skip("docker compose is not here")
    env = tmp_path / "t.env"
    env.write_text("EAX_EXTERNAL_DB_HOST=db.example.org\n", encoding="utf-8")
    p = subprocess.run(["docker", "compose", "--env-file", str(env), "-f",
                        str(REPO / "deploy/compose/scale/docker-compose.external-db.yml"), "config", "--no-interpolate"],
                       capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stderr


# ---------------------------------------------------------------- the owner's first eax jenkins up (18 Nov 2026, 09:21)
def test_jenkins_is_built_on_a_jenkins_new_enough_for_the_newest_plugins():
    """plugins.txt names no versions, so jenkins-plugin-cli takes each plugin's newest, which needs a recent Jenkins:
    the pinned 2.479.3 refused them."""
    docker = (REPO / "deploy/jenkins/Dockerfile").read_text()
    assert "FROM jenkins/jenkins:2.479.3" not in docker and "ARG JENKINS_IMAGE=jenkins/jenkins:lts-jdk21" in docker and "FROM ${JENKINS_IMAGE}" in docker
    assert "${EAX_JENKINS_IMAGE:-jenkins/jenkins:lts-jdk21}" in (REPO / "deploy/jenkins/docker-compose.jenkins.yml").read_text()


def test_a_jenkins_that_does_not_start_says_why(monkeypatch, tmp_path):
    monkeypatch.setattr(J, "WORK", tmp_path)
    out = ("#8 12.1 Downloading plugins...\n#8 14.2 Plugin oic-auth:4.500 requires a newer version of Jenkins (2.504) "
           "than 2.479.3\n#8 14.3 ...\nfailed to solve: process \"/bin/sh -c jenkins-plugin-cli\" did not complete")
    said = J.why_not_started(out)
    assert "requires a newer version of Jenkins" in said and "work/jenkins/start.log" in said
    assert (tmp_path / "jenkins" / "start.log").read_text() == out


# ---------------------------------------------------------------- the owner's clean-restart (18 Nov 2026, 09:49)
def test_cleanup_stops_the_jenkins_agent_before_it_empties_work():
    """"The process cannot access the file 'eax-...-jenkins-agent.log' because it is being used by another process":
    the agent held its log open in work/logs while cleanup emptied work/."""
    ps, sh = (REPO / "eax.ps1").read_text(), (REPO / "eax.sh").read_text()
    ps_clean = ps[ps.index("function Invoke-Cleanup"):]
    assert ps_clean.index("jenkins stop-agent") < ps_clean.index("Remove-Item -Recurse -Force")
    sh_clean = sh[sh.index("cleanup() {"):]
    assert sh_clean.index("jenkins stop-agent") < sh_clean.index("rm -rf")
    main = (REPO / "eaxcli/main.py").read_text()
    assert main.index("jenkins.stop_agent()") < main.index("logkeep.backup(base")


def test_stop_agent_stops_only_the_agent_that_answers(monkeypatch, tmp_path):
    monkeypatch.setattr(J, "WORK", tmp_path)
    (tmp_path / "jenkins").mkdir()
    pid = tmp_path / "jenkins" / "agent.pid"
    killed = []
    monkeypatch.setattr(J.os, "kill", lambda p, s: killed.append(p))
    monkeypatch.setattr(J.time, "sleep", lambda s: None)
    pid.write_text("4242")
    monkeypatch.setattr(J, "_agent_running", lambda: False)                 # a pid file left behind: nothing stopped
    assert J.stop_agent() == "No agent was running." and killed == [] and not pid.exists()
    pid.write_text("4242")
    answers = iter([True, False])
    monkeypatch.setattr(J, "_agent_running", lambda: next(answers, False))
    assert J.stop_agent() == "The Jenkins agent stopped." and killed == [4242] and not pid.exists()


# ---------------------------------------------------------------- the guides as documents (the owner, 18 Nov 2026, 12:29, D772)
def test_the_setup_page_documents_and_runs_nothing():
    """"There should be no run it. Just document": the page shows each guide with its commands filled in, to copy."""
    page = (REPO / "services/web/src/SetupGuides.jsx").read_text()
    assert "Run it" not in page and "/commands/run" not in page
    for want in ("Your values", "Copy every command", "Download this guide", "Windows (PowerShell)", "Linux or macOS"):
        assert want in page, want


def test_a_guides_values_fill_its_commands_and_an_optional_one_takes_its_option_with_it():
    """"put in paramters like server name location of key file and so on and we get the dynamic set of commands"."""
    cert = S.BY_ID["certificates"]
    assert S.params_of(cert) == ["HOSTNAME", "CERT_FILE", "KEY_FILE", "CHAIN_FILE"]
    c = next(c for _t, _s, c, _k in cert["steps"] if c.startswith("certs front install"))
    assert S.fill(c, {"CERT_FILE": "C:/c/ea.crt", "KEY_FILE": "C:/c/ea.key"}, command=True) == \
        "certs front install --cert C:/c/ea.crt --key C:/c/ea.key"
    assert S.fill(c, {"CERT_FILE": "a", "KEY_FILE": "b", "CHAIN_FILE": "c"}, command=True).endswith("--chain c")
    assert S.unfilled(S.fill(c, {}, command=True)) == ["CERT_FILE", "KEY_FILE"]
    assert S.windows("dr:eax-dr --pack <PACK> --install <INSTALL>") == r".\dr\eax-dr.ps1 -Pack <PACK> -Install <INSTALL>"
    assert S.unix("dr:eax-dr --pack <PACK> --install <INSTALL>") == "./dr/eax-dr.sh --pack <PACK> --install <INSTALL>"
    assert S.windows("up") == r".\eax up" and S.unix("up") == "./eax.sh up"
    for g in S.listing():
        assert all(p["key"] in S.PARAMS for p in g["params"]), g["id"]
        for s in g["steps"]:
            assert not s["command"] or (s["windows"] and s["unix"]), (g["id"], s["title"])


def test_the_console_never_runs_a_step_still_missing_a_value_or_a_dr_tool():
    ran, said = [], []
    S.walk("certificates", yes=True, run=lambda c: ran.append(c) or 0, out=said.append, values={"HOSTNAME": "ea.x.org"})
    assert ran == ["certs front"] and any("--set CERT_FILE=" in x for x in said) and any("ea.x.org" in x for x in said)
    ran.clear()
    S.walk("certificates", yes=True, run=lambda c: ran.append(c) or 0, out=said.append,
           values={"CERT_FILE": "C:/c/ea.crt", "KEY_FILE": "C:/c/ea.key"})
    assert ran == ["certs front install --cert C:/c/ea.crt --key C:/c/ea.key", "certs front"]
    ran.clear()
    S.walk("rebuild", yes=True, run=lambda c: ran.append(c) or 0, out=said.append, values={"PACK": "D:/p", "INSTALL": "C:/e"})
    assert not any("eax-dr" in c for c in ran)


def test_the_written_guides_are_made_from_the_list():
    """docs/guides/<guide>.md is eaxcli/setup.py's markdown(): change the list, then write the files again."""
    for g in S.GUIDES:
        assert (REPO / "docs/guides" / f"{g['id']}.md").read_text(encoding="utf-8") == S.markdown(g["id"]), g["id"]
