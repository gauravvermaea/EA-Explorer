"""Every SQL migration runs (18 Nov 2026, closing Release 6): migrations/sql/NNNN_x.sql is run by
migrations/versions/NNNN_x.py, and the wrappers make one unbroken chain. 0106 (the settings' safety copies, R6.7) was
written without its wrapper, so the table would never have been made."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

API = Path(__file__).resolve().parents[1]
SQL = API / "migrations" / "sql"
VERSIONS = API / "migrations" / "versions"


def _wrappers() -> dict[str, tuple[str, str | None]]:
    out = {}
    for p in VERSIONS.glob("*.py"):
        t = p.read_text(encoding="utf-8")
        rev = re.search(r'^revision = "([^"]+)"', t, re.M)
        down = re.search(r'^down_revision = (?:"([^"]+)"|None)', t, re.M)
        if rev:
            out[rev.group(1)] = (p.stem, down.group(1) if down else None)
    return out


def test_every_sql_migration_is_run_by_a_wrapper():
    run = " ".join(p.read_text(encoding="utf-8") for p in VERSIONS.glob("*.py"))
    for sql in SQL.glob("*.sql"):
        if re.match(r"^\d{4}_", sql.stem):
            assert sql.name in run, f"{sql.name} is run by no migrations/versions/*.py: it would never run"


def test_the_wrappers_make_one_unbroken_chain():
    wrappers = _wrappers()
    downs = [d for _f, d in wrappers.values()]
    heads = [r for r in wrappers if r not in downs]
    assert len(heads) == 1, f"more than one newest migration: {heads}"
    assert len([d for d in downs if d is None]) == 1
    assert len(set(d for d in downs if d)) == len([d for d in downs if d]), "two migrations follow the same one"
    for rev, (_f, down) in wrappers.items():
        assert down is None or down in wrappers, f"{rev} follows {down}, which is not there"


def test_the_newest_release_migration_records_the_version_the_api_reports():
    version = tomllib.loads((API / "version.toml").read_text(encoding="utf-8"))["version"]
    tag = "release_" + version.replace(".", "_")
    found = [p for p in SQL.glob(f"*_{tag}.sql")]
    assert found and f"'{version}'" in found[0].read_text(encoding="utf-8"), version
    assert (API.parents[1] / "releases" / f"{version}.md").exists(), f"releases/{version}.md"
