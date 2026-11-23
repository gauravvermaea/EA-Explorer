"""The seed runs as eax_migrator, which may not make temporary tables: the database takes every right from PUBLIC and
gives eax_migrator CONNECT only (deploy/postgres/initdb/01-databases.sh, deploy/external-db/prepare.sql). The Release
12 model upgrade (D887) made one, and on 23 Nov 2026 the API would not start: "permission denied to create temporary
tables in database eaexplorer", over and over. Each step of the upgrade now works out the types itself."""

from __future__ import annotations

import re
from pathlib import Path

from eax.seed import build

API = Path(__file__).resolve().parents[1]
TEMP = re.compile(r"\b(CREATE\s+(GLOBAL\s+|LOCAL\s+)?(TEMP|TEMPORARY)\s+TABLE|pg_temp)\b", re.IGNORECASE)


def test_the_model_upgrade_makes_no_temporary_table():
    sql = build.model_upgrade_sql()
    assert not TEMP.search(sql)
    assert not TEMP.search(build.root_upgrade_sql())
    steps = [s for s in sql.split(";\n") if "r12_types" in s]
    assert len(steps) == 6
    code = ["\n".join(x for x in s.splitlines() if x.strip() and not x.lstrip().startswith("--")) for s in steps]
    assert all(c.startswith("WITH r12_types AS (") for c in code)       # each step lists the types itself


def test_nothing_the_seed_runs_makes_a_temporary_table():
    files = [*sorted((API / "eax" / "seed").glob("*.py")), API / "eax" / "project_library.py",
             API / "eax" / "project_bases.py"]
    for f in files:
        if f.exists():
            assert not TEMP.search(f.read_text(encoding="utf-8")), f


def test_eax_migrator_is_still_given_connect_only():
    """If eax_migrator is ever given TEMPORARY, this test is the place to say so (and the two tests above can go)."""
    for f in (API.parents[1] / "deploy" / "postgres" / "initdb" / "01-databases.sh",
              API.parents[1] / "deploy" / "external-db" / "prepare.sql"):
        text = f.read_text(encoding="utf-8")
        assert re.search(r"REVOKE ALL ON DATABASE .* FROM PUBLIC", text), f
        assert not re.search(r"GRANT\s+(TEMP|TEMPORARY|ALL)[^;]*eax_migrator", text, re.IGNORECASE), f
