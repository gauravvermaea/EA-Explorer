"""Release 11 (D872): certificate mode, each service able to read its own key.

The owner's run (22 Nov 2026, 19:40): `uid=10001(eax) gid=999(eax)` in the API, its key `-rw-r----- 0 10001
client.key`, so libpq "could not load private key file". `useradd --system --uid 10001` gives the user id 10001 but
its group a system id. Now each of our images makes its user's group with the id its key is written for
(eax/certs.py CLIENTS), and `eax certs check` shows, for each running service, whether it can read its key."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO))
from eaxcli import certs as C  # noqa: E402
from eaxcli.core import Failure  # noqa: E402

from eax import certs  # noqa: E402

IMAGES = {"api": "eax", "library": "eaxlib", "views": "eaxviews"}


@pytest.mark.parametrize("svc", sorted(IMAGES))
def test_each_image_user_is_in_the_group_its_key_is_written_for(svc):
    df = (REPO / "services" / svc / "Dockerfile").read_text(encoding="utf-8")
    gid = certs.CLIENTS[svc]["gid"]
    user = IMAGES[svc]
    assert re.search(rf"groupadd --system --gid {gid} {user}\b", df), svc
    assert re.search(rf"useradd --system --uid {gid} --gid {gid} --home /app {user}\b", df), svc
    assert re.search(rf"^USER {user}$", df, re.M), svc


def test_a_useradd_without_its_group_is_never_back():
    """In every Dockerfile of ours, the test runner's too (Dockerfile.test: the owner's smoke test in certificate mode,
    22 Nov 2026, ran nothing because it had the same fault)."""
    files = sorted(REPO.glob("services/*/Dockerfile*")) + sorted(REPO.glob("deploy/**/Dockerfile*"))
    assert any(f.name == "Dockerfile.test" for f in files)
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if "useradd" in line and not line.lstrip().startswith("#"):
                assert "--gid" in line, f"{f.relative_to(REPO)}: {line.strip()}"


def test_the_test_runner_reads_the_apis_key_as_the_api_does():
    df = (REPO / "services" / "api" / "Dockerfile.test").read_text(encoding="utf-8")
    assert "groupadd --system --gid 10001 eax" in df and "useradd --system --uid 10001 --gid 10001 --home /app eax" in df


def _runner(answers):
    def run(args, **k):
        svc = args[args.index("exec") + 2]
        out, rc = answers.get(svc, ("", 1))

        class P:
            returncode, stdout, stderr = rc, out, ("" if rc == 0 else f"service {svc} is not running")
        return P()
    return run


def test_certs_check_says_who_can_read_its_key(monkeypatch):
    monkeypatch.setattr(C, "compose_args", lambda a: a)
    ok = "uid=10001(eax) gid=10001(eax) groups=10001(eax)\nREADABLE\n"
    bad = "uid=10001(eax) gid=999(eax) groups=999(eax)\nUNREADABLE\n-rw-r----- 1 0 10001 227 Nov 22 17:34 /eax-certs/client.key\n"
    res = {c["service"]: c for c in C.check(run=_runner({"api": (bad, 0), "library": (ok, 0), "db": (ok, 0)}))}
    assert res["api"]["ok"] is False and "gid=999" in res["api"]["id"] and "10001" in res["api"]["why"]
    assert res["library"]["ok"] is True and res["db"]["key"] == "server.key"
    assert res["views"]["ok"] is None and "not running" in res["views"]["why"]
    assert res["keycloak"]["key"] == "client.key.pk8"


def test_certs_check_fails_when_a_service_cannot_read_its_key(monkeypatch):
    monkeypatch.setattr(C, "ENV_FILE", type("E", (), {"exists": staticmethod(lambda: True)})())
    monkeypatch.setattr(C, "setting", lambda k, d="": "certificate")
    monkeypatch.setattr(C, "say", lambda *a, **k: None)
    monkeypatch.setattr(C, "check", lambda: [{"service": "api", "key": "client.key", "ok": False, "id": "gid=999", "why": "x"}])
    with pytest.raises(Failure, match="cannot read their key"):
        C.main(["check"])
    monkeypatch.setattr(C, "check", lambda: [{"service": "api", "key": "client.key", "ok": True, "id": "gid=10001", "why": ""}])
    assert C.main(["check"]) == 0


def test_help_and_the_command_test_know_certs_check():
    h = (REPO / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert "### certs [list|check|renew|revoke|switch|front]" in h and "  check          each running service" in h
    assert '(["certs", "check"], [], 120, False)' in (REPO / "eaxcli" / "command_tests.py").read_text(encoding="utf-8")


def _testruns():
    import importlib.util
    spec = importlib.util.spec_from_file_location("testruns_certs", REPO / "services/ops/testruns.py")
    tr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tr)
    return tr


def test_a_runner_the_helper_starts_has_the_apis_certificates_folder():
    """The owner's smoke test in certificate mode (22 Nov 2026, 20:18): "root certificate file /eax-certs/ca.crt does not
    exist": the runner had the API's environment (PGSSLROOTCERT=/eax-certs/ca.crt) but not its folder."""
    tr = _testruns()
    info = {"HostConfig": {"Mounts": [{"Type": "volume", "Source": "eaexplorer_eax-certs", "Target": "/eax-certs",
                                       "ReadOnly": True, "VolumeOptions": {"Subpath": "api"}}]}}
    assert tr.certs_mount(info) == ["--mount", "type=volume,src=eaexplorer_eax-certs,dst=/eax-certs,volume-subpath=api,readonly"]
    old = {"Mounts": [{"Type": "volume", "Name": "eaexplorer_eax-certs", "Destination": "/eax-certs"}]}
    assert "volume-subpath=api" in tr.certs_mount(old)[1]          # never the whole volume (the authority's key is there)
    assert tr.certs_mount({"HostConfig": {"Mounts": []}, "Mounts": []}) == []     # password mode
    src = (REPO / "services/ops/testruns.py").read_text(encoding="utf-8")
    body = src[src.index("def _runner_args("):src.index("def certs_mount(")]
    assert "args += certs_mount(info)" in body


