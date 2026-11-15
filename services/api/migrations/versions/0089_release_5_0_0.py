"""Version 5.0.0: Release 5 (records the version only).

Revision ID: 0089_release_5_0_0
Revises: 0076_step_moved
Create Date: 2026-11-15

The SQL lives in migrations/sql/0089_release_5_0_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0089_release_5_0_0"
down_revision = "0088_r5_tasks_index"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0089_release_5_0_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '5.0.0'")
