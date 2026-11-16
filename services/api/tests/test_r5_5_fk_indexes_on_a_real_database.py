"""Every foreign key has an index, as the self-test's database check sees it (owner, 16 Nov 2026, 15:02: "foreign keys
have an index (speed): core.discovery_found_in(resource_id); core.discovery_not_found(run_id)": migration 0097). The
check's own SQL (eax/testing/db_checks.py) run on a database every migration has run on, so a new table's foreign key
without an index fails here, before a self-test finds it.

Needs EAX_MIGRATED_TEST_DSN (skipped without it)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")
pytestmark = pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")


def test_every_foreign_key_has_an_index():
    from sqlalchemy import create_engine, text

    from eax.testing import db_checks
    sql = next(q for name, q, _o in db_checks.CHECKS if name == "foreign keys have an index (speed)")
    eng = create_engine(DSN)
    try:
        with eng.connect() as c:
            missing = [r[0] for r in c.execute(text(sql))]
    finally:
        eng.dispose()
    assert missing == []
