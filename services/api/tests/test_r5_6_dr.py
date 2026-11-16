"""R5.6-B2: eax-dr (an environment built from a backup) and eax-drill (the restore drill, automated), in the dr folder
that runs on its own (owner, 16 Nov 2026, 20:24 to 20:29).

Here without Docker: the bash forms' checks really run (each refuses before anything is touched), the eax drill steps'
parts that need no containers, and how the pieces fit."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DR = REPO / "dr"
sys.path.insert(0, str(REPO))

from eaxcli import drill as D  # noqa: E402

needs_bash = pytest.mark.skipif(not shutil.which("bash") or not shutil.which("sha256sum"), reason="needs bash and sha256sum")


def _backup(tmp_path: Path, version="5.6.0", status="ok") -> Path:
    b = tmp_path / "safe" / "20261116T010000Z-nightly"
    (b / "databases").mkdir(parents=True)
    (b / "databases" / "eaexplorer.dump").write_bytes(b"dump")
    (b / "config").mkdir()
    (b / "config" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    sums = "".join(f"{hashlib.sha256((b / p).read_bytes()).hexdigest()}  {p}\n"
                   for p in ("config/eaexplorer.env", "databases/eaexplorer.dump"))
    (b / "SHA256SUMS").write_text(sums)
    (b / "manifest.json").write_text(json.dumps({"status": status, "version": version, "name": b.name}))
    return b


def _env(tmp_path: Path) -> Path:
    e = tmp_path / "safe" / "eaexplorer.env"
    e.parent.mkdir(exist_ok=True)
    e.write_text("EAX_DEPLOYMENT=laptop\nEAX_HOSTNAME=localhost\n")
    return e


def _dr(tmp_path, backup, install, version="5.6.0", env=None):
    environ = {**os.environ, "TMPDIR": str(tmp_path), "PATH": f"{tmp_path / 'nodocker'}:{os.environ['PATH']}"}
    (tmp_path / "nodocker").mkdir(exist_ok=True)
    (tmp_path / "nodocker" / "docker").write_text("#!/bin/sh\nexit 1\n")
    (tmp_path / "nodocker" / "docker").chmod(0o755)
    return subprocess.run(["bash", str(DR / "eax-dr.sh"), "--backup", str(backup), "--install", str(install),
                           "--version", version, "--env", str(env or _env(tmp_path))],
                          env=environ, capture_output=True, text=True, timeout=60)


@needs_bash
def test_eax_dr_refuses_a_bad_backup_before_touching_anything(tmp_path):
    install = tmp_path / "install"
    b = _backup(tmp_path)
    (b / "databases" / "eaexplorer.dump").write_bytes(b"changed")
    r = _dr(tmp_path, b, install)
    assert r.returncode == 1 and "does not match its checksum" in r.stdout and not install.exists()
    reports = list(tmp_path.glob("eax-dr-*/report.md"))
    assert reports and "Failed" in reports[0].read_text() and "checks (nothing touched yet)" in reports[0].read_text()
    (b / "manifest.json").unlink()
    assert "not an infrastructure backup" in _dr(tmp_path, b, install).stdout


@needs_bash
def test_eax_dr_refuses_a_newer_backup_a_failed_one_a_full_folder_and_no_docker(tmp_path):
    install = tmp_path / "install"
    assert "newer than 5.5.0" in _dr(tmp_path, _backup(tmp_path, "5.6.0"), install, version="5.5.0").stdout
    shutil.rmtree(tmp_path / "safe")
    assert "manifest says failed" in _dr(tmp_path, _backup(tmp_path, status="failed"), install).stdout
    shutil.rmtree(tmp_path / "safe")
    b = _backup(tmp_path)
    install.mkdir()
    (install / "something").write_text("x")
    assert "is not empty" in _dr(tmp_path, b, install).stdout and (install / "something").exists()
    shutil.rmtree(install)
    r = _dr(tmp_path, b, install)
    assert "Docker does not answer" in r.stdout and not install.exists()


def _fake_install(tmp_path, running=True):
    """An installation stood in: its eax.sh answers the drill's steps and writes down every command it is given."""
    inst = tmp_path / "EA-Explorer"
    (inst / "work").mkdir(parents=True)
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    run = '{"running": true}' if running else '{"running": false, "error": "EA Explorer is not running here (eaexplorer): start it with eax up first"}'
    (inst / "eax.sh").write_text(
        "#!/bin/sh\necho \"$*\" >> \"$(dirname \"$0\")/calls.txt\"\n"
        "case \"$*\" in\n"
        "  'drill info') echo '{\"version\": \"5.6.0\", \"repo\": \"https://github.com/a/b\", \"backups\": \"x\", \"config\": \"y\"}';;\n"
        f"  'drill running') echo '{run}'; [ {1 if running else 0} -eq 1 ] || exit 1;;\n"
        "  *) exit 0;;\nesac\n")
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "docker").write_text("#!/bin/sh\nexit 0\n")
    (bin_ / "docker").chmod(0o755)
    return inst, {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"}


def _drill(inst, dr, temp, env):
    return subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(dr), "--temp", str(temp)],
                          env=env, capture_output=True, text=True, timeout=60)


