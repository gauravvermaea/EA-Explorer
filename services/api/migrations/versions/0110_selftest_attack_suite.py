"""The self-test's attack suite (R8.2): its constraints only; no version change.

Revision ID: 0110_selftest_attack_suite
Revises: 0109_release_7_9_0
Create Date: 2026-11-21

The SQL lives in migrations/sql/0110_selftest_attack_suite.sql.
"""

from pathlib import Path

from alembic import op

revision = "0110_selftest_attack_suite"
down_revision = "0109_release_7_9_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0110_selftest_attack_suite.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM tests.test_results WHERE suite = 'attack'")
    raw.execute("UPDATE tests.test_runs SET suites = array_remove(suites, 'attack') WHERE 'attack' = ANY(suites)")
    raw.execute((SQL_DIR / "0096_selftest_mcp_suite.sql").read_text(encoding="utf-8"))
