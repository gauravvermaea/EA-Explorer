"""The restore drill kept simple (the owner, 18 Nov 2026, 07:12: "this will be used in critical failure so things need to
work"; "Key items, check is only a warning, unless the actual migration fails dont fail test. If we can login into the new
instance we are good").

The owner's drill of 07:04 failed: "Cannot find path ...\\work\\backups\\infrastructure\\20261118T050221Z-drill-krbadvsx":
the backup was not where the drill looked for it on the machine. The backup is now taken straight out of EA Explorer
while it runs; a real sign-in decides whether the DR copy works; the key items and the rest are warnings.
"""

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
from eaxcli import drill as D  # noqa: E402

DR = REPO / "dr"
NAME = "20261118T050221Z-drill-krbadvsx"
needs_bash = pytest.mark.skipif(not shutil.which("bash"), reason="bash is not here")


class P:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


# ---------------------------------------------------------------- the backup taken out of EA Explorer
def test_the_backup_is_taken_out_of_ea_explorer_when_it_is_not_in_the_folder_on_this_machine(monkeypatch, tmp_path):
    """The owner's drill, 18 Nov 2026, 07:04: the folder the drill looked in did not hold the backup."""
    monkeypatch.setattr(D, "info", lambda: {"backups": str(tmp_path / "work" / "backups" / "infrastructure")})
    monkeypatch.setattr(D, "compose_args", lambda a: ["docker", "compose", *a])
    seen = []

    def cp(args, **k):
        seen.append(args)
        dest = Path(args[-1])
        dest.mkdir(parents=True)
        (dest / "SHA256SUMS").write_text("x  db.dump\n")
        (dest / "db.dump").write_text("x")
        return P()
    out = D.take(NAME, str(tmp_path / "temp" / "backup" / NAME), run=cp)
    assert "error" not in out and out["files"] == 2 and "operations helper" in out["how"]
    assert seen[0][:3] == ["docker", "compose", "cp"] and seen[0][3] == f"ops:/backups/infrastructure/{NAME}"


def test_the_backup_is_copied_from_the_folder_on_this_machine_when_it_is_there(monkeypatch, tmp_path):
    src = tmp_path / "bk" / NAME
    src.mkdir(parents=True)
    (src / "SHA256SUMS").write_text("x  a\n")
    (src / "a").write_text("a")
    monkeypatch.setattr(D, "info", lambda: {"backups": str(tmp_path / "bk")})
    out = D.take(NAME, str(tmp_path / "t" / NAME), run=lambda *a, **k: pytest.fail("no docker needed"))
    assert out["files"] == 2 and (tmp_path / "t" / NAME / "a").exists()


def test_taking_a_backup_fails_in_words(monkeypatch, tmp_path):
    monkeypatch.setattr(D, "info", lambda: {"backups": str(tmp_path / "none")})
    monkeypatch.setattr(D, "compose_args", lambda a: a)
    assert "not a backup's name" in D.take("../etc", str(tmp_path / "x"))["error"]
    assert "could not be copied out" in D.take(NAME, str(tmp_path / "x"), run=lambda *a, **k: P(1, "", "no such container"))["error"]
    assert "no SHA256SUMS" in D.take(NAME, str(tmp_path / "y"),
                                     run=lambda a, **k: Path(a[-1]).mkdir(parents=True) or P())["error"]


# ---------------------------------------------------------------- a real sign-in
def test_signin_signs_in_to_keycloak_and_asks_the_api(monkeypatch):
    monkeypatch.setattr(D, "compose_args", lambda a: a)
    calls = []

    def run(args, **k):
        calls.append(args)
        return P(0, "12\n") if args[2] == "keycloak" else P(0, "200\n")
    out = D.signin(run=run)
    assert out == {"people": 12, "realm": "eaexplorer", "api": "answers"}
    assert "config credentials" in calls[0][5] and "/run/secrets/EAX_KC_ADMIN_PASSWORD" in calls[0][5]
    assert "users/count" in calls[0][5] and "/api/health" in calls[1][-1]


