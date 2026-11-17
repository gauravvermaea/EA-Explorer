"""A git repository as one more place for packages (Release 6.5, content promotion; owner, 17 Nov 2026, 20:51: "The
promotion thing can be part of the screen where we export import and github being just one more item. I dont think
there is any need to do more. zip is already there").

A model's package (Download: zip or Excel) and a project's backup file (Back up) go to a git repository on any git
server over HTTPS (one commit, pushed), and are taken from one (listed, then fetched into the same Upload as a file from
this computer). The files are put under eax-packages/ in the repository. The repository's address and branch are typed
each time (the screens remember them in the browser); the user name and token are used for that one call and never kept.

Pure Python git (dulwich): no git program in the image and nothing specific to one git server (D746).
"""

from __future__ import annotations

import io
import re
import shutil
import tempfile
from pathlib import Path

from .metamodel_edit import EditError

FOLDER = "eax-packages"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,200}\.(zip|xlsx)$")


def _check(repo_url: str, file: str | None = None) -> None:
    if not re.match(r"^https://[^\s/]+/\S+$", repo_url or ""):
        raise EditError("The git repository's address is its HTTPS address, for example https://git.example.org/ea/packages.git.")
    if file is not None and (not _NAME.match(file) or "/" in file or ".." in file):
        raise EditError("Not a package's file name.")


def _clone(repo_url: str, branch: str, username: str, token: str, porcelain) -> tuple[object, Path]:
    work = Path(tempfile.mkdtemp(prefix="eax-git-"))
    try:
        repo = porcelain.clone(repo_url, str(work), username=username or None, password=token or None,
                               branch=(branch or None) and branch.encode(), depth=1, errstream=io.BytesIO())
    except Exception as exc:  # noqa: BLE001 - refused, not found, no such branch
        shutil.rmtree(work, ignore_errors=True)
        raise EditError(f"The git repository could not be read: {_plain(exc)}", 502) from exc
    return repo, work


def _plain(exc: Exception) -> str:
    """The git library's words, with any token taken out."""
    return re.sub(r"https://[^@\s]+@", "https://", str(exc))[:200] or exc.__class__.__name__


def push(data: bytes, file: str, repo_url: str, branch: str, username: str, token: str, by: str, porcelain=None) -> dict:
    """The file put under eax-packages/ in the repository: one commit, pushed. The token is never kept."""
    if porcelain is None:
        from dulwich import porcelain
    _check(repo_url, file)
    repo, work = _clone(repo_url, branch, username, token, porcelain)
    try:
        (work / FOLDER).mkdir(exist_ok=True)
        (work / FOLDER / file).write_bytes(data)
        porcelain.add(repo, [str(work / FOLDER / file)])
        who = f"{by} <{re.sub(r'[^A-Za-z0-9._-]', '', by) or 'eax'}@ea-explorer>".encode()
        porcelain.commit(repo, message=f"EA Explorer: {file}, by {by}".encode(), author=who, committer=who)
        try:
            porcelain.push(repo, repo_url, (branch or "main").encode(), username=username or None, password=token or None,
                           errstream=io.BytesIO())
        except Exception as exc:  # noqa: BLE001
            raise EditError(f"The git server refused the push: {_plain(exc)}", 502) from exc
        return {"pushed": f"{FOLDER}/{file}", "repository": repo_url, "branch": branch or "main"}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def listing(repo_url: str, branch: str, username: str, token: str, suffix: str = "", porcelain=None) -> list[str]:
    """The packages in the repository's eax-packages/ (newest name first), those ending in suffix."""
    if porcelain is None:
        from dulwich import porcelain
    _check(repo_url)
    _repo, work = _clone(repo_url, branch, username, token, porcelain)
    try:
        return sorted((p.name for p in (work / FOLDER).glob("*") if p.is_file() and p.name.endswith(suffix)
                       and _NAME.match(p.name)), reverse=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def fetch(repo_url: str, branch: str, username: str, token: str, file: str, porcelain=None) -> bytes:
    """One package's bytes from the repository (the screen then uploads it as if chosen on this computer)."""
    if porcelain is None:
        from dulwich import porcelain
    _check(repo_url, file)
    _repo, work = _clone(repo_url, branch, username, token, porcelain)
    try:
        path = work / FOLDER / file
        if not path.is_file():
            raise EditError(f"There is no {file} in {FOLDER}/ on that branch.", 404)
        return path.read_bytes()
    finally:
        shutil.rmtree(work, ignore_errors=True)
