"""R5.19: the saved server sizing estimates.

Revision ID: 0085_r5_sizing
Revises: 0084_selftest_performance_suite
Create Date: 2026-11-15

The SQL lives in migrations/sql/0085_r5_sizing.sql.
"""

from pathlib import Path

from alembic import op

revision = "0085_r5_sizing"
down_revision = "0084_selftest_performance_suite"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0085_r5_sizing.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.sizing_estimates")
