"""The self-test's MCP suite (R5.5.5): its constraints only; no version change.

Revision ID: 0096_selftest_mcp_suite
Revises: 0095_release_5_5_0
Create Date: 2026-11-16

The SQL lives in migrations/sql/0096_selftest_mcp_suite.sql.
"""

from pathlib import Path

from alembic import op

revision = "0096_selftest_mcp_suite"
down_revision = "0095_release_5_5_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0096_selftest_mcp_suite.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM tests.test_results WHERE suite = 'mcp'")
    raw.execute("UPDATE tests.test_runs SET suites = array_remove(suites, 'mcp') WHERE 'mcp' = ANY(suites)")
    raw.execute((SQL_DIR / "0090_selftest_jobs_suite.sql").read_text(encoding="utf-8"))
