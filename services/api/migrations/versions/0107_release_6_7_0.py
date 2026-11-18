"""Version 6.7.0: Release 6 closed, secrets and certificates, sync, setup, settings (records the version only).

Revision ID: 0107_release_6_7_0
Revises: 0106_r6_7_settings_copies
Create Date: 2026-11-18

The SQL lives in migrations/sql/0107_release_6_7_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0107_release_6_7_0"
down_revision = "0106_r6_7_settings_copies"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0107_release_6_7_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '6.7.0'")
