"""R13.4 (Release 13, D899): every command-line option is documented (owner, 23 Nov 2026, 21:29: "Please do 13.4"; 21:30:
"Ensure there are unit tests for checking this"). Every option the eax code reads is in eaxcli/help.txt, or, for the DR
tools, in their own --help; an option the code passes on to another program (Docker, Git, pytest, uv) or to one of
eax's own helper programs is named below with whose it is. A new option the help does not name fails eax dev check.
A count on 22 Nov 2026 found about 30 eax options not in help.txt; on 23 Nov 2026 it was 25 of eax's own and the 14
of the DR tools (which had no --help at all)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HELP = (ROOT / "eaxcli" / "help.txt").read_text(encoding="utf-8")
DR = ROOT / "dr"
OPTION = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")

# options eax passes on and never reads itself: whose they are (none of them is an eax option to document)
PASSED_ON = {
    # docker and docker compose
    "--ansi": "docker compose", "--progress": "docker compose", "--env-file": "docker compose", "--profile": "docker compose",
    "--profiles": "docker compose", "--rm": "docker compose run", "--no-deps": "docker compose", "--entrypoint": "docker compose run",
    "--force-recreate": "docker compose up",
    "--no-recreate": "docker compose up", "--pull": "docker compose up", "--scale": "docker compose up",
    "--remove-orphans": "docker compose down", "--services": "docker compose config and ps", "--filter": "docker ps",
    "--format": "docker and git", "--tail": "docker logs", "--timestamps": "docker logs", "--detach": "docker run",
    "--no-cache": "docker build", "--ignore-buildable": "docker compose pull",
    "--follow": "docker logs (the screen only refuses a typed -f or --follow; eax logs follows by itself)",
    # git
    "--count": "git rev-list", "--porcelain": "git status", "--untracked-files": "git status", "--bare": "git init",
    "--depth": "git fetch", "--heads": "git ls-remote", "--tags": "git ls-remote", "--no-tags": "git fetch",
    "--quiet": "git, docker compose and uv",
    # pytest and its coverage plugin
    "--cov": "pytest-cov", "--cov-report": "pytest-cov", "--continue-on-collection-errors": "pytest",
    # uv pip (the screen's library)
    "--python": "uv pip", "--target": "uv pip",
    # eax's own helper programs, started by eax itself, never typed
    "--id": "the updater's detached run (updater.py)", "--cache": "releases.py, run by the updater",
    "--scratch": "the backup container's restore.sh (a trial restore)",
    "--fresh": "update-ca-certificates (eax.sh, taking the local certificate authority away)",
    # not options: code that reads options
    "--x": "a docstring of commands.py (--x <v>)", "--no-": "estimate_cli.py takes --no-<part> apart",
}


def _found() -> dict[str, set[str]]:
    """Every --option written in the eax code: eaxcli/*.py, eax.ps1 and eax.sh."""
    out: dict[str, set[str]] = {}
    for f in sorted((ROOT / "eaxcli").glob("*.py")):
        for m in re.finditer(r"""["'](--[a-z][a-z0-9-]*)(?:=|["'\s])""", f.read_text(encoding="utf-8")):
            out.setdefault(m.group(1), set()).add(f.name)
    for name in ("eax.ps1", "eax.sh"):
        for o in OPTION.findall((ROOT / name).read_text(encoding="utf-8")):
            out.setdefault(o, set()).add(name)
    return out


def _dr_help(tool: str) -> str:
    """A DR tool's --help, as eax-<tool>.sh prints it (the same text is in eax-<tool>.ps1)."""
    src = (DR / f"{tool}.sh").read_text(encoding="utf-8")
    return src[src.index("cat <<'USAGE'\n") + 14:src.index("\nUSAGE\n")]


def _section(command: str) -> str:
    """help.txt's section of one command: its ### line to the next."""
    at = re.search(rf"^### {re.escape(command)}\b.*$", HELP, re.M)
    assert at, command
    end = HELP.find("\n### ", at.end())
    return HELP[at.start():end if end > 0 else len(HELP)]


def test_every_option_the_code_reads_is_documented():
    documented = set(OPTION.findall(HELP)) | set(OPTION.findall(_dr_help("eax-dr"))) | set(OPTION.findall(_dr_help("eax-drill")))
    missing = {o: sorted(f) for o, f in _found().items() if o not in documented and o not in PASSED_ON}
    assert not missing, ("Options the eax code reads that no help names: add each to eaxcli/help.txt under its command "
                         f"(or, if eax only passes it on, to PASSED_ON with whose it is): {missing}")


def test_the_passed_on_list_stays_true():
    """Nothing on the list is documented as eax's own, and everything on it is still in the code (no stale names)."""
    found, documented = _found(), set(OPTION.findall(HELP))
    assert not (set(PASSED_ON) & documented), set(PASSED_ON) & documented
    assert not [o for o in PASSED_ON if o not in found], [o for o in PASSED_ON if o not in found]


def test_the_command_centres_and_jenkins_fields_are_in_their_commands_help():
    """Every option the Command centre and Jenkins offer as a field (commands.OVERRIDES) is in that command's own
    section of help.txt."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import commands as C
    for command, params in C.OVERRIDES.items():
        text = _section(command)
        for p in params:
            offered = p["key"].split("/") if p["key"].startswith("--") else []
            offered += [x for x in p.get("flags") or [] if x.startswith("--")]
            if p["type"] == "flags":
                offered += [x for x in p.get("choices") or [] if str(x).startswith("--")]
            for o in sorted(set(offered)):
                assert o in text, f"{command}: {o} is offered as a field but its help does not name it"


def test_restore_models_fields_are_in_its_help():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import jenkins as J
    text = _section("restore-model")
    for p in J.EXTRA_PARAMS["restore-model"]:
        if p["key"].startswith("--"):
            assert p["key"] in text, p["key"]


def test_the_dr_tools_say_every_option_they_take():
    """eax-dr and eax-drill: every option they read (the shell and the PowerShell forms alike) is in their --help, and
    so is every field Jenkins offers for them."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import jenkins as J
    ps_name = {"EnvFile": "--env", "GitHub": "--github", "KeepQuiet": "--keep-quiet", "NoSmoke": "--no-smoke",
               "SmokeAfter": "--smoke-after", "ThenBack": "--then-back"}
    for tool in ("eax-dr", "eax-drill"):
        text = _dr_help(tool)
        sh = (DR / f"{tool}.sh").read_text(encoding="utf-8")
        cases = sh[sh.index('while [ $# -gt 0 ]; do'):sh.index("esac", sh.index('while [ $# -gt 0 ]; do'))]
        sh_opts = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]*)\)", cases)) - {"--help"}
        ps = (DR / f"{tool}.ps1").read_text(encoding="utf-8")
        block = ps[ps.index("param("):ps.index("\n)\n", ps.index("param("))]
        ps_opts = {ps_name.get(n, "--" + n.lower()) for n in re.findall(r"\]\$([A-Za-z]+)", block)} - {"--help", "--rest"}
        assert sh_opts == ps_opts, (tool, sh_opts ^ ps_opts)                # the two forms take the same options
        for o in sh_opts | {"--help"}:
            assert o in text, (tool, o)
        for p in J.DR_TOOLS[tool]["params"]:
            assert p["key"] in text, (tool, p["key"])
        # both forms answer --help, and a missing folder or an unknown option shows the help and fails
        assert "-h|--help) usage; exit 0;;" in sh
        assert "if ($Help -or ($Rest | Where-Object { $_ -in @('--help', '-h', '/?', '-?') })) { Show-Usage; exit 0 }" in ps
        assert 'if ($Rest) { Write-Host "Unknown option $($Rest[0])" -ForegroundColor Red; Show-Usage; exit 2 }' in ps
        for line in text.split("\n"):                                       # the same words in both
            assert f"'{line.replace(chr(39), chr(39) * 2)}'" in ps, (tool, line)


@pytest.mark.skipif(not shutil.which("bash"), reason="no bash here")
@pytest.mark.parametrize("tool", ["eax-dr", "eax-drill"])
def test_the_dr_tools_print_their_help(tool):
    r = subprocess.run(["bash", str(DR / f"{tool}.sh"), "--help"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and r.stdout.strip() == _dr_help(tool).strip(), r.stdout + r.stderr
    r = subprocess.run(["bash", str(DR / f"{tool}.sh"), "--no-such-option"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2


def test_help_txt_stays_ascii():
    """eax.ps1 reads help.txt on Windows PowerShell 5.1 (D331): ASCII only."""
    bad = [i for i, line in enumerate(HELP.split("\n"), 1) if any(ord(c) > 127 for c in line)]
    assert not bad, bad[:10]
    for tool in ("eax-dr", "eax-drill"):
        for ext in ("ps1", "sh"):
            text = (DR / f"{tool}.{ext}").read_text(encoding="utf-8")
            assert all(ord(c) < 128 for c in text), f"{tool}.{ext}"
