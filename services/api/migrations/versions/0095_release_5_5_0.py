"""Version 5.5.0: Release 5.5, enterprise discovery (records the version only).

Revision ID: 0095_release_5_5_0
Revises: 0094_r5_5_discovery_projects
Create Date: 2026-11-16

The SQL lives in migrations/sql/0095_release_5_5_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0095_release_5_5_0"
down_revision = "0094_r5_5_discovery_projects"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0095_release_5_5_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '5.1.0'")
