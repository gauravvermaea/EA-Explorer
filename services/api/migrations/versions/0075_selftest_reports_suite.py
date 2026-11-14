"""The self-test's seventh suite, reports (R4.1): its constraints only; no version change.

Revision ID: 0075_selftest_reports_suite
Revises: 0074_release_3_5_0
Create Date: 2026-11-14

The SQL lives in migrations/sql/0075_selftest_reports_suite.sql.
"""

from pathlib import Path

from alembic import op

revision = "0075_selftest_reports_suite"
down_revision = "0074_release_3_5_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0075_selftest_reports_suite.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    pass
