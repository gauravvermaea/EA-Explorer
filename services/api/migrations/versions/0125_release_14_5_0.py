"""Version 14.5.0: Release 14.5 accepted (records the version only).

Revision ID: 0125_release_14_5_0
Revises: 0124_r14_5_dependencies_domain
Create Date: 2026-11-27

The SQL lives in migrations/sql/0125_release_14_5_0.sql.
"""

from pathlib import Path

from alembic import op

revision = "0125_release_14_5_0"
down_revision = "0124_r14_5_dependencies_domain"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0125_release_14_5_0.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.schema_versions WHERE version = '14.5.0'")
