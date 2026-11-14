"""A step's history may say it was moved (R4.21): a check only; no version change.

Revision ID: 0076_step_moved
Revises: 0075_selftest_reports_suite
Create Date: 2026-11-14

The SQL lives in migrations/sql/0076_step_moved.sql.
"""

from pathlib import Path

from alembic import op

revision = "0076_step_moved"
down_revision = "0075_selftest_reports_suite"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0076_step_moved.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    pass
