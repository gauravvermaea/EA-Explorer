"""The safety copies kept before a settings import (Release 6.7, D755, D768).

Revision ID: 0106_r6_7_settings_copies
Revises: 0105_r6_6_db_integrity
Create Date: 2026-11-18

The SQL lives in migrations/sql/0106_r6_7_settings_copies.sql.
"""

from pathlib import Path

from alembic import op

revision = "0106_r6_7_settings_copies"
down_revision = "0105_r6_6_db_integrity"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0106_r6_7_settings_copies.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.settings_copies")
