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
    (tmp_path / "used" / "x").write_text("x")                                           # not a drill's: never deleted
    assert "holds something other than an earlier drill's DR copy" in _drill(inst, tmp_path / "used", tmp_path / "temp", env).stdout
    assert (tmp_path / "used" / "x").exists()
    (tmp_path / "mine").mkdir()
    (tmp_path / "mine" / "notes.txt").write_text("x")
    r = _drill(inst, tmp_path / "dr2", tmp_path / "mine", env)
    assert r.returncode == 2 and "holds files other than an earlier drill's" in r.stdout and (tmp_path / "mine" / "notes.txt").exists()


def test_the_drill_uses_eax_dr_from_its_own_folder_and_keeps_the_dr_copy_apart():
    for f in ("eax-dr.ps1", "eax-dr.sh", "eax-drill.ps1", "eax-drill.sh", "dr-common.ps1", "dr-common.sh", "README.md"):
        assert (DR / f).exists(), f
    ps = (DR / "eax-drill.ps1").read_text()
    sh = (DR / "eax-drill.sh").read_text()
    assert 'Join-Path $Here "eax-dr.ps1"' in ps and '"$HERE/eax-dr.sh"' in sh                # eax-dr beside it
    assert "-Project $DrProject" in ps and '--project "$DR_PROJECT"' in sh                     # its own volumes (21:52)
    # the drill kept simple (the owner, 18 Nov 2026, 07:12): no test content; the backup taken out; a real sign-in
    for step in ("running", "backup", "take", "shutdown", "fingerprint", "compare", "signin", "code"):
        assert f'"drill", "{step}"' in ps and f"eax drill {step}" in sh, step
    for t in (ps, sh):
        assert "drill content" not in t.replace('"drill", "content', "drill content")
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
    assert D.main(["compare", str(a), str(b)]) == 0                                   # a row added: noted
    capsys.readouterr()
    b.write_text(json.dumps({"tables": {"eaexplorer core.models": [1, "x"]}, "files": {}}))
    # a file lost: a warning, never a failure (the owner, 18 Nov 2026, 07:12: "Key items, check is only a warning")
    assert D.main(["compare", str(a), str(b)]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    assert "error" not in out and any("persist/s.json: missing after" in w for w in out["warnings"])
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
mkdir -p "$here/work"; echo "$*" >> "$here/work/calls.txt"; [ -z "${CALLS_ALL:-}" ] || echo "$here: $*" >> "$CALLS_ALL"
case "$*" in
  'drill info') printf '{"version": "5.6.0", "repo": "https://github.com/a/b", "backups": "%s/bk", "config": "%s/work/eaexplorer.env"}\n' "$here" "$here";;
  'drill running') echo '{"running": true}';;
  'drill take '*) rm -rf "$4"; mkdir -p "$(dirname "$4")"; cp -R "$here/bk/$3" "$4" && echo '{"files": 3, "how": "from the backups folder"}';;
  'drill signin') echo '{"people": 5, "realm": "eaexplorer", "api": "answers"}';;
  'drill backup') echo '{"name": "20261116T010000Z-nightly"}';;
  'drill code '*) python3 -c 'import json, sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from eaxcli.drill import copy_code
print(json.dumps(copy_code(Path(sys.argv[2]), Path(sys.argv[3]))))' "@REPO@" "$3" "$here";;
  'drill compare '*) echo '{"tables": 5, "files": 2}';;
  'drill remove-copy '*) echo '{"containers": 3, "volumes": 2, "networks": 1}';;
  *) echo '{}';;