@needs_bash
def test_eax_drill_stops_when_the_installation_is_not_running(tmp_path):
    """The owner's design (21:40): "check if that install is running or not; if its not running stop"."""
    inst, env = _fake_install(tmp_path, running=False)
    r = _drill(inst, tmp_path / "dr1", tmp_path / "temp", env)
    assert r.returncode == 1 and "is not running here" in r.stdout
    calls = (inst / "calls.txt").read_text().split("\n")
    assert "drill running" in calls and not any(c.startswith(("drill content", "drill backup", "drill shutdown", "drill quiet"))
                                                for c in calls)                        # nothing touched
    assert not (tmp_path / "dr1").exists() and "Back to the installation" not in r.stdout


@needs_bash
def test_eax_drill_always_needs_a_new_folder_apart_from_the_installation(tmp_path):
    """21:40: "ensure it doesnt override the current running folder. Alwyas needs a new folder"."""
    inst, env = _fake_install(tmp_path)
    assert "must be a folder of its own" in _drill(inst, inst / "dr", tmp_path / "temp", env).stdout
    assert "must be a folder of its own" in _drill(inst, tmp_path / "dr", inst / "temp", env).stdout
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "x").write_text("x")
    assert "is not empty" in _drill(inst, tmp_path / "used", tmp_path / "temp", env).stdout
    assert not (inst / "calls.txt").exists()                                            # eax never called


def test_the_drill_uses_eax_dr_from_its_own_folder_and_keeps_the_dr_copy_apart():
    for f in ("eax-dr.ps1", "eax-dr.sh", "eax-drill.ps1", "eax-drill.sh", "dr-common.ps1", "dr-common.sh", "README.md"):
        assert (DR / f).exists(), f
    ps = (DR / "eax-drill.ps1").read_text()
    sh = (DR / "eax-drill.sh").read_text()
    assert 'Join-Path $Here "eax-dr.ps1"' in ps and '"$HERE/eax-dr.sh"' in sh                # eax-dr beside it
    assert "-Project $DrProject" in ps and '--project "$DR_PROJECT"' in sh                     # its own volumes (21:52)
    for step in ("running", "content", "backup", "shutdown", "fingerprint", "compare", "content-check", "content-remove", "code"):
        assert f'"drill", "{step}"' in ps and f"eax drill {step}" in sh, step
    for t in (ps, sh):
        assert "Remove-Item -LiteralPath $Install" not in t and 'rm -rf "$INSTALL"' not in t   # the installation is never deleted
        assert "teardown" not in t
    for f in ("eax-dr.ps1", "eax-dr.sh"):
        t = (DR / f).read_text()
        assert ("drill restore" in t or '"drill", "restore"' in t) and "releases/tags/v" in (DR / ("dr-common" + Path(f).suffix)).read_text()
        assert "Read-Host" not in t and "read -r -p" not in t                                 # nothing is asked
        assert "compose-project" in t
    assert "[Alias(\"Env\")][string]$EnvFile" in (DR / "eax-dr.ps1").read_text()
    # the code goes with the backup, as in a DR pack: the drill never needs GitHub (22:44)
    assert '-Code (Join-Path $Run "code")' in ps and '--code "$RUN/code"' in sh
    assert "Get-Release" not in ps and "release_published" not in sh
    dps = (DR / "eax-dr.ps1").read_text()
    assert "Test-CodeWhole $Code $Version" in dps and '(Join-Path $Pack "code")' in dps and "[switch]$GitHub" in dps
    assert "function Test-CodeWhole" in (DR / "dr-common.ps1").read_text() and "code_whole()" in (DR / "dr-common.sh").read_text()


def test_an_installation_can_have_its_own_docker_name_in_every_form():
    """work/compose-project (not the config file, so a restore never changes it)."""
    assert 'if (Test-Path "work/compose-project") { $env:COMPOSE_PROJECT_NAME' in (REPO / "eax.ps1").read_text()
    assert "if [ -f work/compose-project ]; then COMPOSE_PROJECT_NAME=" in (REPO / "eax.sh").read_text()
    assert 'os.environ["COMPOSE_PROJECT_NAME"] = (WORK / "compose-project")' in (REPO / "eaxcli/core.py").read_text()


