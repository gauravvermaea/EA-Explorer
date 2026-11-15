"""R5.28: core.tasks' duplicate index removed.

Revision ID: 0088_r5_tasks_index
Revises: 0087_r5_service_desk_groups
Create Date: 2026-11-15

The SQL lives in migrations/sql/0088_r5_tasks_index.sql.
"""

from pathlib import Path

from alembic import op

revision = "0088_r5_tasks_index"
down_revision = "0087_r5_service_desk_groups"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0088_r5_tasks_index.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("CREATE INDEX IF NOT EXISTS tasks_requested_by_idx ON core.tasks (requested_by, requested_at DESC)")
