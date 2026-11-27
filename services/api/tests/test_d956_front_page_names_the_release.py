"""The GitHub home page names the release (D956). Release 14.5.0 was accepted and tagged on 27 Nov 2026 while
README.md still said "Status: version 14.0.0" and listed 14.5 as planned (owner, 15:08: "github home page says
nothing about Release 14.5 Please ensure all this is fixed"). The version in services/api/version.toml must now be
named by README.md's status line and releases table and by docs/capabilities.md's title; tools/release.py check
(run by CI on the tag) says the same."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
VERSION = tomllib.loads((API / "version.toml").read_text(encoding="utf-8"))["version"]


def _release():
    spec = importlib.util.spec_from_file_location("eax_release_tool", ROOT / "tools" / "release.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_readme_status_line_names_the_version():
    assert f"**Status: version {VERSION}," in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_readme_releases_table_links_the_notes():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    row = [line for line in readme.splitlines() if f"[{VERSION}](releases/{VERSION}.md)" in line]
    assert row, f"no row in README.md's releases table links releases/{VERSION}.md"
    assert "planned" not in row[0].rsplit("|", 2)[-2], "the released version's row still says planned"


def test_capabilities_names_the_version():
    first = (ROOT / "docs" / "capabilities.md").read_text(encoding="utf-8").splitlines()[0]
    assert f"(version {VERSION})" in first


def test_the_release_check_finds_a_stale_front_page():
    rel = _release()
    assert rel.front_page(VERSION) == []
    assert len(rel.front_page("99.0.0")) == 3
