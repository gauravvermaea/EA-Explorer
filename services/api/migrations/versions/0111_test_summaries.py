"""The test summaries kept and the detailed files deletable (D825): a table and columns; no version change.

Revision ID: 0111_test_summaries
Revises: 0110_selftest_attack_suite
Create Date: 2026-11-21

The SQL lives in migrations/sql/0111_test_summaries.sql.
"""

from pathlib import Path

from alembic import op

revision = "0111_test_summaries"
down_revision = "0110_selftest_attack_suite"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0111_test_summaries.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS tests.full_tests")
    raw.execute("ALTER TABLE IF EXISTS tests.test_runs DROP COLUMN IF EXISTS summary, "
                "DROP COLUMN IF EXISTS files_deleted_at, DROP COLUMN IF EXISTS files_deleted_by")
