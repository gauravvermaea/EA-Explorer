"""Version 10.0.0: Release 10 accepted (records the version only).

Revision ID: 0115_release_10_0_0
Revises: 0114_release_9_0_0
Create Date: 2026-11-22

The SQL lives in migrations/sql/0115_release_10_0_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0115_release_10_0_0"
down_revision = "0114_release_9_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0115_release_10_0_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '10.0.0'")
