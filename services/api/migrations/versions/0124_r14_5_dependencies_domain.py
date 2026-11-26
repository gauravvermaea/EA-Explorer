"""Release 14.5: DR-01's dependencies function reads the entity type's domain (D939).

Revision ID: 0124_r14_5_dependencies_domain
Revises: 0123_release_14_0_0
Create Date: 2026-11-26

The SQL lives in migrations/sql/0124_r14_5_dependencies_domain.sql.
"""

from pathlib import Path

from alembic import op

revision = "0124_r14_5_dependencies_domain"
down_revision = "0123_release_14_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0124_r14_5_dependencies_domain.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    pass  # the old body read a column that no longer exists: nothing to go back to
