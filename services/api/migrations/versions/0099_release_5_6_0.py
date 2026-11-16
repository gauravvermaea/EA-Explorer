"""Version 5.6.0: Release 5.6, backup and restore tested, job priorities, GitHub Releases (records the version only).

Revision ID: 0099_release_5_6_0
Revises: 0098_r5_6_job_priorities
Create Date: 2026-11-16

The SQL lives in migrations/sql/0099_release_5_6_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0099_release_5_6_0"
down_revision = "0098_r5_6_job_priorities"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0099_release_5_6_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '5.6.0'")
