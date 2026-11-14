"""The resource history (R3.5-M8): operations.resource_samples.

Revision ID: 0073_resource_history
Revises: 0072_release_3_0_0
Create Date: 2026-11-14

The SQL lives in migrations/sql/0073_resource_history.sql.
"""

from pathlib import Path

from alembic import op

revision = "0073_resource_history"
down_revision = "0072_release_3_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0073_resource_history.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS operations.resource_samples")
