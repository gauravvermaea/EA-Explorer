"""Release 14.6: ArchiMate's layer is domain inside too (D959; owner, 26 Nov 2026, 17:54: "Add a next minor release to
move layer to domain"; D941). Migration 0126 renames core.layers and library_models.layers to domains, layer_id to
domain_id and the analyses' layer columns to domain, and writes again the four functions that named them; the code reads
the new names; what was made before still works: history keeps its rows (the change log reads 'layers' as Domain), the
seed's ids still derive from "layer" (a new key would give every domain a new id), and a library_models database of its
own is renamed in place before it is brought in line."""

from __future__ import annotations

import re
from pathlib import Path

API = Path(__file__).resolve().parents[1]
SQL = API / "migrations" / "sql"
MIG = (SQL / "0126_r14_6_layer_to_domain.sql").read_text(encoding="utf-8")
OLD = re.compile(r"core\.layers\b|library_models\.layers\b|\blayer_id\b")


def test_0126_follows_0125_and_renames_every_name():
    wrapper = (API / "migrations" / "versions" / "0126_r14_6_layer_to_domain.py").read_text(encoding="utf-8")
    assert 'revision = "0126_r14_6_layer_to_domain"' in wrapper and 'down_revision = "0125_release_14_5_0"' in wrapper
    for line in ("ALTER TABLE core.layers RENAME TO domains;", "ALTER TABLE library_models.layers RENAME TO domains;",
                 "ALTER TABLE core.entity_types RENAME COLUMN layer_id TO domain_id;",
                 "ALTER TABLE library_models.entity_types RENAME COLUMN layer_id TO domain_id;",
                 "ALTER TABLE core.gap_items RENAME COLUMN layer TO domain;",
                 "ALTER TABLE core.common_items RENAME COLUMN layer TO domain;",
                 "ALTER SEQUENCE core.layers_id_seq RENAME TO domains_id_seq;"):
        assert line in MIG, line
    for trigger in ("00_access", "0_lock", "0_no_truncate", "1_model_lock", "history", "stamp"):
        assert f"ALTER TRIGGER layers_{trigger} ON core.domains RENAME TO domains_{trigger};" in MIG


def test_the_functions_are_written_again_with_the_new_names_and_the_same_results():
    funcs = MIG[MIG.index("CREATE OR REPLACE FUNCTION core.copy_model"):]
    for f in ("core.copy_model", "rpt.f_entities", "rpt.f_catalogue", "rpt.f_gap_items"):
        assert f"CREATE OR REPLACE FUNCTION {f}(" in funcs, f
    body = "\n".join(line for line in funcs.splitlines() if not line.startswith(" RETURNS"))
    assert not OLD.search(body) and "i.layer" not in body
    # the report functions keep their result columns, so every rpt view and Superset dataset stays as it is
    assert "layer_code text, layer text" in funcs and "model_name text, layer text, entity_type_code" in funcs


def test_history_is_never_rewritten_and_the_change_log_reads_old_rows():
    assert "history.row_versions" not in MIG.split("-- Views follow")[1]
    assert "UPDATE history" not in MIG and "DISABLE TRIGGER" not in MIG
    from eax import change_log
    assert change_log.TYPES["layers"] == change_log.TYPES["domains"] == "Domain"


def test_no_code_names_the_old_table_or_column():
    bad = []
    for p in [*(API / "eax").rglob("*.py"), *(API / "tests" / "sql").glob("*.sql"),
              *(f for f in (API / "tests").glob("test_*.py") if f.name != Path(__file__).name)]:
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if OLD.search(line) and "now domains" not in line and "RENAME" not in line and "RENAMES" not in line \
                    and not re.search(r'\("(TABLE|SEQUENCE|COLUMN|CONSTRAINT|INDEX)", "library_models\.', line):
                bad.append(f"{p.relative_to(API)}:{n}: {line.strip()[:100]}")
    assert not bad, bad


def test_the_seed_ids_still_derive_from_layer():
    src = (API / "eax" / "seed" / "build.py").read_text(encoding="utf-8")
    assert 'ids("layer", domain)' in src and 'gid(key, "layer", n)' in src
    assert 'ids("domain"' not in src and not re.search(r'gid\([a-z_]+, "domain"', src)
    assert 'gid(k, "layer", n)' in (API / "eax" / "seed" / "togaf10.py").read_text(encoding="utf-8")


def test_a_library_database_of_its_own_is_renamed_in_place():
    from eax import databases as dbs
    names = {(k, o, n) for k, o, n in dbs.RENAMES["library_models"]}
    assert ("TABLE", "library_models.layers", "domains") in names
    assert ("COLUMN", "library_models.entity_types.layer_id", "domain_id") in names
    for kind, old, new in dbs.RENAMES["library_models"]:
        if kind in ("TABLE", "SEQUENCE", "INDEX"):
            assert f"{old} RENAME TO {new};" in MIG, old          # the same renames as the repository's database
    src = (API / "eax" / "databases.py").read_text(encoding="utf-8")
    assert src.index("renames(conn, key)") < src.index("steps = plan(shared, conn, tables)")
