"""R5.27: the service desk reworked (groups, the Super Admins assign, no approvals).

Revision ID: 0087_r5_service_desk_groups
Revises: 0086_r5_live_browser
Create Date: 2026-11-15

The SQL lives in migrations/sql/0087_r5_service_desk_groups.sql.
"""

from pathlib import Path

from alembic import op

revision = "0087_r5_service_desk_groups"
down_revision = "0086_r5_live_browser"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0087_r5_service_desk_groups.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("UPDATE core.service_types SET enabled = true WHERE area IN ('Reports', 'Help')")
