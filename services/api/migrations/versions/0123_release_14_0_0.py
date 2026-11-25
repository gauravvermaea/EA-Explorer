"""Version 14.0.0: Release 14 accepted (records the version only).

Revision ID: 0123_release_14_0_0
Revises: 0122_r14_foreign_key_indexes
Create Date: 2026-11-25

The SQL lives in migrations/sql/0123_release_14_0_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0123_release_14_0_0"
down_revision = "0122_r14_foreign_key_indexes"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0123_release_14_0_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '14.0.0'")
