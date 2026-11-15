"""R5.1: the optimisation reports.

Revision ID: 0083_r5_optimisation
Revises: 0082_r5_service_desk
Create Date: 2026-11-15

The SQL lives in migrations/sql/0083_r5_optimisation.sql.
"""

from pathlib import Path

from alembic import op

revision = "0083_r5_optimisation"
down_revision = "0082_r5_service_desk"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0083_r5_optimisation.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DROP TABLE IF EXISTS core.optimisation_reports")
