"""R5.22: the Auditor role (sees everything, changes nothing).

Revision ID: 0079_r5_auditor
Revises: 0078_r5_machine_addresses
Create Date: 2026-11-15

The SQL lives in migrations/sql/0079_r5_auditor.sql.
"""

from pathlib import Path

from alembic import op

revision = "0079_r5_auditor"
down_revision = "0078_r5_machine_addresses"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0079_r5_auditor.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("DELETE FROM core.role_mappings WHERE app_role = 'auditor'; DELETE FROM core.app_roles WHERE code = 'auditor'")
