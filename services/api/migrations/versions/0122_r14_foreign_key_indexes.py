"""Release 14 (R14.38): an index for each of the five foreign keys of the Release 12 project tables that had none.

Revision ID: 0122_r14_foreign_key_indexes
Revises: 0121_release_13_0_0
Create Date: 2026-11-24

The SQL lives in migrations/sql/0122_r14_foreign_key_indexes.sql.
"""

from pathlib import Path

from alembic import op

revision = "0122_r14_foreign_key_indexes"
down_revision = "0121_release_13_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
INDEXES = ("backlog_items_item_idx", "backlog_items_sprint_idx", "sprint_decisions_backlog_idx", "raci_item_idx",
           "raci_step_idx")


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0122_r14_foreign_key_indexes.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    for name in INDEXES:
        raw.execute(f"DROP INDEX IF EXISTS proj.{name}")