def test_signin_waits_while_the_copy_starts_then_fails_in_words(monkeypatch):
    monkeypatch.setattr(D, "compose_args", lambda a: a)
    tries = []

    def run(args, **k):
        tries.append(1)
        return P(1, "", "Connection refused") if args[2] == "keycloak" else P(0, "200")
    out = D.signin(minutes=0, run=run, sleep=lambda s: None)
    assert "nobody can sign in" in out["error"] and "Connection refused" in out["error"]
    answers = iter([P(1, "", "starting"), P(0, "200"), P(0, "3\n"), P(0, "200")])
    assert D.signin(minutes=1, run=lambda *a, **k: next(answers), sleep=lambda s: None)["people"] == 3


def test_signin_with_nobody_in_the_realm_is_a_warning_not_a_failure(monkeypatch):
    monkeypatch.setattr(D, "compose_args", lambda a: a)
    out = D.signin(run=lambda a, **k: P(0, "0\n") if a[2] == "keycloak" else P(0, "200"))
    assert "error" not in out and "no people" in out["warnings"][0]


# ---------------------------------------------------------------- the key items: warnings only
def test_key_items_lost_are_warnings_never_a_failure(tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"tables": {"eaexplorer core.models": [5, "x"], "eaexplorer core.entities": [100, "y"]}, "files": {}}))
    b.write_text(json.dumps({"tables": {"eaexplorer core.models": [4, "x"], "eaexplorer core.entities": [100, "y"]}, "files": {}}))
    assert D.main(["compare", str(a), str(b)]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    assert "error" not in out and "models: 5 before, 4 after" in out["warnings"]


# ---------------------------------------------------------------- the scripts
def test_only_the_restore_and_the_sign_in_fail_the_drill():
    ps, sh = (DR / "eax-drill.ps1").read_text(), (DR / "eax-drill.sh").read_text()
    for t in (ps, sh):
        assert "drill content" not in t.replace('"drill", "content', "drill content")     # no test content made
    # the two steps of going back (R9.10) come only with --then-back, after the drill itself
    back = ("the DR copy stopped (kept)", "the installation started again and a real sign-in")
    hard_ps = [line.split('"')[1] for line in ps.splitlines() if line.strip().startswith("Step \"")
               and line.split('"')[1] not in back]
    hard_sh = [line.split('"')[1] for line in sh.splitlines() if line.startswith("step \"")]
    assert all(f'step "{b}"' in sh and f'Step "{b}"' in ps for b in back)
    for hard in (hard_ps, hard_sh):
        assert [h.split(":")[0].split(" (")[0] for h in hard] == [
            "checks", "an earlier drill's DR copy and leftovers removed and the folders made",
            "the installation running", "a full infrastructure backup",
            "the backup, the env file and the code copied out into the temp folder and checked",
            "the installation shut down", "eax-dr", "a real sign-in to the DR copy"], hard
    for f in ("eax-dr.ps1", "eax-dr.sh"):
        t = (DR / f).read_text()
        assert "a real sign-in" in t and "drill" in t and "signin" in t
        for soft in ("the maintenance page on and the background paused", "the rest up", "the smoke test"):
            line = next(x for x in t.splitlines() if soft in x and ("Step" in x or "step" in x))
            assert "SoftStep" in line or "soft_step" in line, line
    assert "function SoftStep" in (DR / "dr-common.ps1").read_text() and "soft_step()" in (DR / "dr-common.sh").read_text()


@needs_bash
def test_a_warning_step_failing_never_fails_the_drill(tmp_path):
    """The key items could not be counted (a fingerprint that fails): the drill still passes, with a warning."""
    from test_r5_6_dr import _backup, _code_source, _offline
    inst = _code_source(tmp_path)
    eax = (inst / "eax.sh").read_text().replace("  'drill compare '*)",
                                                "  'drill fingerprint '*) echo '{\"error\": \"a table could not be read\"}'; exit 1;;\n  'drill compare '*)")
    (inst / "eax.sh").write_text(eax)
    (inst / "work").mkdir()
    (inst / "work" / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\n")
    shutil.copytree(_backup(tmp_path), inst / "bk" / "20261116T010000Z-nightly")
    r = subprocess.run(["bash", str(DR / "eax-drill.sh"), "--install", str(inst), "--dr", str(tmp_path / "dr1"), "--temp",
                        str(tmp_path / "temp")], env={**_offline(tmp_path), **{k: v for k, v in os.environ.items() if k == "HOME"}},
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "PASSED with" in r.stdout and "a table could not be read" in r.stdout
