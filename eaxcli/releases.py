"""Releases of EA Explorer: its GitHub Releases, its code from its git repository (phase 36, D417, D498; R5.6-U1, U2).
Standard library and the git command only.

Shared by the updater (eaxcli/updater.py, `eax update`), the operations helper's listing of versions and `eax deploy`
(phase 36, D498): one place that knows the channels, how versions are named and compared, which versions a channel
offers, the release notes, and how to fetch one version's files.

Where versions come from (owner, 16 Nov 2026, 15:21: "Release should not be picked from the main branch, instead pick
them from here - https://github.com/gauravvermaea/EA-Explorer/releases only upgrade forward"; 15:47: public; 16:20:
"EA-Explorer for both"): the repository's **published GitHub Releases** only (read without a sign-in), never `main`:
  prod    the published releases that are not pre-releases (tags vX.Y.Z)          on always
  rc      the pre-releases too (tags vX.Y.Z or vX.Y.Z-rc.N)                     off until a Super Admin or IT Admin enables it
A draft is never offered; a tag with no published release is not offered. The code an update installs is that
release's tag, fetched from the same repository.

Release notes (D510): a release's text on GitHub; when it is empty, `releases/<version>.md` in the repository at its tag.
When GitHub cannot be reached or refuses (its limit on calls without a sign-in), this says so in words and offers
nothing rather than guessing.

Forward only: a channel never offers a version lower than (or equal to) the installed one. Several releases behind (D417): the update goes one release after another, in order.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

CHANNELS = {
    "prod": {"label": "Prod", "branch": "GitHub Releases", "default": True,
             "about": "The published releases of the repository's GitHub Releases page. Recommended."},
    "rc": {"label": "RC", "branch": "GitHub pre-releases", "default": False,
           "about": "The published pre-releases as well: try a version before it is released."},
}
GITHUB_API = os.environ.get("EAX_GITHUB_API", "") or "https://api.github.com"   # another address only for a mirror
DEFAULT_REPO = "https://github.com/gauravvermaea/EA-Explorer"
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$")
NOTES_DIR = "releases"


class ReleaseError(RuntimeError):
    """Something about the repository or a version that the person must hear in plain words."""


# ---------------------------------------------------------------- versions
def parse(version: str) -> tuple[int, int, int, int, int] | None:
    """'0.19.0' or 'v0.19.0-rc.2' -> a key that sorts versions: a release sorts after its RCs. None if not a version."""
    m = TAG.match(version if version.startswith("v") else f"v{version}")
    if not m:
        return None
    major, minor, patch, rc = m.groups()
    return (int(major), int(minor), int(patch), 0 if rc else 1, int(rc or 0))


def base(version: str) -> str:
    """'0.19.0-rc.2' -> '0.19.0'."""
    return version.lstrip("v").split("-")[0]


def is_rc(version: str) -> bool:
    """Whether a version is a release candidate."""
    return "-rc." in version


def newer(a: str, b: str) -> bool:
    """Is version a newer than version b? (unknown versions are never newer)"""
    ka, kb = parse(a), parse(b)
    return bool(ka and kb and ka > kb)


def name_of(tag: str) -> str:
    """A version from its tag."""
    return tag.lstrip("v")


@dataclass
class Version:
    """One version a channel offers."""
    channel: str
    version: str             # 0.19.0, 0.19.0-rc.2
    ref: str                 # its tag (v0.19.0)
    commit: str = ""
    date: str = ""
    title: str = ""          # the release's title on GitHub
    notes: str = ""
    steps: list[str] = field(default_factory=list)   # filled by plan(): the versions gone through, in order

    def as_dict(self) -> dict:
        """The version as a dict."""
        return asdict(self)


# ---------------------------------------------------------------- git
def git(*args: str, cwd: str | os.PathLike | None = None, timeout: int = 300, check: bool = True) -> str:
    """Runs git (never asking for a password)."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="echo")
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    except FileNotFoundError as exc:
        raise ReleaseError("git is not installed here.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ReleaseError(f"git {args[0]} took longer than {timeout} s.") from exc
    if check and r.returncode:
        msg = (r.stderr or r.stdout).strip().splitlines()
        raise ReleaseError(f"git {args[0]} failed: {msg[-1] if msg else r.returncode}")
    return r.stdout


def check_url(url: str) -> str:
    """The repository link as given, checked a little (https, http, ssh, git, or a local path for tests)."""
    url = (url or "").strip()
    if not url:
        raise ReleaseError("No repository link is set: System admin > Updates (or EAX_UPDATE_GIT_URL in the config file).")
    if not re.match(r"^(https?://|ssh://|git@|git://|file://|/)", url) and not Path(url).exists():
        raise ReleaseError(f"{url} does not look like a git repository link (https://...).")
    return url


def remote_refs(url: str) -> dict[str, str]:
    """Every tag and branch head of the repository: {'refs/tags/v0.19.0': commit, 'refs/heads/main': commit}."""
    out = git("ls-remote", "--tags", "--heads", check_url(url), timeout=60)
    refs: dict[str, str] = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.endswith("^{}"):          # an annotated tag: the commit it points at
            refs[ref[:-3]] = sha
        else:
            refs.setdefault(ref, sha)
    return refs


def tags(url: str) -> dict[str, str]:
    """The version tags: {'v0.19.0': commit, 'v0.19.0-rc.1': commit}."""
    return {r[len("refs/tags/"):]: s for r, s in remote_refs(url).items()
            if r.startswith("refs/tags/") and TAG.match(r[len("refs/tags/"):])}


def cache_repo(folder: str | os.PathLike) -> Path:
    """A bare repository kept to read notes and commits without touching the installation (work/updates/cache.git)."""
    p = Path(folder)
    if not (p / "HEAD").exists():
        p.mkdir(parents=True, exist_ok=True)
        git("init", "--bare", "--quiet", str(p))
    return p


def fetch(cache: str | os.PathLike, url: str, ref: str, depth: int = 1) -> str:
    """Fetches one tag or branch into the cache repository; its commit."""
    spec = f"+refs/tags/{ref}:refs/tags/{ref}" if TAG.match(ref) else f"+refs/heads/{ref}:refs/remotes/origin/{ref}"
    git("fetch", "--quiet", "--no-tags", *(["--depth", str(depth)] if depth else []), check_url(url), spec, cwd=cache)
    local = f"refs/tags/{ref}" if TAG.match(ref) else f"refs/remotes/origin/{ref}"
    return git("rev-parse", f"{local}^{{commit}}", cwd=cache).strip()


def show(cache: str | os.PathLike, commit: str, path: str) -> str | None:
    """A file as it is at a commit (None when it is not there)."""
    r = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=cache, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def version_at(cache: str | os.PathLike, commit: str) -> str:
    """The version (services/api/version.toml) at a commit."""
    text = show(cache, commit, "services/api/version.toml") or ""
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return m.group(1) if m else ""


def notes_for(cache: str | os.PathLike, commit: str, version: str) -> str:
    """The release notes file at that commit: releases/<version>.md, or for an RC its release's file."""
    for v in (version, base(version)):
        text = show(cache, commit, f"{NOTES_DIR}/{v}.md")
        if text:
            return text.strip()
    return ""


# ---------------------------------------------------------------- GitHub Releases (R5.6-U1)
def github_repo(url: str) -> tuple[str, str]:
    """(owner, name) of a github.com repository link; anything else is refused in words."""
    m = re.match(r"^(?:https?://|git@)github\.com[/:]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", (url or "").strip())
    if not m:
        raise ReleaseError(f"{url or 'No repository link'}: updates read the repository's GitHub Releases, so the link "
                           f"must be a github.com repository (for example {DEFAULT_REPO}).")
    return m.group(1), m.group(2)


def _get_json(url: str, timeout: int = 20):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "EA-Explorer-updates",
                                               "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310 - GitHub's API, https
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            reset = exc.headers.get("X-RateLimit-Reset", "")
            raise ReleaseError("GitHub refused: its limit on calls without a sign-in is reached"
                               + (f" until {time.strftime('%H:%M UTC', time.gmtime(int(reset)))}" if reset.isdigit() else "")
                               + ". Nothing is offered until then.") from exc
        if exc.code == 404:
            raise ReleaseError("GitHub has no such repository (or it is private): check the repository link.") from exc
        raise ReleaseError(f"GitHub answered {exc.code}: nothing is offered.") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ReleaseError(f"GitHub cannot be reached ({exc}): nothing is offered.") from exc


def github_releases(url: str, fetcher=None) -> list[dict]:
    """The repository's published releases, newest first: {tag, version, title, notes, date, prerelease}. Drafts and
    tags that are not versions are left out."""
    owner, name = github_repo(url)
    get = fetcher or _get_json
    out: list[dict] = []
    for page in range(1, 6):
        rows = get(f"{GITHUB_API}/repos/{owner}/{name}/releases?per_page=100&page={page}")
        if not isinstance(rows, list):
            raise ReleaseError("GitHub's answer about the releases was not understood: nothing is offered.")
        for r in rows:
            tag = str(r.get("tag_name") or "")
            if r.get("draft") or not TAG.match(tag):
                continue
            out.append({"tag": tag, "version": name_of(tag), "title": str(r.get("name") or tag),
                        "notes": str(r.get("body") or "").strip(), "date": str(r.get("published_at") or ""),
                        "prerelease": bool(r.get("prerelease"))})
        if len(rows) < 100:
            break
    out.sort(key=lambda x: parse(x["version"]), reverse=True)
    return out


def offered_releases(url: str, channel: str, fetcher=None) -> list[dict]:
    """A channel's releases, newest first (for the drop-downs): prod without the pre-releases, rc with them."""
    if channel not in CHANNELS:
        raise ReleaseError("Versions come only from the published GitHub Releases: channel prod, or rc when it is on "
                           "(never the main branch).")
    rel = github_releases(url, fetcher)
    return [r for r in rel if channel == "rc" or (not r["prerelease"] and not is_rc(r["version"]))]


# ---------------------------------------------------------------- what a channel offers
def available(url: str, channel: str, installed: dict, cache: str | os.PathLike, with_notes: bool = True) -> list[Version]:
    """The versions the channel offers above the installed one, oldest first (forward only, D417).
    installed: {'version': '0.18.0', 'commit': '...'}."""
    have = installed.get("version") or "0.0.0"
    rel = [r for r in offered_releases(url, channel) if newer(r["version"], have)]      # forward only
    if not rel:
        return []
    shas = tags(url)
    out = [Version(channel=channel, version=r["version"], ref=r["tag"], commit=shas.get(r["tag"], ""), date=r["date"],
                   title=r["title"], notes=r["notes"]) for r in rel]
    out.sort(key=lambda x: parse(x.version))
    if with_notes:
        cache = cache_repo(cache)
        for x in out:
            if x.notes:
                continue                     # GitHub's own text; the file at the tag only when it is empty
            try:
                fetch(cache, url, x.ref)
                x.notes = notes_for(cache, x.commit, x.version)
            except ReleaseError:
                pass
    return out


def plan(offered: list[Version], target: str = "") -> Version:
    """The version to move to and the versions gone through on the way (D417: one release at a time).
    target: a version (0.19.0, 0.19.0-rc.2) or its tag; empty: the newest offered."""
    if not offered:
        raise ReleaseError("Nothing newer on this channel: the installed version is the newest.")
    if target:
        pick = next((x for x in offered if x.version == target.lstrip("v") or x.ref == target), None)
        if not pick:
            raise ReleaseError(f"{target} is not offered: it is not on this channel, or not newer than the installed "
                               "version (updates only go forward).")
    else:
        pick = offered[-1]
    upto = [x for x in offered if parse(x.version) <= parse(pick.version)]
    by_release: dict[str, Version] = {}
    for x in upto:                       # each release once: its final version if offered, else its newest RC
        b = base(x.version)
        if b not in by_release or parse(x.version) > parse(by_release[b].version):
            by_release[b] = x
    by_release[base(pick.version)] = pick
    pick.steps = [by_release[b].ref for b in sorted(by_release, key=lambda v: parse(v))]
    return pick


# ---------------------------------------------------------------- a version's files (eax deploy, non-git installs)
def export(url: str, ref: str, dest: str | os.PathLike, cache: str | os.PathLike | None = None) -> str:
    """Writes the files of one version (a tag, branch or commit) into dest, without git history; its commit.
    Used by `eax deploy` (D498) and by updates of an installation that is not a git checkout."""
    tmp = None
    if cache is None:
        tmp = tempfile.mkdtemp(prefix="eax-release-")
        cache = Path(tmp) / "cache.git"
    try:
        c = cache_repo(cache)
        try:
            sha = fetch(c, url, ref)
        except ReleaseError:
            git("fetch", "--quiet", "--depth", "1", check_url(url), ref, cwd=c)   # a commit id
            sha = git("rev-parse", "FETCH_HEAD", cwd=c).strip()
        Path(dest).mkdir(parents=True, exist_ok=True)
        archive = Path(tempfile.mkdtemp(prefix="eax-archive-")) / "v.tar"
        git("archive", "--format=tar", "-o", str(archive), sha, cwd=c)
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")
        shutil.rmtree(archive.parent, ignore_errors=True)
        return sha
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- supported versions (8.5, D514)
def supported(installed: str, releases: list[str]) -> tuple[bool, str]:
    """The supported-versions policy (docs/release-process.md): the newest release line (X.Y) and the one before are
    supported; a release candidate only until its release is out."""
    finals = sorted({base(r) for r in releases if not is_rc(r) and parse(r)}, key=parse)
    if not finals or not parse(installed):
        return True, ""
    lines = []
    for f in reversed(finals):
        line = ".".join(f.split(".")[:2])
        if line not in lines:
            lines.append(line)
    keep = lines[:2]
    mine = ".".join(base(installed).split(".")[:2])
    if is_rc(installed) and base(installed) in finals:
        return False, f"{installed} is a release candidate of {base(installed)}, which is now released: update to it."
    if mine in keep or newer(installed, finals[-1]):
        return True, ""
    return False, (f"{installed} is no longer supported: the supported release lines are {', '.join(keep)}. "
                   f"Update to {finals[-1]}.")


def main(argv: list[str]) -> int:
    """python3 releases.py list <url> <channel> <installed-version> [<installed-commit>] [--cache <folder>]
       python3 releases.py published <url> <channel>
    Prints the versions offered (or every published release) as JSON (used by the operations helper, which has no internet itself)."""
    if len(argv) >= 3 and argv[0] == "published":      # python3 releases.py published <url> <channel>
        try:
            print(json.dumps({"releases": offered_releases(argv[1], argv[2])}))
            return 0
        except ReleaseError as exc:
            print(json.dumps({"error": str(exc)}))
            return 1
    if len(argv) >= 4 and argv[0] == "list":
        cache = argv[argv.index("--cache") + 1] if "--cache" in argv else tempfile.mkdtemp(prefix="eax-cache-")
        rest = [a for i, a in enumerate(argv) if a != "--cache" and (i == 0 or argv[i - 1] != "--cache")]
        installed = {"version": rest[3], "commit": rest[4] if len(rest) > 4 else ""}
        try:
            got = available(rest[1], rest[2], installed, cache)
            print(json.dumps({"versions": [v.as_dict() for v in got]}))
            return 0
        except ReleaseError as exc:
            print(json.dumps({"error": str(exc)}))
            return 1
    print(main.__doc__)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
