"""Job priorities (R5.6-Q2): the levels changed on the Jobs page and the skips; no version change.

Revision ID: 0098_r5_6_job_priorities
Revises: 0097_discovery_fk_indexes
Create Date: 2026-11-16

The SQL lives in migrations/sql/0098_r5_6_job_priorities.sql.
"""

from pathlib import Path

from alembic import op

revision = "0098_r5_6_job_priorities"
down_revision = "0097_discovery_fk_indexes"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0098_r5_6_job_priorities.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.job_priorities; DROP TABLE IF EXISTS core.job_skips")
