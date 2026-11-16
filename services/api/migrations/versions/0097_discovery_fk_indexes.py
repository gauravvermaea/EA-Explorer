"""Indexes for two foreign keys of the discovery tables (R5.5): no version change.

Revision ID: 0097_discovery_fk_indexes
Revises: 0096_selftest_mcp_suite
Create Date: 2026-11-16

The SQL lives in migrations/sql/0097_discovery_fk_indexes.sql.
"""

from pathlib import Path

from alembic import op

revision = "0097_discovery_fk_indexes"
down_revision = "0096_selftest_mcp_suite"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0097_discovery_fk_indexes.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP INDEX IF EXISTS core.discovery_found_in_resource; DROP INDEX IF EXISTS core.discovery_not_found_run")
