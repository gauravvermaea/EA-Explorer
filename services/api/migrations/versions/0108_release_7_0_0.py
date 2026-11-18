"""Version 7.0.0: Release 7 closed, the documentation release (records the version only).

Revision ID: 0108_release_7_0_0
Revises: 0107_release_6_7_0
Create Date: 2026-11-18

The SQL lives in migrations/sql/0108_release_7_0_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0108_release_7_0_0"
down_revision = "0107_release_6_7_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0108_release_7_0_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '7.0.0'")
