"""Version 12.0.0: Release 12 closed as unstable (records the version only).

Revision ID: 0120_release_12_0_0
Revises: 0119_r12_project_management
Create Date: 2026-11-23

The SQL lives in migrations/sql/0120_release_12_0_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0120_release_12_0_0"
down_revision = "0119_r12_project_management"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0120_release_12_0_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '12.0.0'")
