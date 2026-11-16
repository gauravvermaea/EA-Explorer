"""The service desk's foreign keys indexed (R5.47): indexes only; no version change.

Revision ID: 0091_service_desk_fk_indexes
Revises: 0090_selftest_jobs_suite
Create Date: 2026-11-16

The SQL lives in migrations/sql/0091_service_desk_fk_indexes.sql.
"""

from pathlib import Path

from alembic import op

revision = "0091_service_desk_fk_indexes"
down_revision = "0090_selftest_jobs_suite"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0091_service_desk_fk_indexes.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP INDEX IF EXISTS core.service_tickets_type_idx; DROP INDEX IF EXISTS core.service_ticket_files_ticket_idx")
