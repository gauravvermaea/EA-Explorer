"""Version 8.0.0: Release 8 closed, code quality and testing (records the version only).

Revision ID: 0112_release_8_0_0
Revises: 0111_test_summaries
Create Date: 2026-11-22

The SQL lives in migrations/sql/0112_release_8_0_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0112_release_8_0_0"
down_revision = "0111_test_summaries"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0112_release_8_0_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '8.0.0'")
