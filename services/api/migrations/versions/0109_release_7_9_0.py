"""Version 7.9.0: Release 7.9 closed, error codes and the error code guide (records the version only).

Revision ID: 0109_release_7_9_0
Revises: 0108_release_7_0_0
Create Date: 2026-11-19

The SQL lives in migrations/sql/0109_release_7_9_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0109_release_7_9_0"
down_revision = "0108_release_7_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0109_release_7_9_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '7.9.0'")
