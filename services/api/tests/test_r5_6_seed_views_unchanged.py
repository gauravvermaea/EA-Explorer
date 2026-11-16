"""R5.6-B1, the owner's backup and restore test (16 Nov 2026, 22:21): "core.viewpoints: same rows, other content". Every
start loaded the report catalogue again and stamped every built-in view as modified, so a restored installation never
looked like its backup. A built-in view is now written only when something in it changed.

On a real database (EAX_MIGRATED_TEST_DSN); the catalogue loaded twice in one transaction, rolled back. A row written
again gets a new physical place (ctid) even in the same transaction, so that is what is compared."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")


def test_the_catalogue_only_writes_a_view_when_it_changed_in_the_sql():
    from eax.seed.catalog import catalog_sql
    s = catalog_sql()
    assert "IS DISTINCT FROM (EXCLUDED.name" in s and "core.viewpoints.togaf_artifact)" in s


@pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")
def test_loading_the_catalogue_again_leaves_every_built_in_view_untouched():
    from sqlalchemy import create_engine, text

    from eax.seed.catalog import catalog_sql
    eng = create_engine(DSN)
    with eng.connect() as c:
        tx = c.begin()
        try:
            c.exec_driver_sql(catalog_sql())
            q = text("SELECT code, ctid::text, modified_at FROM core.viewpoints WHERE is_builtin ORDER BY code")
            before = c.execute(q).all()
            assert before
            c.exec_driver_sql(catalog_sql())
            assert c.execute(q).all() == before
            # a real change is still written
            code = before[0][0]
            c.execute(text("UPDATE core.viewpoints SET purpose = 'changed by hand' WHERE code = :c"), {"c": code})
            c.exec_driver_sql(catalog_sql())
            assert c.execute(text("SELECT purpose FROM core.viewpoints WHERE code = :c"), {"c": code}).scalar() != "changed by hand"
        finally:
            tx.rollback()
