"""eax site: the website inside EA Explorer (Release 7.1, D776, D777).

    eax site build                       the website made again from docs/site, docs/guides and releases
    eax site check                       the same in memory: what is wrong, nothing written
    eax site shots [--only P,P] [--missing]
                                         the How do I pages' pictures taken from this installation's own screens,
                                         then the website made again
    eax site pdfs [--only ID,ID]         the 24 printed guides (docs/manuals/manuals.json) as PDFs in documents/,
                                         with the pictures shots took (D783); then the website made again, with them

The pictures are taken in the test runner (Chromium is there), signed in as the first Super Admin; it opens pages, and the
tabs, links, cards and dialogs a page's do: line names, and never saves anything (D781). The PDFs are printed in the same
runner from the repository (tools/build_manuals.py). Neither is part of eax test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .core import EAX, ROOT, Failure, compose, say

USAGE = f"Usage: {EAX} site build|check|shots|pdfs [--only PAGE,PAGE] [--missing]"


def _builder():
    """tools/build_website.py, loaded as a module (Python's own library only)."""
    spec = importlib.util.spec_from_file_location("build_website", Path(ROOT) / "tools" / "build_website.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_website"] = mod   # a dataclass looks its module up here while it is made
    spec.loader.exec_module(mod)
    return mod


def remove_old_copies(root: Path) -> list[str]:
    """The How do I pages that became Guides (18 Nov 2026, D777): the old copy in docs/site/how-do-i is deleted when the
    Guide of the same name is there (the owner, 14:45: "delete old content"). Only those files; returns their names."""
    site = Path(root) / "docs" / "site"
    gone = []
    for guide in sorted((site / "guides").glob("*.md")):
        old = site / "how-do-i" / guide.name
        if old.is_file():
            old.unlink()
            gone.append(old.name)
    return gone


def shots_command(rest: list[str]) -> list[str]:
    """The compose arguments that take the pictures: the test runner with docs/site mounted, its own program."""
    site = (Path(ROOT) / "docs" / "site").resolve().as_posix()
    return ["--profile", "test", "run", "--rm", "--no-deps", "-v", f"{site}:/site-src", "--entrypoint", "python",
            "testrunner", "-m", "eax.testing.site_shots", *rest]


def pdfs_command(rest: list[str]) -> list[str]:
    """The compose arguments that print the guides: the test runner with the repository mounted at /repo, the PDFs
    written to documents/ (D783, D785)."""
    repo = Path(ROOT).resolve().as_posix()
    return ["--profile", "test", "run", "--rm", "--no-deps", "-v", f"{repo}:/repo", "--entrypoint", "python",
            "testrunner", "/repo/tools/build_manuals.py", "--out", "/repo/documents", *rest]


def main(rest: list[str]) -> int:
    """eax site build|check|shots|pdfs."""
    what = rest[0] if rest else ""
    if what not in ("build", "check", "shots", "pdfs"):
        raise Failure(USAGE)
    if what == "pdfs":
        bad = [a for a in rest[1:] if a.startswith("--") and a != "--only"]
        if bad:
            raise Failure(USAGE)
        compose(["--profile", "test", "build", "testrunner"])
        say("Printing the guides in the test runner (Chromium): a few minutes...")
        compose(pdfs_command(rest[1:]))
        say("The guides are in documents/ (EA-Explorer-<nn>-<name>.pdf). Making the website again, with them...")
        problems = _builder().build(write=True)
        for p in problems:
            say(f"  {p}", "red")
        return 1 if problems else 0
    if what != "check":
        gone = remove_old_copies(ROOT)
        if gone:
            say(f"Deleted {len(gone)} old How do I page(s) that are now Guides: {', '.join(gone)}")
    if what == "shots":
        bad = [a for a in rest[1:] if a.startswith("--") and a not in ("--only", "--missing", "--width", "--height")]
        if bad:
            raise Failure(USAGE)
        say("Building the website first (the list of screens), then the test runner if it changed...")
        _builder().build(write=True)
        compose(["--profile", "test", "build", "testrunner"])
        say("Taking the pictures as the first Super Admin: pages are only opened, nothing is changed.")
        compose(shots_command(rest[1:]))
    builder = _builder()
    problems = builder.build(write=what != "check")
    for p in problems:
        say(f"  {p}", "red")
    if problems:
        return 1
    say("The website: no problems." if what == "check" else
        "The website is made in services/web/public/site/<version> (open /site/ after eax up; copy the folder to publish it).")
    return 0
