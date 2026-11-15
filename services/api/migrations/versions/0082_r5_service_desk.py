"""R5.11: the service desk and its first catalogue.

Revision ID: 0082_r5_service_desk
Revises: 0081_r5_db_maintenance
Create Date: 2026-11-15

The SQL lives in migrations/sql/0082_r5_service_desk.sql.
"""

from pathlib import Path

from alembic import op

revision = "0082_r5_service_desk"
down_revision = "0081_r5_db_maintenance"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0082_r5_service_desk.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.service_ticket_files, core.service_ticket_events, core.service_tickets, core.service_types")
