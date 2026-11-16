"""R5.6-B2: eax dr-pack, a DR pack in one command with checksums and a fingerprint (owner, 16 Nov 2026, 22:12: "can
the DR pack that is generated have some sort of has or fingerprints, which can compare after DR restore to ensure
everything was done in DR tool?"; 22:13: "One command: eax dr-pack"), and eax-dr -Pack checking it."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import drpack as P  # noqa: E402
from eaxcli.core import Failure  # noqa: E402


def _fake(monkeypatch, tmp_path, running=True):
    """The installation stood in: its backup lands in tmp_path/backups, its config in work."""
    work = tmp_path / "inst" / "work"
    (work).mkdir(parents=True)
    (work / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\nEAX_DB_PASSWORD=s3cret\n")
    (tmp_path / "inst" / "dr").mkdir()
    for f in P.DR_FILES:
        (tmp_path / "inst" / "dr" / f).write_text(f"# {f}\n")
    code = tmp_path / "inst"                                          # its code, and what is not code
    (code / "services" / "api" / "eax").mkdir(parents=True)
    (code / "services" / "api" / "version.toml").write_text('[release]\nversion = "5.6.0"\n')
    (code / "services" / "api" / "eax" / "plugin_of_ours.py").write_text("# a customisation, never committed\n")
    (code / "eax.sh").write_text("#!/bin/sh\n")
    for junk in (".git/HEAD", "services/web/node_modules/x/index.js", "services/api/eax/__pycache__/a.pyc", "work/logs/x.log"):
        (code / junk).parent.mkdir(parents=True, exist_ok=True)
        (code / junk).write_text("x")
    monkeypatch.setattr(P, "WORK", work)
    monkeypatch.setattr(P, "ROOT", tmp_path / "inst")
    monkeypatch.setattr(P, "version", lambda: "5.6.0")
    monkeypatch.setattr(P, "say", lambda *a, **k: None)
    monkeypatch.setattr(P.DRL, "running", lambda: {"running": running} if running else {"running": False, "error": "not running"})
    monkeypatch.setattr(P.DRL, "info", lambda: {"backups": str(tmp_path / "backups")})
    calls = []

    def ops(*a):
        calls.append(a[0] + (" " + a[1] if len(a) > 1 else ""))
        if a[0] == "fingerprint":
            return {"tables": {"eaexplorer core.models": [3, "abc"]}, "files": {"persist/s.json": "1"}}
        if a[0] == "backup":
            b = tmp_path / "backups" / "20261116T220000Z-dr-pack"
            (b / "databases").mkdir(parents=True)
            (b / "databases" / "eaexplorer.dump").write_bytes(b"dump")
            (b / "manifest.json").write_text('{"status": "ok", "version": "5.6.0"}')
            (b / "SHA256SUMS").write_text(f"{P.sha256(b / 'databases' / 'eaexplorer.dump')}  databases/eaexplorer.dump\n")
            return {"name": b.name, "bytes": 4, "seconds": 1}
        return {}
    monkeypatch.setattr(P.DRL, "_ops", ops)
    monkeypatch.setattr(P.DRL, "_api", lambda cmd, state: calls.append(f"api {cmd}") or {"idle": True})
    return calls


def test_the_pack_holds_the_backup_version_env_tool_fingerprint_and_a_checksum_of_every_file(monkeypatch, tmp_path):
    calls = _fake(monkeypatch, tmp_path)
    pack = tmp_path / "pack"
    assert P.main([str(pack)]) == 0
    assert calls == ["quiet on", "api idle", "fingerprint", "backup dr-pack", "quiet off"]   # drained, then the two
    assert (pack / "VERSION.txt").read_text() == "5.6.0\n"
    assert (pack / "eaexplorer.env").read_text().startswith("EAX_DEPLOYMENT=laptop")
    assert json.loads((pack / "fingerprint.json").read_text())["tables"]["eaexplorer core.models"] == [3, "abc"]
    assert (pack / "backup" / "20261116T220000Z-dr-pack" / "manifest.json").exists()
    assert {f.name for f in (pack / "dr").iterdir()} == set(P.DR_FILES)
    assert "-Pack .. -Install" in (pack / "RESTORE.txt").read_text() and "5.6.0" in (pack / "RESTORE.txt").read_text()
    sums = (pack / "PACK.sha256").read_text().splitlines()
    listed = {ln.split("  ", 1)[1] for ln in sums}
    assert {"VERSION.txt", "eaexplorer.env", "fingerprint.json", "RESTORE.txt", "dr/eax-dr.ps1",
            "backup/20261116T220000Z-dr-pack/databases/eaexplorer.dump"} <= listed and "PACK.sha256" not in listed
    assert P.check_sums(pack) == []
    # the code as it runs (owner, 22:44 and 22:47: not git's: a customisation comes too), without work/, git, packages, caches
    got = {p.relative_to(pack / "code").as_posix() for p in (pack / "code").rglob("*") if p.is_file()}
    assert got == {"services/api/version.toml", "services/api/eax/plugin_of_ours.py", "eax.sh", "CODE.sha256",
                   *(f"dr/{f}" for f in P.DR_FILES)}
    assert {"code/CODE.sha256", "code/services/api/eax/plugin_of_ours.py"} <= listed
    assert P.DRL.check_code(pack / "code") == []
    assert "no GitHub" in (pack / "RESTORE.txt").read_text()
    (pack / "VERSION.txt").write_text("9.9.9\n")
    (pack / "dr" / "eax-dr.sh").unlink()
    assert sorted(P.check_sums(pack)) == ["VERSION.txt: changed", "dr/eax-dr.sh: missing"]


def test_the_page_comes_off_when_the_backup_fails_and_a_pack_needs_a_new_folder_outside_the_installation(monkeypatch, tmp_path):
    calls = _fake(monkeypatch, tmp_path)
    good = P.DRL._ops
    monkeypatch.setattr(P.DRL, "_ops", lambda *a: {"error": "disk full"} if a[0] == "backup" else good(*a))
    with pytest.raises(Failure, match="the backup: disk full"):
        P.main([str(tmp_path / "pack")])
    assert calls[-1] == "quiet off"
    with pytest.raises(Failure, match="inside the installation's folder"):
        P.main([str(P.WORK / "pack")])
    with pytest.raises(Failure, match="inside the installation's folder"):
        P.main([str(P.ROOT / "dr-pack")])                                   # it would copy itself as code
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "x").write_text("x")
    with pytest.raises(Failure, match="not empty"):
        P.main([str(tmp_path / "used")])


def test_no_pack_when_ea_explorer_is_not_running(monkeypatch, tmp_path):
    calls = _fake(monkeypatch, tmp_path, running=False)
    with pytest.raises(Failure, match="not running"):
        P.main([str(tmp_path / "pack")])
    assert calls == []


@pytest.mark.skipif(not shutil.which("bash") or not shutil.which("sha256sum"), reason="needs bash and sha256sum")
def test_eax_dr_checks_the_pack_before_anything_else(monkeypatch, tmp_path):
    _fake(monkeypatch, tmp_path)
    pack = tmp_path / "pack"
    P.main([str(pack)])
    (pack / "fingerprint.json").write_text("{}")                                    # damaged on the way
    env = {**os.environ, "TMPDIR": str(tmp_path)}
    r = subprocess.run(["bash", str(REPO / "dr" / "eax-dr.sh"), "--pack", str(pack), "--install", str(tmp_path / "new")],
                       env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "does not match its checksum" in r.stdout and not (tmp_path / "new").exists()
    assert "the DR pack is whole" in r.stdout


def test_eax_drill_code_refuses_a_used_folder_and_finds_a_changed_file(tmp_path):
    root = tmp_path / "inst"
    (root / "services" / "api").mkdir(parents=True)
    (root / "services" / "api" / "version.toml").write_text('version = "5.6.0"\n')
    (root / "a.py").write_text("a")
    out = P.DRL.copy_code(tmp_path / "c", root)
    assert out["files"] == 2 and out["version"] == "5.6.0"
    (tmp_path / "c" / "a.py").write_text("changed")
    (tmp_path / "c" / "services" / "api" / "version.toml").unlink()
    assert sorted(P.DRL.check_code(tmp_path / "c")) == ["a.py: missing or changed", "services/api/version.toml: missing or changed"]
    with pytest.raises(Failure, match="not empty"):
        P.DRL.copy_code(tmp_path / "c", root)
    inner = P.DRL.copy_code(root / "copy", root)                            # a folder inside it is not copied into itself
    assert inner["files"] == 2 and not (root / "copy" / "copy").exists()


def test_eax_dr_compares_the_fingerprint_and_a_given_env_file_is_not_checked():
    ps = (REPO / "dr" / "eax-dr.ps1").read_text()
    sh = (REPO / "dr" / "eax-dr.sh").read_text()
    assert '"drill", "compare", $Fingerprint' in ps and 'eax drill compare "$FINGERPRINT"' in sh
    assert '$EnvGiven -and $Matches[2] -eq "eaexplorer.env"' in ps and "grep -v '  eaexplorer.env$' PACK.sha256" in sh
    assert '"allow", "drill", "dr-pack", "sign"' in (REPO / "eax.ps1").read_text()
    assert "allow|drill|dr-pack|sign" in (REPO / "eax.sh").read_text()
    assert 'elif command == "dr-pack":' in (REPO / "eaxcli/main.py").read_text()
    assert "### dr-pack <folder>" in (REPO / "eaxcli/help.txt").read_text()