esac
'''


def _code_source(tmp_path: Path, version="5.6.0") -> Path:
    """EA Explorer's code stood in: version.toml, a customisation, and an eax.sh that answers."""
    src = tmp_path / "running"
    (src / "services" / "api" / "eax").mkdir(parents=True)
    (src / "services" / "api" / "version.toml").write_text(f'version = "{version}"\n')
    (src / "services" / "api" / "eax" / "our_connector.py").write_text("# set up on this machine only\n")
    (src / "library" / "Phase A").mkdir(parents=True)                                  # a name beyond ASCII (11:45)
    (src / "library" / "Phase A" / "TOGAF® Template [draft].docx").write_bytes(b"docx")
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
    # the core only before the restore (13:22: a new installation's sample data was waited for, up to 30 minutes, and
    # then replaced); everything waited for after it
    assert calls[:4] == ["up", "drill quiet on", "drill restore 20261116T010000Z-nightly", "up"]
    # 13:25: "The DR should let us in as soon as the web is up": the door opens on the core, the rest after it
    assert calls.index("drill quiet off") < calls.index("up --wait-all") < calls.index("test smoke")
    assert any(c.startswith("drill compare ") for c in calls) and calls[-3:] == ["drill quiet off", "up --wait-all", "test smoke"]
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
def test_eax_drill_runs_end_to_end_from_the_installations_own_code_with_no_github_and_puts_everything_back(tmp_path):
    """09:03: "For testing auto remove and create destination folders. Expect them to be cleaned and deleted"."""
    inst = _code_source(tmp_path)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    dr, temp = tmp_path / "dr1", tmp_path / "temp"
    (dr / "work").mkdir(parents=True)                                                   # an earlier drill's DR copy
    (dr / "work" / "compose-project").write_text("eaexplorer-dr\n")
    (temp / "drill-20261101T010101Z" / "backup").mkdir(parents=True)                    # and its temp folder
    env = {**_offline(tmp_path), "CALLS_ALL": str(tmp_path / "all-calls.txt")}
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(dr), "--temp", str(temp)],
                       env=env, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "PASSED" in r.stdout and "from the copied code (no GitHub)" in r.stdout
    assert not (tmp_path / "net.txt").exists()
    calls = (tmp_path / "all-calls.txt").read_text().splitlines()
    mine = [c.split(": ", 1)[1] for c in calls if c.startswith(f"{inst}: ")]
    there = [c.split(": ", 1)[1] for c in calls if c.startswith(f"{dr}: ")]
    assert mine[mine.index("drill running") + 1].startswith("drill preflight ")          # the pre-flight (D747)
    # the last drill's DR copy (left running for the owner, 18 Nov 2026, 07:46) removed first, before the running check
    assert mine.index("drill remove-copy eaexplorer-dr") < mine.index("drill running")
    # the backup and the code taken out while EA Explorer still runs (the owner's drill, 18 Nov 2026, 07:04), then shut down
    assert mine.index(next(c for c in mine if c.startswith("drill take "))) < mine.index("drill shutdown")
    assert mine.index(next(c for c in mine if c.startswith("drill code "))) < mine.index("drill shutdown")
    assert "drill signin" in there                                                       # a real sign-in to the DR copy
    assert "drill restore 20261116T010000Z-nightly" in there                             # built and restored there
    # 18 Nov 2026, 06:39: "not exhasutive ... number of rows or some key items": no smoke test unless asked (--smoke)
    assert "test smoke" not in there and "test smoke" not in mine
    # the DR copy left running for the owner to test, the installation left stopped (07:46); the backup kept
    assert mine[-1] == "drill shutdown" and not any(c.startswith(("drill delete-backup", "up")) for c in mine)
    assert (dr / "work" / "compose-project").exists() and not temp.exists()
    report = next((inst / "work" / "tests").glob("drill-*/report.md")).read_text()
    assert "Passed" in report and "The DR copy is left running" in report and ".\\eax stop" not in report
    assert "./eax stop" in report and "is kept (pinned)" in report
    assert (inst / "work" / "tests").glob("drill-*/drill.log")


def test_system_admin_has_a_disaster_recovery_tab_with_the_steps_and_commands_for_both_systems():
    """The owner, 17 Nov 2026, 00:04: "On backup and restore page add a tab for DR and provide commands and steps for setup"."""
    web = REPO / "services" / "web" / "src"
    admin, page = (web / "adminNav.js").read_text(), (web / "DisasterRecovery.jsx").read_text()   # D898
    assert admin.index('{ key: "restores", label: "Restores"') < admin.index('{ key: "disaster-recovery", label: "Disaster recovery"')
    for cmd in (".\\\\eax dr-pack", "./eax dr-pack", ".\\\\eax-dr -Pack .. -Install", "./eax-dr.sh --pack .. --install",
                ".\\\\dr\\\\eax-drill -Install", "./dr/eax-drill.sh --install", "eax test backup-restore"):
        assert cmd in page, cmd
    for step in ("Set it up: make a DR pack", "Recover on another machine", "Rehearse it: the restore drill", "A backup or DR: which one"):
        assert step in page, step
    assert "#/documentation/backup-disaster-recovery" in page and "needs no GitHub" in page


def test_a_programs_messages_on_its_error_stream_never_fail_a_powershell_step():
    """The owner's drill, 17 Nov 2026, 08:17: "FAIL a test project, models and content of every kind : the test's record:
    self-test run 14": Windows PowerShell 5.1 turned the test's progress line (on its error stream) into an error, and with
    $ErrorActionPreference = "Stop" it ended the step. Every program the scripts run goes through Invoke-Native, which turns
    such lines back into text; only the exit code says whether it failed."""
    common = (DR / "dr-common.ps1").read_text()
    assert 'function Invoke-Native' in common and '$ErrorActionPreference = "Continue"' in common
    assert "[System.Management.Automation.ErrorRecord]" in common
    assert "Invoke-Native { & $Ps -NoProfile -ExecutionPolicy Bypass -File $eaxPs1 @EaxArgs }" in common
    import re
    for f in ("eax-dr.ps1", "eax-drill.ps1"):
        for line in (DR / f).read_text().splitlines():
            code = line.split("#")[0]
            if re.search(r"&\s*(docker|git)\b", code):
                assert "Invoke-Native" in code, (f, line)                              # never a bare program call
            assert "2>&1" not in code and "*> $null" not in code, (f, line)



def test_no_step_block_can_see_step_s_own_variables_by_mistake():
    """The owner's drill, 17 Nov 2026, 09:02: a block inside Step read $name and got Step's $Name (the step's title), so the
    backup's copy was looked for under "...\\infrastructure\\the backup, the env file and the code copied ...". Step's own
    names now start with "step", and the scripts never use a name Step has."""
    import re
    common = (DR / "dr-common.ps1").read_text()
    step = common[common.index("function Step("):common.index("\n}\n", common.index("function Step("))]
    # $script:... names are the scripts' shared ones on purpose (the warnings, D747), not Step's own
    own = {v.lower() for v in re.findall(r"\$(?!script:)([A-Za-z]\w*)", step)} - {"results", "_", "true", "false"}
    assert own and all(v.startswith("step") for v in own), own
    for f in ("eax-dr.ps1", "eax-drill.ps1"):
        used = {v.lower() for v in re.findall(r"\$(?:script:)?([A-Za-z]\w*)", (DR / f).read_text())}
        assert not (used & own), (f, used & own)
        assert "$name" not in (DR / f).read_text().lower().replace("$backupname", "")


@needs_bash
def test_a_failed_drill_still_puts_everything_back_and_keeps_its_backup(tmp_path):
    inst = _code_source(tmp_path)
    # the DR copy restored but nobody can sign in: the one check after the restore that fails the drill (18 Nov 2026, 07:12)
    eax = (inst / "eax.sh").read_text().replace("""  'drill signin') echo '{"people": 5, "realm": "eaexplorer", "api": "answers"}';;""",
                                                """  'drill signin') echo '{"error": "nobody can sign in"}'; exit 1;;""")
    (inst / "eax.sh").write_text(eax)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    dr, temp = tmp_path / "dr1", tmp_path / "temp"
    env = {**_offline(tmp_path), "CALLS_ALL": str(tmp_path / "all-calls.txt")}
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(dr), "--temp", str(temp)],
                       env=env, capture_output=True, text=True, timeout=180)
    assert r.returncode == 1 and "FAILED" in r.stdout
    mine = [c.split(": ", 1)[1] for c in (tmp_path / "all-calls.txt").read_text().splitlines() if c.startswith(f"{inst}: ")]
    # the DR copy left as it is for the owner to look at, the installation left stopped (18 Nov 2026, 07:46)
    assert mine[-2] == "drill shutdown" and mine[-1].startswith("drill diagnose ")
    assert not any(c.startswith("drill delete-backup") for c in mine)                    # the backup kept
    assert dr.exists() and not temp.exists()
    report = next((inst / "work" / "tests").glob("drill-*/report.md")).read_text()
    assert "Failed" in report and "is kept (pinned)" in report


def test_remove_copy_never_touches_this_installation_and_the_powershell_drill_cleans_up_the_same_way(monkeypatch):
    monkeypatch.setattr(D, "project", lambda: "eaexplorer")
    assert "never removed" in D.remove_copy("eaexplorer")["error"] and "not a Docker name" in D.remove_copy("../x")["error"]
    seen = []

    class R:
        stdout = ""
    monkeypatch.setattr(D.subprocess, "run", lambda a, **k: seen.append(a) or R())
    assert D.remove_copy("eaexplorer-dr") == {"containers": 0, "volumes": 0, "networks": 0}   # images shared: kept
    assert not any("image" in a for a in seen)
    assert all("label=com.docker.compose.project=eaexplorer-dr" in a for a in seen)
    ps = (DR / "eax-drill.ps1").read_text()
    for must in ('Disposable-Dr $Dr', 'Disposable-Temp $Temp', '@("drill", "remove-copy", $DrProject)', '@("up", "--wait-all")',
                 'The DR copy is left running', 'work\\tests\\$Stamp', "Remove-Item -Recurse -Force -LiteralPath $Dr"):
        assert must in ps, must
    assert ps.index("Disposable-Temp $Temp") < ps.index("New-Item -ItemType Directory -Force $Run")


def test_shutdown_switches_every_profile_on_and_removes_what_compose_leaves(monkeypatch, tmp_path):
    """The owner's drill, 17 Nov 2026, 11:13: {"containers_left": 14, "error": "14 container(s) left"} after compose down."""
    monkeypatch.setattr(D, "compose_args", lambda a: ["docker", "compose", *a])
    monkeypatch.setattr(D, "project", lambda: "eaexplorer")
    left = {"ids": ["c1", "c2"]}
    seen = []

    class R:
        returncode, stderr = 0, ""

        def __init__(self, out=""):
            self.stdout = out

    def run(a, **k):
        seen.append((a, k.get("env", {}).get("COMPOSE_PROFILES")))
        if a[:3] == ["docker", "compose", "config"]:
            return R("analytics\ndocuments\nvault\n")
        if a[:3] == ["docker", "rm", "-f"]:
            left["ids"] = []
        return R(" ".join(left["ids"]) if a[:2] == ["docker", "ps"] else "")
    monkeypatch.setattr(D.subprocess, "run", run)
    out = D.shutdown()
    assert out == {"containers_left": 0, "removed_directly": 2, "profiles": ["analytics", "documents", "vault"]}
    down = next(x for x in seen if x[0][:3] == ["docker", "compose", "down"])
    assert down[1] == "analytics,documents,vault"                                   # every profile, by name
    assert (["docker", "rm", "-f", "c1", "c2"], None) in seen                       # only containers: no -v
    left["ids"] = ["c3"]
    monkeypatch.setattr(D.subprocess, "run", lambda a, **k: R("c3" if a[:2] == ["docker", "ps"] else ""))
    assert "1 container(s) left" in D.shutdown()["error"]


def test_a_step_that_answers_with_an_error_fails_even_when_its_exit_code_says_ok():
    """11:13: the drill took {"error": "14 container(s) left"} as "ok ... stopped"."""
    common = (DR / "dr-common.ps1").read_text()
    assert "if ($code -ne 0 -or ($json -and $json.error))" in common and "$code = $global:NativeExit" in common
    assert '[ -n "$(json_get error "$EAX_JSON" 2>/dev/null)" ]' in (DR / "dr-common.sh").read_text()
    for f in ("eax-dr.ps1", "eax-drill.ps1"):
        lines = (DR / f).read_text().splitlines()
        for i, line in enumerate(lines):
            if "$LASTEXITCODE" in line:
                assert "Invoke-Native" not in lines[i - 1], (f, line)                 # wrapped programs: NativeExit


@needs_bash
def test_the_bash_drill_stops_when_shutdown_answers_with_an_error_and_exit_zero(tmp_path):
    inst = _code_source(tmp_path)
    eax = (inst / "eax.sh").read_text().replace("  'drill compare '*)",
                                                "  'drill shutdown') echo '{\"containers_left\": 14, \"error\": \"14 container(s) left\"}';;\n  'drill compare '*)")
    (inst / "eax.sh").write_text(eax)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(tmp_path / "dr1"), "--temp",
                        str(tmp_path / "temp")], env=_offline(tmp_path), capture_output=True, text=True, timeout=180)
    assert r.returncode == 1 and "FAIL the installation shut down" in r.stdout and "14 container(s) left" in r.stdout
    assert "eax-dr" not in (inst / "work" / "calls.txt").read_text()


def test_every_text_file_the_powershell_scripts_read_is_read_as_utf8():
    """The owner's drill, 17 Nov 2026, 11:45: "TOGAF® Template - Architecture Definition.docx in the code is missing or does
    not match its checksum": Windows PowerShell 5.1 read CODE.sha256 as ANSI, so the name came out garbled."""
    import re
    for f in ("dr-common.ps1", "eax-dr.ps1", "eax-drill.ps1"):
        for line in (DR / f).read_text(encoding="utf-8").splitlines():
            for m in re.finditer(r"\b(Get-Content|Select-String)\b", line.split("#")[0]):
                assert line[m.end():].startswith(" -Encoding UTF8"), (f, line)



def test_eax_ps1_starts_in_a_folder_that_is_not_a_git_checkout():
    """The owner's drill, 17 Nov 2026, 12:28: in the DR copy (no .git) eax up stopped at "fatal: not a git repository":
    Windows PowerShell 5.1 with $ErrorActionPreference "Stop" turns a program's error-stream message into an error even
    with 2>$null. Every such call in eax.ps1 now goes through Invoke-Quiet (its error stream dropped, never an error)."""
    import re
    ps = (REPO / "eax.ps1").read_text(encoding="utf-8")
    fn = ps[ps.index("function Invoke-Quiet"):ps.index("\n}\n", ps.index("function Invoke-Quiet"))]
    assert '$ErrorActionPreference = "Continue"' in fn and "$global:QuietExit = $LASTEXITCODE" in fn
    for i, line in enumerate(ps.splitlines(), 1):
        code = line.split("#")[0]
        if "2>$null" in code:
            assert "& $Exe @Arguments 2>$null" in code, (i, line)                   # only inside Invoke-Quiet
        assert not re.search(r"&\s*git\b", code), (i, line)                         # git only through Invoke-Quiet
    assert 'Invoke-Quiet git @("rev-list", "--count", "HEAD")' in ps and "$global:QuietExit -ne 0" in ps   # D882


def test_the_drill_and_the_dr_tool_start_from_command_prompt_too():
    """The owner, 17 Nov 2026, 12:44: typed .\\dr\\eax-drill.ps1 in Command Prompt, which opened it in VS Code. eax-drill.cmd
    and eax-dr.cmd start them in PowerShell from either shell, as eax.cmd does; the documents show those names."""
    for n in ("eax-drill", "eax-dr"):
        cmd = (DR / f"{n}.cmd").read_bytes()
        assert b"\r\n" in cmd and f'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0{n}.ps1" %*'.encode() in cmd
        assert b"exit /b %ERRORLEVEL%" in cmd
    from eaxcli import drpack
    assert "eax-drill.cmd" in drpack.DR_FILES and "eax-dr.cmd" in drpack.DR_FILES
    for doc in ("docs/backup-disaster-recovery.md", "docs/backup-drill-monthly.md", "docs/testing.md", "dr/README.md",
                "services/web/src/DisasterRecovery.jsx", "services/web/src/TestRuns.jsx"):
        t = (REPO / doc).read_text(encoding="utf-8")
        assert "eax-drill.ps1 -Install" not in t and "eax-dr.ps1 -Pack" not in t, doc


def test_the_dr_tool_starts_only_the_core_before_the_restore_in_both_forms():
    ps, sh = (DR / "eax-dr.ps1").read_text(), (DR / "eax-dr.sh").read_text()
    assert 'Step "EA Explorer built and its core started" { Eax @("up") | Out-Null' in ps
    assert 'step "EA Explorer built and its core started" eax up\n' in sh
    for t, s in ((ps, "Step "), (sh, "step ")):
        assert t.index(s + '"EA Explorer built and its core') < t.index(s + '"the full restore of') \
            < t.index(s + '"EA Explorer\'s core started again') < t.index(s + '"the background back and the maintenance page off: everyone') < t.index(s + '"the rest up')