def test_eax_drill_steps_answer_in_json_and_never_from_the_web(tmp_path, capsys, monkeypatch):
    assert D.backups_folder("") == D.WORK / "backups" and D.backups_folder("eax-backups") == D.WORK / "backups"
    assert D.backups_folder("/srv/eax/backups") == Path("/srv/eax/backups")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"tables": {"eaexplorer core.models": [1, "x"]}, "files": {"persist/s.json": "1"}}))
    b.write_text(a.read_text())
    assert D.main(["compare", str(a), str(b)]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[0])["tables"] == 1
    b.write_text(json.dumps({"tables": {"eaexplorer core.models": [2, "y"]}, "files": {"persist/s.json": "1"}}))
    assert D.main(["compare", str(a), str(b)]) == 1
    assert "1 rows before, 2 after" in json.loads(capsys.readouterr().out.strip().splitlines()[0])["error"]
    assert D.main(["nonsense"]) == 1
    from eaxcli import commands
    assert "drill" in commands.HOST and "eax-drill" in commands.HOST_WHY["drill"]
    st = tmp_path / "state.json"
    st.write_text(json.dumps({"sid": "x", "snapshot": {"tags": {"rows": 1, "sum": "a"}}}))
    monkeypatch.setattr(D, "_api", lambda cmd, state: {"tags": {"rows": 1, "sum": "a"}})
    assert D.main(["content-check", str(st)]) == 0
    monkeypatch.setattr(D, "_api", lambda cmd, state: {"tags": {}})
    assert D.main(["content-check", str(st)]) == 1 and "differs" in capsys.readouterr().out
    assert '"allow", "drill", "dr-pack", "sign"' in (REPO / "eax.ps1").read_text() and "allow|drill|dr-pack|sign" in (REPO / "eax.sh").read_text()
    assert 'elif command == "drill":' in (REPO / "eaxcli/main.py").read_text()
    assert "### drill" in (REPO / "eaxcli/help.txt").read_text()


# ---------------------------------------------------------------- the code in the pack: no GitHub (owner, 16 Nov 2026, 22:44)
FAKE_EAX = r'''#!/bin/sh
# an installation stood in: every command written down (in work/, which is never code), each answered
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$here/work"; echo "$*" >> "$here/work/calls.txt"
case "$*" in
  'drill info') printf '{"version": "5.6.0", "repo": "https://github.com/a/b", "backups": "%s/bk", "config": "%s/work/eaexplorer.env"}\n' "$here" "$here";;
  'drill running') echo '{"running": true}';;
  'drill content '*) echo '{"made": 3}';;
  'drill backup') echo '{"name": "20261116T010000Z-nightly"}';;
  'drill code '*) python3 -c 'import json, sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from eaxcli.drill import copy_code
print(json.dumps(copy_code(Path(sys.argv[2]), Path(sys.argv[3]))))' "@REPO@" "$3" "$here";;
  'drill compare '*) echo '{"tables": 5, "files": 2}';;
  *) echo '{}';;
esac
'''


def _code_source(tmp_path: Path, version="5.6.0") -> Path:
    """EA Explorer's code stood in: version.toml, a customisation, and an eax.sh that answers."""
    src = tmp_path / "running"
    (src / "services" / "api" / "eax").mkdir(parents=True)
    (src / "services" / "api" / "version.toml").write_text(f'version = "{version}"\n')
    (src / "services" / "api" / "eax" / "our_connector.py").write_text("# set up on this machine only\n")
    (src / "eax.sh").write_text(FAKE_EAX.replace("@REPO@", str(REPO)))
    return src


def _offline(tmp_path: Path) -> dict:
    """Docker answers; git and curl only write down that they were called, and fail (no GitHub here)."""
    b = tmp_path / "bin"
    b.mkdir(exist_ok=True)
    for name, body in (("docker", "exit 0"), ("git", f'echo git >> "{tmp_path}/net.txt"; exit 1'),
                       ("curl", f'echo curl >> "{tmp_path}/net.txt"; exit 1')):
        (b / name).write_text(f"#!/bin/sh\n{body}\n")
        (b / name).chmod(0o755)
    return {**os.environ, "TMPDIR": str(tmp_path), "PATH": f"{b}:{os.environ['PATH']}",
            "EAX_GITHUB_API": "http://127.0.0.1:9/none"}


