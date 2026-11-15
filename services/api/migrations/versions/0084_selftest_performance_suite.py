"""The self-test's performance suite (R5.18): its constraints only; no version change.

Revision ID: 0084_selftest_performance_suite
Revises: 0083_r5_optimisation
Create Date: 2026-11-15

The SQL lives in migrations/sql/0084_selftest_performance_suite.sql.
"""

from pathlib import Path

from alembic import op

revision = "0084_selftest_performance_suite"
down_revision = "0083_r5_optimisation"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0084_selftest_performance_suite.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    pass
