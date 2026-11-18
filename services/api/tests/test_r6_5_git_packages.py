"""Git as one more place for model and project packages (Release 6.5, D753; owner, 17 Nov 2026, 20:51: "github being
just one more item ... zip is already there"; 21:54: "for R6x we needed git based import and export of model and
project where is that?"). The git library is stood in for: pushing, listing and fetching, the token never kept."""

from __future__ import annotations

from pathlib import Path

import pytest

from eax import gitpackages as gp
from eax.metamodel_edit import EditError

REPO = Path(__file__).resolve().parents[3]


class FakeGit:
    """A stand-in for dulwich.porcelain over one 'remote' folder."""
    def __init__(self, remote: Path):
        self.remote, self.pushed, self.creds = remote, [], []

    def clone(self, url, target, username=None, password=None, branch=None, depth=None, errstream=None):
        import shutil
        self.creds.append((username, password))
        if "missing" in url:
            raise RuntimeError(f"https://{username}:{password}@git.example/x not found")
        shutil.copytree(self.remote, target, dirs_exist_ok=True)
        return target

    def add(self, repo, paths):
        self.added = paths

    def commit(self, repo, message=None, author=None, committer=None):
        self.message = message

    def push(self, repo, url, ref, username=None, password=None, errstream=None):
        import shutil
        shutil.copytree(Path(repo) / gp.FOLDER, self.remote / gp.FOLDER, dirs_exist_ok=True)
        self.pushed.append(ref)


def test_a_package_goes_to_git_and_comes_back(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    g = FakeGit(remote)
    out = gp.push(b"PK-model", "Insurance.zip", "https://git.example/ea/packages.git", "main", "ann", "t0ken", "ann", porcelain=g)
    assert out == {"pushed": "eax-packages/Insurance.zip", "repository": "https://git.example/ea/packages.git", "branch": "main"}
    assert g.pushed == [b"main"] and b"Insurance.zip" in g.message
    gp.push(b"PK-project", "Claims.eaxproject.zip", "https://git.example/ea/packages.git", "main", "", "", "ann", porcelain=g)
    assert gp.listing("https://git.example/ea/packages.git", "main", "", "", ".eaxproject.zip", porcelain=g) == ["Claims.eaxproject.zip"]
    assert gp.fetch("https://git.example/ea/packages.git", "main", "", "", "Insurance.zip", porcelain=g) == b"PK-model"


def test_refusals_say_why_and_never_show_the_token(tmp_path):
    g = FakeGit(tmp_path)
    with pytest.raises(EditError) as exc:
        gp.listing("https://git.example/missing.git", "main", "ann", "s3cret", porcelain=g)
    assert "s3cret" not in str(exc.value) and exc.value.status == 502
    for bad in ("http://git.example/x.git", "git@git.example:x.git", ""):
        with pytest.raises(EditError):
            gp.listing(bad, "main", "", "", porcelain=g)
    with pytest.raises(EditError):
        gp.fetch("https://git.example/ea/x.git", "main", "", "", "../etc/passwd.zip", porcelain=g)


def test_the_screens_offer_git_beside_download_and_upload():
    web = REPO / "services/web/src"
    ops = (web / "ModelOps.jsx").read_text()
    assert 'gitPush(git, { source: "model", model: m.id, format, content })' in ops          # a model's Download
    assert "<GitPicker onFile={(f) => analyse(f)} />" in ops                                  # a model's Upload
    tabs = (web / "ProjectTabs.jsx").read_text()
    assert 'source: "project-backup", project: p.id, file: gitFile' in tabs                    # a project's backup
    assert '<GitPicker suffix=".eaxproject.zip" onFile={(f) => setFile(f)} />' in tabs        # a project's restore
    assert 'source: "project-backup"' in (web / "Backups.jsx").read_text()
    assert "never kept" in (web / "GitPlace.jsx").read_text()