# ---------------------------------------------------------------- R11.3 and R11.2: switching, remembered, and clean-restart
def test_certs_switch_remembers_the_choice_for_the_next_clean_restart(monkeypatch, tmp_path):
    """R14.11 (21 Nov 2026), now R11.3: `eax certs switch` changed the config file but not persist/auth.json, so the next
    clean restart went back to the old mode."""
    from eaxcli import persist as P
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_AUTH_MODE=password\n", encoding="utf-8")
    monkeypatch.setattr(C, "ENV_FILE", env)
    monkeypatch.setattr(C, "say", lambda *a, **k: None)
    import eaxcli.secrets as S
    monkeypatch.setattr(S, "dated_copy", lambda text: None)
    monkeypatch.setattr(P, "folder", lambda: tmp_path)
    C.switch("certificate")
    assert "EAX_AUTH_MODE=certificate" in env.read_text(encoding="utf-8")
    assert P.read_json(tmp_path / "auth.json", {})[0] == {"mode": "certificate"}
    C.switch("password")
    assert P.read_json(tmp_path / "auth.json", {})[0] == {"mode": "password"}
    with pytest.raises(Failure):
        C.switch("magic")


def test_clean_restart_passes_the_mode_to_init(monkeypatch, tmp_path):
    from eaxcli import main as M
    ran = []
    monkeypatch.setattr(M, "run_self", lambda step: ran.append(step) or 0)
    monkeypatch.setattr(M, "say", lambda *a, **k: None)
    monkeypatch.setattr(M, "ENV_FILE", tmp_path / "none.env")
    assert M.clean("clean-restart", ["laptop", "--certificate"], False) == 0
    assert ["init", "laptop", "--certificate"] in ran
    ran.clear()
    M.clean("clean-run", ["--password"], True)
    assert ran == [["cleanup", "--all", "--yes"], ["init", "laptop", "--password"], ["up", "--wait-all"]]
    ran.clear()
    M.clean("clean-run", [], False)
    assert ["init", "laptop"] in ran                                  # the choice made before is kept
    ps = (REPO / "eax.ps1").read_text(encoding="utf-8")
    assert '$initStep = @("init", $kind) + $modes' in ps and all(ord(c) < 128 for c in ps)
    sh = (REPO / "eax.sh").read_text(encoding="utf-8")
    assert 'steps=("cleanup --all --yes" "init $kind$modes"' in sh
    h = (REPO / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert "### clean-restart [laptop|server] [--certificate|--password] [--wait-all]" in h


@pytest.mark.skipif(not __import__("shutil").which("bash"), reason="bash is not here")
def test_the_shell_launcher_passes_the_mode_to_init(tmp_path):
    import subprocess
    sh = (REPO / "eax.sh").read_text(encoding="utf-8")
    block = sh[sh.index("  clean-run|clean-debug|clean-restart)"):sh.index("    export EAX_BUILD_PULL=1")]
    body = block.split("\n", 1)[1]
    script = f'CMD=clean-restart; ENV_FILE=/nonexistent\nset -- clean-restart server --certificate --wait-all\n{body}\nprintf "%s|" "${{steps[@]}}"\n'
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=20).stdout
    assert "init server --certificate|" in out


def test_the_secrets_page_switches_through_the_command_centre():
    web = (REPO / "services" / "web" / "src" / "Secrets.jsx").read_text(encoding="utf-8")
    assert 'argv: ["certs", "switch", to]' in web and "Switch to certificates" in web and "Switch to passwords" in web
    assert "<RestartOffer why={run.why} />" in web                   # the restart offered after it
    import json
    cat = json.loads((REPO / "services" / "web" / "src" / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "button:Switch to certificates" in cat and "button:Switch to passwords" in cat
    from eaxcli import commands
    assert commands.check_argv(["certs", "switch", "certificate"]) == ["certs", "switch", "certificate"]