def _pack(tmp_path: Path, version="5.6.0") -> Path:
    from eaxcli import drpack as P
    pack = tmp_path / "pack"
    b = _backup(tmp_path)
    shutil.copytree(b, pack / "backup" / b.name)
    (pack / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    (pack / "VERSION.txt").write_text("5.6.0\n")
    (pack / "fingerprint.json").write_text("{}")
    D.copy_code(pack / "code", _code_source(tmp_path, version))
    P.write_sums(pack)
    return pack


@needs_bash
def test_eax_dr_builds_from_the_packs_code_with_no_github(tmp_path):
    pack = _pack(tmp_path)
    new = tmp_path / "new"
    r = subprocess.run(["bash", str(DR / "eax-dr.sh"), "--pack", str(pack), "--install", str(new)],
                       env=_offline(tmp_path), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "GitHub not needed" in r.stdout and "(no GitHub)" in r.stdout and "DONE" in r.stdout
    assert not (tmp_path / "net.txt").exists()                                        # neither git nor curl
    assert (new / "services" / "api" / "eax" / "our_connector.py").exists()            # the customisation came too
    assert not (new / "CODE.sha256").exists() and os.access(new / "eax.sh", os.X_OK)
    calls = (new / "work" / "calls.txt").read_text().splitlines()
    assert calls[:3] == ["up --wait-all", "drill quiet on", "drill restore 20261116T010000Z-nightly"]
    assert any(c.startswith("drill compare ") for c in calls) and calls[-2:] == ["drill quiet off", "test smoke"]
    assert (new / "work" / "backups" / "infrastructure" / "20261116T010000Z-nightly" / "manifest.json").exists()


@needs_bash
def test_eax_dr_refuses_damaged_code_or_code_of_another_version(tmp_path):
    from eaxcli import drpack as P
    pack = _pack(tmp_path, version="5.5.9")
    r = subprocess.run(["bash", str(DR / "eax-dr.sh"), "--pack", str(pack), "--install", str(tmp_path / "new")],
                       env=_offline(tmp_path), capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "the code is of version 5.5.9, not 5.6.0" in r.stdout and not (tmp_path / "new").exists()
    shutil.rmtree(tmp_path / "pack")
    shutil.rmtree(tmp_path / "running")
    shutil.rmtree(tmp_path / "safe")
    pack = _pack(tmp_path)
    (pack / "code" / "services" / "api" / "eax" / "our_connector.py").write_text("changed")
    P.write_sums(pack)                                     # the pack's own checksums agree; the code's do not
    r = subprocess.run(["bash", str(DR / "eax-dr.sh"), "--pack", str(pack), "--install", str(tmp_path / "new")],
                       env=_offline(tmp_path), capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "does not match its checksum" in r.stdout and not (tmp_path / "new").exists()
    assert not (tmp_path / "net.txt").exists()


@needs_bash
def test_eax_drill_runs_end_to_end_from_the_installations_own_code_with_no_github(tmp_path):
    inst = _code_source(tmp_path)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    dr, temp = tmp_path / "dr1", tmp_path / "temp"
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(dr), "--temp", str(temp)],
                       env=_offline(tmp_path), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "PASSED" in r.stdout and "from the copied code (no GitHub)" in r.stdout
    assert not (tmp_path / "net.txt").exists()
    mine = (inst / "work" / "calls.txt").read_text().splitlines()
    assert mine.index("drill shutdown") < mine.index(next(c for c in mine if c.startswith("drill code ")))
    assert (dr / "services" / "api" / "eax" / "our_connector.py").exists()             # the DR copy has its code
    assert (dr / "work" / "compose-project").read_text().strip() == "eaexplorer-dr"
    drc = (dr / "work" / "calls.txt").read_text().splitlines()
    assert "drill restore 20261116T010000Z-nightly" in drc and "test smoke" in drc
    run = next(temp.glob("drill-*"))
    assert not (run / "code").exists() and not (run / "backup").exists()               # copies removed after a pass
    assert "Passed" in (run / "report.md").read_text()


def test_system_admin_has_a_disaster_recovery_tab_with_the_steps_and_commands_for_both_systems():
    """The owner, 17 Nov 2026, 00:04: "On backup and restore page add a tab for DR and provide commands and steps for setup"."""
    web = REPO / "services" / "web" / "src"
    admin, page = (web / "Admin.jsx").read_text(), (web / "DisasterRecovery.jsx").read_text()
    assert admin.index('["restores", "Restores"') < admin.index('["disaster-recovery", "Disaster recovery"')
    assert '"#/admin/disaster-recovery"' in (web / "menu.js").read_text()
    for cmd in (".\\\\eax dr-pack", "./eax dr-pack", ".\\\\eax-dr.ps1 -Pack .. -Install", "./eax-dr.sh --pack .. --install",
                ".\\\\dr\\\\eax-drill.ps1 -Install", "./dr/eax-drill.sh --install", "eax test backup-restore"):
        assert cmd in page, cmd
    for step in ("Set it up: make a DR pack", "Recover on another machine", "Rehearse it: the restore drill", "A backup or DR: which one"):
        assert step in page, step
    assert "#/documentation/backup-disaster-recovery" in page and "needs no GitHub" in page
