"""The build number goes up by one with every commit (owner, 23 Nov 2026: "Also build number shown on the page makes no
sense can we have incremental numbers?", then "show count of commits, increment the build number each time"; D882).

It is the count of commits on the checked-out branch, one more when files differ from the last commit (the build the
next commit makes), "dev" outside git, and whatever CI sets in EAX_BUILD. The same in eaxcli, eax.sh and eax.ps1
(D331). The commit's id stays beside it (EAX_COMMIT, in the version tag's tooltip).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from eaxcli import core  # noqa: E402

PS1 = (ROOT / "eax.ps1").read_text(encoding="utf-8")
SH = (ROOT / "eax.sh").read_text(encoding="utf-8")


def _with(monkeypatch, count: str, changed: str, code: int = 0):
    def capture(cmd, *a, **k):
        if cmd[:3] == ["git", "rev-list", "--count"]:
            return code, count
        if cmd[:2] == ["git", "status"]:
            return 0, changed
        raise AssertionError(cmd)
    monkeypatch.setattr(core, "capture", capture)
    monkeypatch.delenv("EAX_BUILD", raising=False)


def test_the_number_is_the_count_of_commits(monkeypatch):
    _with(monkeypatch, "1234\n", "")
    assert core.build_id() == "1234"


def test_one_more_when_files_differ_from_the_last_commit(monkeypatch):
    _with(monkeypatch, "1234\n", " M services/api/eax/agile.py\n")
    assert core.build_id() == "1235"


def test_dev_outside_git_and_ci_wins(monkeypatch):
    _with(monkeypatch, "", "", code=128)
    assert core.build_id() == "dev"
    _with(monkeypatch, "fatal: not a git repository", "")
    assert core.build_id() == "dev"
    monkeypatch.setenv("EAX_BUILD", "ci-77")
    assert core.build_id() == "ci-77"


def test_no_commit_id_and_no_changed_suffix_any_more():
    src = Path(core.__file__).read_text(encoding="utf-8")
    fn = src[src.index("def build_id"):src.index("def release")]
    assert '"rev-parse", "--short"' not in fn and "-changed" not in fn
    sh = SH[SH.index("build_id() {"):SH.index("release() {")]
    assert "rev-list --count HEAD" in sh and "-changed" not in sh and "n=$((n + 1))" in sh
    ps = PS1[PS1.index("function Get-BuildId"):PS1.index("function Get-Release")]
    assert '"rev-list", "--count", "HEAD"' in ps and "-changed" not in ps and "$n = $n + 1" in ps
    assert all(ord(c) < 128 for c in PS1)                     # eax.ps1 stays ASCII


@pytest.mark.skipif(not shutil.which("git") or not shutil.which("bash"), reason="needs git and bash")
def test_eax_sh_counts_in_a_real_repository(tmp_path):
    fn = SH[SH.index("build_id() {"):SH.index("release() {")]
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    env.pop("EAX_BUILD", None)

    def run(script):
        return subprocess.run(["bash", "-c", fn + "\n" + script], cwd=tmp_path, env=env, capture_output=True, text=True).stdout.strip()

    assert run("build_id") == "dev"                            # not a repository yet
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, env=env)
    for i in (1, 2, 3):
        (tmp_path / "f.txt").write_text(str(i))
        subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", f"c{i}"], cwd=tmp_path, check=True, env=env)
        assert run("build_id") == str(i)                       # up by one with every commit
    (tmp_path / "f.txt").write_text("changed")
    assert run("build_id") == "4"                              # files differ: the next build
    assert re.fullmatch(r"ci-1", run("EAX_BUILD=ci-1 build_id"))
