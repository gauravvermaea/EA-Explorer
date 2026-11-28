"""Release 14.6: which version of a standard each metamodel item belongs to (D965; owner, 28 Nov 2026, 07:43: "in both
core domain and entity types we should have a archimate_version_id_start and archimate_version_id_end ... when new
versions of archimate come we know what new items come in it, then what is removed goes in end and what lives on is in
new version"; 07:47: the relationship types and allowed relationships too, a "replaced by" link, the names
standard_version_start_id and standard_version_end_id, the end empty while the item is current). Checked on PostgreSQL
16 when built: the seed marks the ArchiMate model's 7 domains, 42 of its 49 element types (not the 7 extensions), its 11
relationship types and the 3,140 allowed relationships between ArchiMate's own types; core.copy_model carries the
versions and the replaced-by link (mapped to the copy's own rows) to a copy."""

from __future__ import annotations

from pathlib import Path

from eax.seed import archimate4 as A
from eax.seed import build as B

SQL = (Path(__file__).resolve().parents[1] / "migrations" / "sql" / "0126_r14_6_standard_versions.sql").read_text(encoding="utf-8")
TABLES = ("domains", "entity_types", "relationship_types", "allowed_relationships")


def test_a_table_of_versions_and_the_columns_on_each_metamodel_table():
    assert "CREATE TABLE IF NOT EXISTS core.standard_versions" in SQL and "UNIQUE (standard, version)" in SQL
    assert "VALUES ('ArchiMate', '4.0', 40," in SQL
    for t in TABLES:
        for col in ("standard_version_start_id bigint REFERENCES core.standard_versions (id)",
                    "standard_version_end_id bigint REFERENCES core.standard_versions (id)",
                    f"replaced_by_id bigint REFERENCES core.{t} (id) ON DELETE SET NULL"):
            assert col in SQL, (t, col)
        for col in ("standard_version_start_id", "standard_version_end_id", "replaced_by_id"):
            assert f"CREATE INDEX IF NOT EXISTS {t}_{col}_idx ON core.{t} ({col});" in SQL        # every foreign key indexed
        assert f"ALTER TABLE library_models.{t}\n    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint," in SQL


def test_a_copy_of_a_model_carries_them():
    copy = SQL[SQL.index("CREATE OR REPLACE FUNCTION core.copy_model"):]
    assert copy.count("standard_version_start_id, standard_version_end_id") >= 6
    for t in TABLES:
        assert f"UPDATE core.{t} d SET replaced_by_id = dn.id" in copy


def test_the_seed_marks_archimate_40_and_leaves_the_extensions_and_the_end_empty():
    sql = B.standard_version_sql("m-guid")
    assert sql.count("standard = 'ArchiMate' AND version = '4.0'") == 4 and "standard_version_end_id" not in sql
    for ext in A.EXTENSION_DESCRIPTIONS:
        assert f"'{ext}'" in sql
    assert "standard_version_sql(m)" in (Path(B.__file__)).read_text(encoding="utf-8")
    assert "standard_version_sql" not in B.metamodel_sql(B.TEMPLATE_KEY, None, missing_only=True)   # an upgrade changes nothing
    assert "UPDATE core.domains SET standard_version_start_id" in B.metamodel_sql(B.TEMPLATE_KEY, None)
