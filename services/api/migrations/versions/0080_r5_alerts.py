"""R5.9: the alerts system's tables.

Revision ID: 0080_r5_alerts
Revises: 0079_r5_auditor
Create Date: 2026-11-15

The SQL lives in migrations/sql/0080_r5_alerts.sql.
"""

from pathlib import Path

from alembic import op

revision = "0080_r5_alerts"
down_revision = "0079_r5_auditor"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0080_r5_alerts.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.alert_custom, core.alert_config, core.alert_silences, core.alert_history, core.alert_checks")
