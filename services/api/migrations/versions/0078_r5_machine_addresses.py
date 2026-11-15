"""R5.2: a machine credential limited to its own addresses.

Revision ID: 0078_r5_machine_addresses
Revises: 0077_release_4_0_0
Create Date: 2026-11-15

The SQL lives in migrations/sql/0078_r5_machine_addresses.sql.
"""

from pathlib import Path

from alembic import op

revision = "0078_r5_machine_addresses"
down_revision = "0077_release_4_0_0"
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    raw = op.get_bind().connection.driver_connection  # the psycopg 3 connection
    raw.execute((SQL_DIR / "0078_r5_machine_addresses.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection.driver_connection
    raw.execute("ALTER TABLE core.machine_credentials DROP COLUMN IF EXISTS allowed_addresses")
