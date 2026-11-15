"""R5.12: the record of database maintenance.

Revision ID: 0081_r5_db_maintenance
Revises: 0080_r5_alerts
Create Date: 2026-11-15

The SQL lives in migrations/sql/0081_r5_db_maintenance.sql.
"""

from pathlib import Path

from alembic import op

revision = "0081_r5_db_maintenance"
down_revision = "0080_r5_alerts"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0081_r5_db_maintenance.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.db_maintenance_runs")
